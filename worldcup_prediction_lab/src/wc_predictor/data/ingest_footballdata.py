"""Ingest Football-Data.co.uk World Cup odds into market-odds silver data."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.data.devig import no_vig_three_way
from wc_predictor.data.team_aliases import TeamAliasResolver


WORLDCUP_WORKBOOK_URL = "https://www.football-data.co.uk/WorldCup2026.xlsx"
DEFAULT_SHEETS = (
    "WorldCup2014",
    "WorldCup2018",
    "WorldCup2022",
    "WorldCup2026Qualifiers",
    "WorldCup2026",
)
MARKET_ODDS_COLUMNS = [
    "date",
    "home_team_id",
    "away_team_id",
    "home_team_name",
    "away_team_name",
    "bookmaker",
    "prob_home",
    "prob_draw",
    "prob_away",
    "source_sheet",
]
ALIAS_SOURCES = ("footballdata", "fifa", "martj42", "openfootball", "manual")


@dataclass(frozen=True)
class RawSnapshot:
    source_url: str
    ingest_utc: str
    sha256: str
    byte_count: int
    raw_path: str
    manifest_path: str


def _utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _write_parquet(dataframe: pd.DataFrame, path: Path) -> None:
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        connection.register("df_to_write", dataframe)
        connection.execute(f"COPY df_to_write TO '{escaped_path}' (FORMAT PARQUET)")


def _read_excel_input(path_or_bytes: bytes | str | Path) -> BytesIO | str | Path:
    if isinstance(path_or_bytes, bytes):
        return BytesIO(path_or_bytes)
    return path_or_bytes


def _column_key(column: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(column).strip().casefold())


def _first_column(columns_by_key: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        column = columns_by_key.get(_column_key(candidate))
        if column is not None:
            return column
    return None


def _sheet_columns(dataframe: pd.DataFrame) -> dict[str, str]:
    return {_column_key(column): str(column) for column in dataframe.columns}


def _odds_columns(
    dataframe: pd.DataFrame,
) -> tuple[str, tuple[str, str, str]] | None:
    columns = _sheet_columns(dataframe)
    candidates = [
        ("avg", ("H-Avg", "AvgH"), ("D-Avg", "AvgD"), ("A-Avg", "AvgA")),
        ("bet365", ("bet365-H", "B365H"), ("bet365-D", "B365D"), ("bet365-A", "B365A")),
    ]
    for bookmaker, home_candidates, draw_candidates, away_candidates in candidates:
        home = _first_column(columns, home_candidates)
        draw = _first_column(columns, draw_candidates)
        away = _first_column(columns, away_candidates)
        if home is not None and draw is not None and away is not None:
            return bookmaker, (home, draw, away)
    return None


def _required_match_columns(dataframe: pd.DataFrame) -> tuple[str, str, str] | None:
    columns = _sheet_columns(dataframe)
    date = _first_column(columns, ("Date", "Match Date"))
    home = _first_column(columns, ("Home", "HomeTeam", "Home Team"))
    away = _first_column(columns, ("Away", "AwayTeam", "Away Team"))
    if date is None or home is None or away is None:
        return None
    return date, home, away


def _clean_team_name(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _resolve_team_id(
    name: str | None,
    resolver: TeamAliasResolver,
    unmatched_names: set[str],
) -> str | pd._libs.missing.NAType:
    if name is None:
        return pd.NA
    for source in ALIAS_SOURCES:
        try:
            return resolver.resolve(name, source=source).canonical_team_id
        except KeyError:
            continue
    unmatched_names.add(name)
    return pd.NA


def _has_missing_odds(row: pd.Series, odds_columns: tuple[str, str, str]) -> bool:
    return any(pd.isna(row[column]) or str(row[column]).strip() == "" for column in odds_columns)


def _empty_market_odds() -> pd.DataFrame:
    return pd.DataFrame(columns=MARKET_ODDS_COLUMNS)


def parse_workbook(
    path_or_bytes: bytes | str | Path,
    *,
    resolver: TeamAliasResolver | None = None,
    sheets: tuple[str, ...] = DEFAULT_SHEETS,
    silver_dir: str | Path = settings.SILVER_DIR,
    write: bool = False,
) -> pd.DataFrame:
    """Parse Football-Data World Cup workbook sheets into no-vig market odds."""

    resolver = resolver or TeamAliasResolver.from_csv()
    excel = pd.ExcelFile(_read_excel_input(path_or_bytes), engine="openpyxl")
    unmatched_names: set[str] = set()
    rows: list[dict[str, Any]] = []
    rows_per_sheet: dict[str, int] = {}
    odds_rows_per_sheet: dict[str, int] = {}
    skipped_missing_odds_rows = 0
    skipped_invalid_odds_rows = 0
    skipped_missing_required_rows = 0

    for sheet_name in sheets:
        if sheet_name not in excel.sheet_names:
            continue
        source = excel.parse(sheet_name=sheet_name)
        rows_per_sheet[sheet_name] = int(len(source))
        odds_rows_per_sheet[sheet_name] = 0

        match_columns = _required_match_columns(source)
        market_columns = _odds_columns(source)
        if match_columns is None or market_columns is None:
            skipped_missing_required_rows += int(len(source))
            continue

        date_column, home_column, away_column = match_columns
        bookmaker, odds_columns = market_columns

        for _, row in source.iterrows():
            home_name = _clean_team_name(row[home_column])
            away_name = _clean_team_name(row[away_column])
            match_date = pd.to_datetime(row[date_column], errors="coerce")
            if home_name is None or away_name is None or pd.isna(match_date):
                skipped_missing_required_rows += 1
                continue
            if _has_missing_odds(row, odds_columns):
                skipped_missing_odds_rows += 1
                continue

            try:
                prob_home, prob_draw, prob_away = no_vig_three_way(
                    row[odds_columns[0]],
                    row[odds_columns[1]],
                    row[odds_columns[2]],
                )
            except ValueError:
                skipped_invalid_odds_rows += 1
                continue

            rows.append(
                {
                    "date": match_date.normalize(),
                    "home_team_id": _resolve_team_id(home_name, resolver, unmatched_names),
                    "away_team_id": _resolve_team_id(away_name, resolver, unmatched_names),
                    "home_team_name": home_name,
                    "away_team_name": away_name,
                    "bookmaker": bookmaker,
                    "prob_home": prob_home,
                    "prob_draw": prob_draw,
                    "prob_away": prob_away,
                    "source_sheet": sheet_name,
                }
            )
            odds_rows_per_sheet[sheet_name] += 1

    market_odds = _empty_market_odds() if not rows else pd.DataFrame(rows)
    if not market_odds.empty:
        market_odds = market_odds.loc[:, MARKET_ODDS_COLUMNS].sort_values(
            ["date", "source_sheet", "home_team_name", "away_team_name", "bookmaker"],
            kind="mergesort",
        )
    market_odds = market_odds.reset_index(drop=True)
    market_odds.attrs.update(
        {
            "source": "footballdata",
            "rows_per_sheet": rows_per_sheet,
            "odds_rows_per_sheet": odds_rows_per_sheet,
            "skipped_missing_odds_rows": int(skipped_missing_odds_rows),
            "skipped_invalid_odds_rows": int(skipped_invalid_odds_rows),
            "skipped_missing_required_rows": int(skipped_missing_required_rows),
            "unmatched_team_names": sorted(unmatched_names),
            "unmatched_team_count": len(unmatched_names),
        }
    )

    if write:
        _write_parquet(
            market_odds,
            Path(silver_dir) / "footballdata_market_odds.parquet",
        )
    return market_odds


def _validate_xlsx_response(content: bytes, content_type: str) -> None:
    if not content.startswith(b"PK\x03\x04"):
        raise ValueError("downloaded Football-Data workbook is not an XLSX zip payload")
    normalized_type = content_type.casefold()
    allowed_type = (
        "spreadsheet" in normalized_type
        or "excel" in normalized_type
        or "octet-stream" in normalized_type
        or normalized_type == ""
    )
    if not allowed_type:
        raise ValueError(f"unexpected Football-Data workbook content type: {content_type!r}")


def download_worldcup_workbook(
    url: str = WORLDCUP_WORKBOOK_URL,
    raw_dir: str | Path = settings.RAW_DIR / "footballdata",
) -> RawSnapshot:
    """Download the Football-Data World Cup workbook to a local gitignored raw dir."""

    import httpx

    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    content = response.content
    _validate_xlsx_response(content, response.headers.get("content-type", ""))

    digest = hashlib.sha256(content).hexdigest()
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    workbook_path = raw_path / f"WorldCup2026_{_utc_slug()}_{digest[:12]}.xlsx"
    workbook_path.write_bytes(content)

    manifest_path = workbook_path.with_suffix(".manifest.json")
    snapshot = RawSnapshot(
        source_url=url,
        ingest_utc=_utc_iso(),
        sha256=digest,
        byte_count=len(content),
        raw_path=str(workbook_path),
        manifest_path=str(manifest_path),
    )
    manifest_path.write_text(
        json.dumps(asdict(snapshot), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


def summarize_quality(market_odds: pd.DataFrame) -> dict[str, Any]:
    if market_odds.empty:
        date_min = None
        date_max = None
        distinct_matches = 0
    else:
        dates = pd.to_datetime(market_odds["date"], errors="coerce")
        date_min = dates.min().strftime("%Y-%m-%d")
        date_max = dates.max().strftime("%Y-%m-%d")
        distinct_matches = int(
            market_odds[["date", "home_team_name", "away_team_name"]]
            .drop_duplicates()
            .shape[0]
        )

    return {
        "total_odds_rows": int(len(market_odds)),
        "rows_per_sheet": market_odds.attrs.get("rows_per_sheet", {}),
        "odds_rows_per_sheet": market_odds.attrs.get("odds_rows_per_sheet", {}),
        "date_min": date_min,
        "date_max": date_max,
        "distinct_matches": distinct_matches,
        "unmatched_team_count": int(market_odds.attrs.get("unmatched_team_count", 0)),
        "unmatched_team_names": market_odds.attrs.get("unmatched_team_names", []),
        "skipped_missing_odds_rows": int(
            market_odds.attrs.get("skipped_missing_odds_rows", 0)
        ),
        "skipped_invalid_odds_rows": int(
            market_odds.attrs.get("skipped_invalid_odds_rows", 0)
        ),
        "skipped_missing_required_rows": int(
            market_odds.attrs.get("skipped_missing_required_rows", 0)
        ),
    }


def write_quality_report(
    summary: dict[str, Any],
    report_dir: str | Path = settings.REPORTS_DIR / "data_quality",
) -> Path:
    report_path = Path(report_dir) / "footballdata_market_odds_q1.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Q1 Football-Data market odds data quality",
        "",
        f"- Source: `{summary['source_url']}`",
        f"- Ingest UTC: `{summary['ingest_utc']}`",
        f"- Raw SHA-256: `{summary['sha256']}`",
        f"- Total normalized odds rows: {summary['total_odds_rows']:,}",
        f"- Distinct matches: {summary['distinct_matches']:,}",
        f"- Date range: {summary['date_min']} to {summary['date_max']}",
        f"- Unmatched team-name count: {summary['unmatched_team_count']:,}",
        f"- Rows skipped for missing odds: {summary['skipped_missing_odds_rows']:,}",
        f"- Rows skipped for invalid odds: {summary['skipped_invalid_odds_rows']:,}",
        f"- Rows skipped for missing required fields/schema: {summary['skipped_missing_required_rows']:,}",
        "",
        "Rows per workbook sheet:",
    ]
    for sheet_name, count in sorted(summary["rows_per_sheet"].items()):
        odds_count = summary["odds_rows_per_sheet"].get(sheet_name, 0)
        lines.append(f"- {sheet_name}: {count:,} source rows; {odds_count:,} normalized odds rows")

    lines.extend(
        [
            "",
            "Unmatched team names are retained with null canonical ids so ingestion does not",
            "silently drop historical matches. Q2 can either map these aliases or filter to",
            "resolved matches before joining to Elo predictions.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_schema_sample(
    market_odds: pd.DataFrame,
    report_dir: str | Path = settings.REPORTS_DIR / "data_quality",
    *,
    row_count: int = 5,
) -> Path:
    sample_path = Path(report_dir) / "footballdata_market_odds_schema_sample.csv"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    market_odds.loc[:, MARKET_ODDS_COLUMNS].head(row_count).to_csv(
        sample_path,
        index=False,
    )
    return sample_path


def ingest(
    url: str = WORLDCUP_WORKBOOK_URL,
    *,
    raw_dir: str | Path = settings.RAW_DIR / "footballdata",
    silver_dir: str | Path = settings.SILVER_DIR,
    report_dir: str | Path = settings.REPORTS_DIR / "data_quality",
) -> tuple[RawSnapshot, pd.DataFrame, dict[str, Any]]:
    snapshot = download_worldcup_workbook(url=url, raw_dir=raw_dir)
    market_odds = parse_workbook(snapshot.raw_path, silver_dir=silver_dir, write=True)
    summary = summarize_quality(market_odds)
    summary.update(
        {
            "source_url": snapshot.source_url,
            "ingest_utc": snapshot.ingest_utc,
            "sha256": snapshot.sha256,
            "raw_path": snapshot.raw_path,
            "manifest_path": snapshot.manifest_path,
        }
    )
    report_path = write_quality_report(summary, report_dir=report_dir)
    sample_path = write_schema_sample(market_odds, report_dir=report_dir)
    summary["report_path"] = str(report_path)
    summary["schema_sample_path"] = str(sample_path)
    return snapshot, market_odds, summary


if __name__ == "__main__":
    _, _, ingestion_summary = ingest()
    print(json.dumps(ingestion_summary, indent=2, sort_keys=True))
