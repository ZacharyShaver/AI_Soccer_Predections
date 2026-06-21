"""Ingest martj42 international results into bronze and silver datasets."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.data.team_aliases import (
    TeamAlias,
    TeamAliasResolver,
    normalize_team_name,
)


MARTJ42_RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)

SOURCE_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
]

MATCH_COLUMNS = [
    "match_id",
    "date",
    "home_team_id",
    "away_team_id",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
    "source",
    "occurrence_index",
]

FIXTURE_COLUMNS = [
    "date",
    "home_team_id",
    "away_team_id",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
    "source",
    "status",
]


@dataclass(frozen=True)
class RawSnapshot:
    source_url: str
    ingest_utc: str
    row_count: int
    sha256: str
    raw_path: str
    manifest_path: str


def _utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _read_csv_input(csv_bytes_or_path: bytes | str | Path) -> Any:
    if isinstance(csv_bytes_or_path, bytes):
        return BytesIO(csv_bytes_or_path)

    if isinstance(csv_bytes_or_path, Path):
        return csv_bytes_or_path

    possible_path = Path(csv_bytes_or_path)
    if "\n" not in csv_bytes_or_path and possible_path.exists():
        return possible_path
    return StringIO(csv_bytes_or_path)


def _write_parquet(dataframe: pd.DataFrame, path: Path) -> None:
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        connection.register("df_to_write", dataframe)
        connection.execute(
            f"COPY df_to_write TO '{escaped_path}' (FORMAT PARQUET)"
        )


def _content_row_count(content: bytes) -> int:
    return len(pd.read_csv(BytesIO(content), usecols=["date"]))


def download_raw(
    url: str = MARTJ42_RESULTS_URL,
    raw_dir: str | Path = settings.RAW_DIR,
) -> RawSnapshot:
    """Download results.csv and persist a hashed raw snapshot plus manifest."""

    import httpx

    response = httpx.get(url, timeout=60.0)
    response.raise_for_status()
    content = response.content
    digest = hashlib.sha256(content).hexdigest()
    row_count = _content_row_count(content)
    ingest_utc = _utc_iso()

    raw_path = Path(raw_dir) / f"martj42_results_{_utc_slug()}_{digest[:12]}.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(content)

    manifest_path = raw_path.with_suffix(".manifest.json")
    snapshot = RawSnapshot(
        source_url=url,
        ingest_utc=ingest_utc,
        row_count=row_count,
        sha256=digest,
        raw_path=str(raw_path),
        manifest_path=str(manifest_path),
    )
    manifest_path.write_text(
        json.dumps(asdict(snapshot), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


def parse_bronze(
    csv_bytes_or_path: bytes | str | Path,
    bronze_dir: str | Path = settings.BRONZE_DIR,
    *,
    write: bool = True,
) -> pd.DataFrame:
    """Parse martj42 results.csv into a source-shaped bronze DataFrame."""

    dataframe = pd.read_csv(
        _read_csv_input(csv_bytes_or_path),
        dtype="string",
        keep_default_na=True,
    )
    missing_columns = [column for column in SOURCE_COLUMNS if column not in dataframe]
    if missing_columns:
        raise ValueError(f"missing source columns: {', '.join(missing_columns)}")

    dataframe = dataframe.loc[:, SOURCE_COLUMNS].copy()
    if write:
        _write_parquet(
            dataframe,
            Path(bronze_dir) / "martj42_results_bronze.parquet",
        )
    return dataframe


def _score_present(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype("string").str.strip().ne("")


def _coerce_scores(dataframe: pd.DataFrame, score_columns: list[str]) -> pd.DataFrame:
    coerced = dataframe.copy()
    for column in score_columns:
        numeric = pd.to_numeric(coerced[column], errors="coerce")
        invalid = numeric.isna() | (numeric < 0) | (numeric % 1 != 0)
        if invalid.any():
            raise ValueError("scores must be non-negative integers")
        coerced[column] = numeric.astype("Int64")
    return coerced


def _coerce_neutral(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.casefold()
    mapping = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
    }
    invalid = normalized.isna() | ~normalized.isin(mapping)
    if invalid.any():
        raise ValueError("neutral must be boolean")
    return normalized.map(mapping).astype(bool)


def _format_match_id_part(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _match_id(row: pd.Series) -> str:
    parts = [
        _format_match_id_part(row["date"]),
        _format_match_id_part(row["home_team_id"]),
        _format_match_id_part(row["away_team_id"]),
        _format_match_id_part(row["tournament"]),
        _format_match_id_part(row["city"]),
        _format_match_id_part(row["occurrence_index"]),
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _canonical_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_team_name(name)).strip("-")
    if slug:
        return slug
    return "team-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def _team_alias_for_martj42(
    name: str,
    resolver: TeamAliasResolver,
    auto_registered_names: set[str],
) -> TeamAlias:
    try:
        return resolver.resolve(name, source="martj42")
    except KeyError:
        auto_registered_names.add(name)
        return TeamAlias(canonical_team_id=_canonical_slug(name), canonical_name=name)


def _build_team_maps(
    dataframe: pd.DataFrame,
    resolver: TeamAliasResolver,
) -> tuple[dict[str, TeamAlias], list[str], pd.DataFrame]:
    names = {
        str(name).strip()
        for column in ("home_team", "away_team")
        for name in dataframe[column].dropna()
        if str(name).strip()
    }
    auto_registered_names: set[str] = set()
    aliases = {
        name: _team_alias_for_martj42(name, resolver, auto_registered_names)
        for name in sorted(names)
    }

    team_rows = []
    for source_name, alias in aliases.items():
        team_rows.append(
            {
                "canonical_team_id": alias.canonical_team_id,
                "canonical_name": alias.canonical_name,
                "source_team_name": source_name,
                "source": "martj42",
                "auto_registered": source_name in auto_registered_names,
            }
        )
    team_dimension = pd.DataFrame(team_rows).sort_values(
        ["canonical_team_id", "source_team_name"], kind="mergesort"
    )
    return aliases, sorted(auto_registered_names), team_dimension.reset_index(drop=True)


def _normalize_common_columns(
    dataframe: pd.DataFrame,
    aliases: dict[str, TeamAlias],
) -> pd.DataFrame:
    normalized = dataframe.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    normalized["home_team"] = normalized["home_team"].astype("string").str.strip()
    normalized["away_team"] = normalized["away_team"].astype("string").str.strip()
    normalized["tournament"] = normalized["tournament"].astype("string").str.strip()
    normalized["city"] = normalized["city"].astype("string").str.strip()
    normalized["country"] = normalized["country"].astype("string").str.strip()
    normalized["neutral"] = _coerce_neutral(normalized["neutral"])
    normalized["home_team_id"] = normalized["home_team"].map(
        lambda name: aliases[str(name)].canonical_team_id if pd.notna(name) else pd.NA
    )
    normalized["away_team_id"] = normalized["away_team"].map(
        lambda name: aliases[str(name)].canonical_team_id if pd.notna(name) else pd.NA
    )
    normalized["source"] = "martj42"
    return normalized


def _validate_matches(matches: pd.DataFrame) -> None:
    required_columns = [
        "date",
        "home_team",
        "away_team",
        "home_team_id",
        "away_team_id",
        "home_score",
        "away_score",
    ]
    if matches[required_columns].isna().any().any():
        raise ValueError("matches has missing date/team/score values")
    if matches[["home_team_id", "away_team_id"]].isna().any().any():
        raise ValueError("team ids must be non-null")
    if matches["match_id"].isna().any() or matches["match_id"].duplicated().any():
        raise ValueError("duplicate match_id")


def _validate_team_ids(matches: pd.DataFrame, fixtures: pd.DataFrame) -> None:
    all_rows = pd.concat(
        [matches[["home_team_id", "away_team_id"]], fixtures[["home_team_id", "away_team_id"]]],
        ignore_index=True,
    )
    if all_rows.isna().any().any():
        raise ValueError("team ids must be non-null")


def _validate_recent_years(matches: pd.DataFrame) -> None:
    years = set(matches["date"].dt.year.dropna().astype(int))
    missing_years = {2025, 2026} - years
    if missing_years:
        years_text = ", ".join(str(year) for year in sorted(missing_years))
        raise ValueError(f"matches missing required recent years: {years_text}")


def _attach_summary_attrs(
    matches: pd.DataFrame,
    fixtures: pd.DataFrame,
    *,
    total_rows: int,
    source_rows_after_exact_dedupe: int,
    exact_duplicate_rows_dropped: int,
    double_header_group_count: int,
    auto_registered_team_names: list[str],
    team_dimension: pd.DataFrame,
) -> None:
    attrs = {
        "source": "martj42",
        "total_rows": total_rows,
        "source_rows_after_exact_dedupe": source_rows_after_exact_dedupe,
        "exact_duplicate_rows_dropped": exact_duplicate_rows_dropped,
        "match_rows": len(matches),
        "fixture_rows": len(fixtures),
        "double_header_group_count": double_header_group_count,
        "distinct_canonical_teams": int(team_dimension["canonical_team_id"].nunique()),
        "auto_registered_team_count": len(auto_registered_team_names),
        "auto_registered_team_names": auto_registered_team_names,
    }
    matches.attrs.update(attrs)
    fixtures.attrs.update(attrs)


def split_and_normalize(
    bronze_df: pd.DataFrame,
    silver_dir: str | Path = settings.SILVER_DIR,
    *,
    resolver: TeamAliasResolver | None = None,
    write: bool = True,
    require_recent_years: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split completed results from blank-score fixtures and normalize teams."""

    missing_columns = [column for column in SOURCE_COLUMNS if column not in bronze_df]
    if missing_columns:
        raise ValueError(f"missing source columns: {', '.join(missing_columns)}")

    resolver = resolver or TeamAliasResolver.from_csv()
    source_before_dedupe = bronze_df.loc[:, SOURCE_COLUMNS].copy()
    source_before_dedupe["_source_row_order"] = range(len(source_before_dedupe))
    duplicate_mask = source_before_dedupe.duplicated(subset=SOURCE_COLUMNS, keep="first")
    exact_duplicate_rows_dropped = int(duplicate_mask.sum())
    source = source_before_dedupe.loc[~duplicate_mask].copy()

    aliases, auto_registered_names, team_dimension = _build_team_maps(source, resolver)

    has_home_score = _score_present(source["home_score"])
    has_away_score = _score_present(source["away_score"])
    completed_mask = has_home_score & has_away_score

    matches = _normalize_common_columns(source.loc[completed_mask].copy(), aliases)
    fixtures = _normalize_common_columns(source.loc[~completed_mask].copy(), aliases)

    matches = _coerce_scores(matches, ["home_score", "away_score"])
    fixtures["home_score"] = pd.NA
    fixtures["away_score"] = pd.NA
    fixtures["status"] = "scheduled"

    natural_key_columns = [
        "date",
        "home_team_id",
        "away_team_id",
        "tournament",
        "city",
    ]
    matches = matches.sort_values("_source_row_order", kind="mergesort")
    matches["occurrence_index"] = (
        matches.groupby(natural_key_columns, sort=False, dropna=False).cumcount().astype("int64")
    )
    duplicate_natural_key_rows = matches.duplicated(
        subset=natural_key_columns,
        keep=False,
    )
    double_header_group_count = int(
        matches.loc[duplicate_natural_key_rows, natural_key_columns]
        .drop_duplicates()
        .shape[0]
    )
    matches["match_id"] = matches.apply(_match_id, axis=1)

    matches = matches.loc[:, MATCH_COLUMNS].sort_values(
        [
            "date",
            "home_team_id",
            "away_team_id",
            "tournament",
            "city",
            "occurrence_index",
        ],
        kind="mergesort",
    )
    fixtures = fixtures.loc[:, FIXTURE_COLUMNS].sort_values(
        ["date", "home_team_id", "away_team_id", "tournament", "city"],
        kind="mergesort",
    )

    matches = matches.reset_index(drop=True)
    fixtures = fixtures.reset_index(drop=True)

    _validate_matches(matches)
    _validate_team_ids(matches, fixtures)
    if require_recent_years:
        _validate_recent_years(matches)

    _attach_summary_attrs(
        matches,
        fixtures,
        total_rows=len(source_before_dedupe),
        source_rows_after_exact_dedupe=len(source),
        exact_duplicate_rows_dropped=exact_duplicate_rows_dropped,
        double_header_group_count=double_header_group_count,
        auto_registered_team_names=auto_registered_names,
        team_dimension=team_dimension,
    )

    if write:
        silver_path = Path(silver_dir)
        _write_parquet(matches, silver_path / "martj42_matches.parquet")
        _write_parquet(fixtures, silver_path / "martj42_fixtures.parquet")
        _write_parquet(team_dimension, silver_path / "martj42_teams.parquet")

    return matches, fixtures


def summarize_quality(matches: pd.DataFrame, fixtures: pd.DataFrame) -> dict[str, Any]:
    all_dates = pd.concat([matches["date"], fixtures["date"]], ignore_index=True)
    years = sorted(matches["date"].dt.year.dropna().astype(int).unique().tolist())
    recent_completed_mask = matches["date"].dt.year.isin([2025, 2026])
    return {
        "total_rows": int(matches.attrs.get("total_rows", len(matches) + len(fixtures))),
        "source_rows_after_exact_dedupe": int(
            matches.attrs.get("source_rows_after_exact_dedupe", len(matches) + len(fixtures))
        ),
        "exact_duplicate_rows_dropped": int(
            matches.attrs.get("exact_duplicate_rows_dropped", 0)
        ),
        "matches_count": int(len(matches)),
        "fixtures_count": int(len(fixtures)),
        "date_min": all_dates.min().strftime("%Y-%m-%d") if not all_dates.empty else None,
        "date_max": all_dates.max().strftime("%Y-%m-%d") if not all_dates.empty else None,
        "matches_date_min": matches["date"].min().strftime("%Y-%m-%d")
        if not matches.empty
        else None,
        "matches_date_max": matches["date"].max().strftime("%Y-%m-%d")
        if not matches.empty
        else None,
        "fixtures_date_min": fixtures["date"].min().strftime("%Y-%m-%d")
        if not fixtures.empty
        else None,
        "fixtures_date_max": fixtures["date"].max().strftime("%Y-%m-%d")
        if not fixtures.empty
        else None,
        "double_header_group_count": int(
            matches.attrs.get("double_header_group_count", 0)
        ),
        "distinct_canonical_teams": int(
            matches.attrs.get(
                "distinct_canonical_teams",
                pd.concat(
                    [
                        matches["home_team_id"],
                        matches["away_team_id"],
                        fixtures["home_team_id"],
                        fixtures["away_team_id"],
                    ]
                ).nunique(),
            )
        ),
        "auto_registered_team_count": int(
            matches.attrs.get("auto_registered_team_count", 0)
        ),
        "matches_contains_2025": 2025 in years,
        "matches_contains_2026": 2026 in years,
        "completed_2025_2026_count": int(recent_completed_mask.sum()),
        "match_id_unique": bool(matches["match_id"].is_unique),
    }


def write_quality_report(
    summary: dict[str, Any],
    report_dir: str | Path = settings.REPORTS_DIR / "data_quality",
) -> Path:
    """Write the committed aggregate DQ summary for martj42 I3."""

    report_path = Path(report_dir) / "martj42_international_results_i3.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# I3 martj42 international results data quality",
        "",
        f"- Source: `{summary['source_url']}`",
        f"- Ingest UTC: `{summary['ingest_utc']}`",
        f"- Raw SHA-256: `{summary['sha256']}`",
        f"- Total source rows: {summary['total_rows']:,}",
        f"- Exact-identical duplicate rows dropped: {summary['exact_duplicate_rows_dropped']:,}",
        f"- Rows after exact dedupe: {summary['source_rows_after_exact_dedupe']:,}",
        f"- Completed matches after dedupe: {summary['matches_count']:,}",
        f"- Blank-score fixtures: {summary['fixtures_count']:,}",
        f"- Completed match date range: {summary['matches_date_min']} to {summary['matches_date_max']}",
        f"- Fixture date range: {summary['fixtures_date_min']} to {summary['fixtures_date_max']}",
        f"- All-row date range after dedupe: {summary['date_min']} to {summary['date_max']}",
        f"- Multi-match same-day natural-key groups: {summary['double_header_group_count']:,}",
        f"- Distinct canonical teams: {summary['distinct_canonical_teams']:,}",
        f"- Auto-registered martj42 teams: {summary['auto_registered_team_count']:,}",
        f"- Completed matches in 2025-2026: {summary['completed_2025_2026_count']:,}",
        f"- Match ID unique across silver matches: {summary['match_id_unique']}",
        f"- Contains 2025 completed matches: {summary['matches_contains_2025']}",
        f"- Contains 2026 completed matches: {summary['matches_contains_2026']}",
        "",
        "Natural-key duplicates are not rejected. They are retained as legitimate double-headers",
        "when the score or another source field differs, with `occurrence_index` assigned by",
        "original source row order and `match_id` asserted unique.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def ingest(
    url: str = MARTJ42_RESULTS_URL,
    *,
    raw_dir: str | Path = settings.RAW_DIR,
    bronze_dir: str | Path = settings.BRONZE_DIR,
    silver_dir: str | Path = settings.SILVER_DIR,
) -> tuple[RawSnapshot, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Run the live martj42 raw -> bronze -> silver ingestion."""

    snapshot = download_raw(url=url, raw_dir=raw_dir)
    bronze = parse_bronze(snapshot.raw_path, bronze_dir=bronze_dir, write=True)
    matches, fixtures = split_and_normalize(
        bronze,
        silver_dir=silver_dir,
        write=True,
        require_recent_years=True,
    )
    summary = summarize_quality(matches, fixtures)
    summary.update(
        {
            "source_url": snapshot.source_url,
            "ingest_utc": snapshot.ingest_utc,
            "sha256": snapshot.sha256,
            "raw_path": snapshot.raw_path,
            "manifest_path": snapshot.manifest_path,
        }
    )
    report_path = write_quality_report(summary)
    summary["report_path"] = str(report_path)
    return snapshot, matches, fixtures, summary


if __name__ == "__main__":
    _, _, _, ingestion_summary = ingest()
    print(json.dumps(ingestion_summary, indent=2, sort_keys=True))
