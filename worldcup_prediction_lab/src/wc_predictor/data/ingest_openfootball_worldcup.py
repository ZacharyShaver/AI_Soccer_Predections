"""Ingest openfootball World Cup 2026 fixtures into silver datasets."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.data.team_aliases import TeamAliasResolver


CUP_URL = "https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup.txt"
CUP_FINALS_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup_finals.txt"
)

FIXTURE_COLUMNS = [
    "fixture_id",
    "stage",
    "group",
    "home_team_id",
    "away_team_id",
    "home_slot",
    "away_slot",
    "match_date",
    "venue",
    "match_number",
]

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
}

STAGE_MAP = {
    "round of 32": "round_of_32",
    "round of 16": "round_of_16",
    "quarter-final": "quarter_final",
    "quarter final": "quarter_final",
    "semi-final": "semi_final",
    "semi final": "semi_final",
    "match for third place": "third_place",
    "final": "final",
}


@dataclass(frozen=True)
class RawFileSnapshot:
    name: str
    source_url: str
    sha256: str
    byte_count: int
    line_count: int
    raw_path: str


@dataclass(frozen=True)
class RawSnapshot:
    source_id: str
    ingest_utc: str
    files: list[RawFileSnapshot]
    manifest_path: str


def _utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _read_text_input(text_or_path: bytes | str | Path) -> str:
    if isinstance(text_or_path, bytes):
        return text_or_path.decode("utf-8")
    if isinstance(text_or_path, Path):
        return text_or_path.read_text(encoding="utf-8")

    possible_path = Path(text_or_path)
    if "\n" not in text_or_path and possible_path.exists():
        return possible_path.read_text(encoding="utf-8")
    return text_or_path


def _write_parquet(dataframe: pd.DataFrame, path: Path) -> None:
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        connection.register("df_to_write", dataframe)
        connection.execute(f"COPY df_to_write TO '{escaped_path}' (FORMAT PARQUET)")


def _read_parquet(path: Path) -> pd.DataFrame:
    import duckdb

    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(
            f"SELECT * FROM read_parquet('{escaped_path}')"
        ).fetchdf()


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def parse_group_declaration(line: str) -> tuple[str, list[str]]:
    """Parse `Group A | Mexico  South Africa ...` declarations."""

    match = re.match(r"^Group\s+([A-L])\s*\|\s*(?P<teams>.+)$", line.strip())
    if match is None:
        raise ValueError(f"not a group declaration: {line!r}")

    teams = [
        _normalize_spaces(team)
        for team in re.split(r"\s{2,}", match.group("teams").strip())
        if team.strip()
    ]
    if len(teams) != 4:
        raise ValueError(f"group {match.group(1)} must declare four teams")
    return match.group(1), teams


def _parse_date_line(line: str) -> pd.Timestamp | None:
    match = re.match(
        r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]+)\s+(\d{1,2})\s*$",
        line.strip(),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None

    month = MONTHS.get(match.group(1).casefold())
    if month is None:
        return None
    return pd.Timestamp(year=2026, month=month, day=int(match.group(2)))


def _fixture_id(row: dict[str, Any]) -> str:
    match_date = row["match_date"]
    if isinstance(match_date, pd.Timestamp):
        date_text = match_date.strftime("%Y-%m-%d")
    else:
        date_text = str(match_date)

    def part(name: str) -> str:
        value = row.get(name)
        if value is None or pd.isna(value):
            return ""
        return str(value)

    home_ref = part("home_team_id") or part("home_slot")
    away_ref = part("away_team_id") or part("away_slot")
    parts = [
        part("stage"),
        part("group"),
        part("match_number"),
        date_text,
        home_ref,
        away_ref,
        part("venue"),
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _resolve_group_teams(
    group_teams: dict[str, list[str]],
    resolver: TeamAliasResolver,
    canonical_team_ids: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    resolved: dict[str, dict[str, str]] = {}
    for group, teams in sorted(group_teams.items()):
        resolved[group] = {}
        for team in teams:
            alias = resolver.resolve(team, source="openfootball")
            if (
                canonical_team_ids is not None
                and alias.canonical_team_id not in canonical_team_ids
            ):
                raise KeyError(
                    f"openfootball team {team!r} resolved to {alias.canonical_team_id!r}, "
                    "which is absent from martj42 canonical teams"
                )
            resolved[group][team] = alias.canonical_team_id
    return resolved


def _parse_group_fixture_body(body: str, teams: list[str]) -> tuple[str, str]:
    normalized = _normalize_spaces(body)
    teams_by_length = sorted(teams, key=len, reverse=True)
    for home in teams_by_length:
        if not (normalized == home or normalized.startswith(f"{home} ")):
            continue
        for away in teams_by_length:
            if home == away:
                continue
            if normalized.endswith(f" {away}") or normalized == away:
                return home, away
    raise ValueError(f"could not parse group fixture teams from: {body!r}")


def _build_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(rows, columns=FIXTURE_COLUMNS)
    if dataframe.empty:
        return dataframe

    dataframe["match_date"] = pd.to_datetime(dataframe["match_date"], errors="coerce")
    dataframe["match_number"] = pd.array(dataframe["match_number"], dtype="Int64")
    dataframe = dataframe.sort_values(
        ["match_date", "match_number", "stage", "group", "fixture_id"],
        kind="mergesort",
        na_position="last",
    )
    return dataframe.reset_index(drop=True)


def parse_cup_text(
    cup_text_or_path: bytes | str | Path,
    silver_dir: str | Path = settings.SILVER_DIR,
    *,
    resolver: TeamAliasResolver | None = None,
    canonical_team_ids: set[str] | None = None,
    write: bool = True,
) -> pd.DataFrame:
    """Parse openfootball `cup.txt` group declarations and group fixtures."""

    text = _read_text_input(cup_text_or_path)
    resolver = resolver or TeamAliasResolver.from_csv()

    group_teams: dict[str, list[str]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^Group\s+[A-L]\s*\|", stripped):
            group, teams = parse_group_declaration(stripped)
            group_teams[group] = teams

    resolved_teams = _resolve_group_teams(group_teams, resolver, canonical_team_ids)

    rows: list[dict[str, Any]] = []
    current_group: str | None = None
    current_date: pd.Timestamp | None = None
    fixture_pattern = re.compile(
        r"^\s*\d{1,2}:\d{2}\s+UTC[+-]\d+\s+(?P<body>.+?)\s+@\s+(?P<venue>.+?)\s*$"
    )

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("="):
            continue

        if "|" not in stripped:
            group_match = re.match(r"^[^\w]*(?:Group)\s+([A-L])\s*$", stripped)
            if group_match is not None:
                current_group = group_match.group(1)
                current_date = None
                continue

        parsed_date = _parse_date_line(stripped)
        if parsed_date is not None:
            current_date = parsed_date
            continue

        match = fixture_pattern.match(line)
        if match is None or current_group is None or current_date is None:
            continue

        teams = group_teams[current_group]
        home_team, away_team = _parse_group_fixture_body(match.group("body"), teams)
        row = {
            "stage": "group",
            "group": current_group,
            "home_team_id": resolved_teams[current_group][home_team],
            "away_team_id": resolved_teams[current_group][away_team],
            "home_slot": pd.NA,
            "away_slot": pd.NA,
            "match_date": current_date,
            "venue": _normalize_spaces(match.group("venue")),
            "match_number": pd.NA,
        }
        row["fixture_id"] = _fixture_id(row)
        rows.append(row)

    fixtures = _build_dataframe(rows)
    if write:
        _write_parquet(fixtures, Path(silver_dir) / "openfootball_group_fixtures.parquet")
    return fixtures


def parse_cup_finals_text(
    cup_finals_text_or_path: bytes | str | Path,
    silver_dir: str | Path = settings.SILVER_DIR,
    *,
    write: bool = True,
) -> pd.DataFrame:
    """Parse openfootball `cup_finals.txt` knockout fixtures."""

    text = _read_text_input(cup_finals_text_or_path)
    rows: list[dict[str, Any]] = []
    current_stage: str | None = None
    current_date: pd.Timestamp | None = None
    fixture_pattern = re.compile(
        r"^\s*\((?P<number>\d+)\)\s+\d{1,2}:\d{2}\s+UTC[+-]\d+\s+"
        r"(?P<home_slot>\S+)\s+v\s+(?P<away_slot>\S+)\s+@\s+(?P<venue>.+?)\s*$"
    )

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("="):
            continue

        stage_candidate = re.sub(r"^[^\w]+", "", stripped).strip().casefold()
        if stage_candidate in STAGE_MAP:
            current_stage = STAGE_MAP[stage_candidate]
            current_date = None
            continue

        parsed_date = _parse_date_line(stripped)
        if parsed_date is not None:
            current_date = parsed_date
            continue

        match = fixture_pattern.match(line)
        if match is None or current_stage is None or current_date is None:
            continue

        row = {
            "stage": current_stage,
            "group": pd.NA,
            "home_team_id": pd.NA,
            "away_team_id": pd.NA,
            "home_slot": match.group("home_slot"),
            "away_slot": match.group("away_slot"),
            "match_date": current_date,
            "venue": _normalize_spaces(match.group("venue")),
            "match_number": int(match.group("number")),
        }
        row["fixture_id"] = _fixture_id(row)
        rows.append(row)

    fixtures = _build_dataframe(rows)
    if write:
        _write_parquet(
            fixtures,
            Path(silver_dir) / "openfootball_knockout_fixtures.parquet",
        )
    return fixtures


def _group_declarations(cup_text_or_path: bytes | str | Path) -> dict[str, list[str]]:
    text = _read_text_input(cup_text_or_path)
    groups: dict[str, list[str]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^Group\s+[A-L]\s*\|", stripped):
            group, teams = parse_group_declaration(stripped)
            groups[group] = teams
    return groups


def _validate_expected_counts(
    fixtures: pd.DataFrame,
    group_teams: dict[str, list[str]],
) -> None:
    group_fixtures = fixtures[fixtures["stage"] == "group"]
    knockout_fixtures = fixtures[fixtures["stage"] != "group"]

    if len(group_teams) != 12:
        raise ValueError(f"expected 12 groups, found {len(group_teams)}")
    if len({team for teams in group_teams.values() for team in teams}) != 48:
        raise ValueError("expected 48 distinct group-stage teams")
    if len(group_fixtures) != 72:
        raise ValueError(f"expected 72 group fixtures, found {len(group_fixtures)}")
    if len(knockout_fixtures) != 32:
        raise ValueError(f"expected 32 knockout fixtures, found {len(knockout_fixtures)}")
    if len(fixtures) != 104:
        raise ValueError(f"expected 104 fixtures, found {len(fixtures)}")

    date_min = fixtures["match_date"].min().strftime("%Y-%m-%d")
    date_max = fixtures["match_date"].max().strftime("%Y-%m-%d")
    if (date_min, date_max) != ("2026-06-11", "2026-07-19"):
        raise ValueError(f"unexpected fixture date range: {date_min} to {date_max}")

    if group_fixtures[["home_team_id", "away_team_id"]].isna().any().any():
        raise ValueError("group fixtures must have resolved team ids")
    if knockout_fixtures[["home_team_id", "away_team_id"]].notna().any().any():
        raise ValueError("knockout fixtures must keep team ids null")
    if knockout_fixtures[["home_slot", "away_slot"]].isna().any().any():
        raise ValueError("knockout fixtures must keep placeholder slots")
    if fixtures["fixture_id"].duplicated().any():
        raise ValueError("duplicate fixture_id")


def _load_martj42_canonical_team_ids(
    silver_dir: str | Path = settings.SILVER_DIR,
) -> set[str] | None:
    teams_path = Path(silver_dir) / "martj42_teams.parquet"
    if not teams_path.exists():
        return None
    teams = _read_parquet(teams_path)
    return set(teams["canonical_team_id"].astype(str))


def combine_and_validate(
    cup_text_or_path: bytes | str | Path,
    cup_finals_text_or_path: bytes | str | Path,
    silver_dir: str | Path = settings.SILVER_DIR,
    *,
    resolver: TeamAliasResolver | None = None,
    canonical_team_ids: set[str] | None = None,
    write: bool = True,
    require_expected_counts: bool = True,
) -> pd.DataFrame:
    resolver = resolver or TeamAliasResolver.from_csv()
    if canonical_team_ids is None:
        canonical_team_ids = _load_martj42_canonical_team_ids(silver_dir)

    groups = _group_declarations(cup_text_or_path)
    group_fixtures = parse_cup_text(
        cup_text_or_path,
        silver_dir=silver_dir,
        resolver=resolver,
        canonical_team_ids=canonical_team_ids,
        write=False,
    )
    knockout_fixtures = parse_cup_finals_text(
        cup_finals_text_or_path,
        silver_dir=silver_dir,
        write=False,
    )
    fixtures = pd.concat([group_fixtures, knockout_fixtures], ignore_index=True)
    fixtures = _build_dataframe(fixtures.to_dict("records"))

    if require_expected_counts:
        _validate_expected_counts(fixtures, groups)

    if write:
        silver_path = Path(silver_dir)
        _write_parquet(fixtures, silver_path / "openfootball_worldcup_2026_fixtures.parquet")
        manifest = summarize_quality(fixtures, groups)
        manifest_path = silver_path / "openfootball_worldcup_2026_fixtures.manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    fixtures.attrs["group_count"] = len(groups)
    fixtures.attrs["group_stage_team_count"] = len(
        {team for teams in groups.values() for team in teams}
    )
    return fixtures


def download_raw(
    cup_url: str = CUP_URL,
    cup_finals_url: str = CUP_FINALS_URL,
    raw_dir: str | Path = settings.RAW_DIR,
) -> RawSnapshot:
    """Download both openfootball fixture files and persist hashes plus manifest."""

    import httpx

    ingest_utc = _utc_iso()
    slug = _utc_slug()
    targets = [("cup", cup_url), ("cup_finals", cup_finals_url)]
    files: list[RawFileSnapshot] = []
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for name, url in targets:
            response = client.get(url)
            response.raise_for_status()
            content = response.content
            digest = hashlib.sha256(content).hexdigest()
            file_path = (
                raw_path
                / f"openfootball_worldcup_2026_{name}_{slug}_{digest[:12]}.txt"
            )
            file_path.write_bytes(content)
            files.append(
                RawFileSnapshot(
                    name=name,
                    source_url=url,
                    sha256=digest,
                    byte_count=len(content),
                    line_count=len(content.decode("utf-8").splitlines()),
                    raw_path=str(file_path),
                )
            )

    manifest_path = raw_path / f"openfootball_worldcup_2026_{slug}.manifest.json"
    snapshot = RawSnapshot(
        source_id="openfootball_worldcup_2026",
        ingest_utc=ingest_utc,
        files=files,
        manifest_path=str(manifest_path),
    )
    manifest_path.write_text(
        json.dumps(asdict(snapshot), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


def reconcile_martj42_fixtures(
    openfootball_fixtures: pd.DataFrame,
    silver_dir: str | Path = settings.SILVER_DIR,
) -> dict[str, Any]:
    martj42_path = Path(silver_dir) / "martj42_fixtures.parquet"
    if not martj42_path.exists():
        return {
            "martj42_fixture_rows_checked": 0,
            "martj42_fixture_disagreement_count": 0,
            "martj42_fixture_disagreements": [],
            "martj42_reconciliation_note": "martj42_fixtures.parquet not found",
        }

    martj42 = _read_parquet(martj42_path)
    martj42["date"] = pd.to_datetime(martj42["date"], errors="coerce")
    martj42 = martj42[martj42["date"].dt.year == 2026].copy()

    open_group = openfootball_fixtures[openfootball_fixtures["stage"] == "group"].copy()
    disagreements: list[dict[str, Any]] = []
    open_by_pair: dict[tuple[str, str], list[pd.Series]] = {}
    open_by_reverse_pair: dict[tuple[str, str], list[pd.Series]] = {}
    for row in open_group.itertuples(index=False):
        key = (str(row.home_team_id), str(row.away_team_id))
        open_by_pair.setdefault(key, []).append(row)
        reverse_key = (str(row.away_team_id), str(row.home_team_id))
        open_by_reverse_pair.setdefault(reverse_key, []).append(row)

    for row in martj42.itertuples(index=False):
        key = (str(row.home_team_id), str(row.away_team_id))
        candidates = open_by_pair.get(key, [])
        if not candidates:
            reverse_candidates = open_by_reverse_pair.get(key, [])
            if reverse_candidates:
                disagreements.append(
                    {
                        "type": "home_away_order_disagreement",
                        "martj42_date": row.date.strftime("%Y-%m-%d"),
                        "openfootball_dates": sorted(
                            candidate.match_date.strftime("%Y-%m-%d")
                            for candidate in reverse_candidates
                        ),
                        "martj42_home_team_id": row.home_team_id,
                        "martj42_away_team_id": row.away_team_id,
                        "openfootball_home_team_id": reverse_candidates[0].home_team_id,
                        "openfootball_away_team_id": reverse_candidates[0].away_team_id,
                    }
                )
                continue
            disagreements.append(
                {
                    "type": "pairing_missing_in_openfootball",
                    "martj42_date": row.date.strftime("%Y-%m-%d"),
                    "home_team_id": row.home_team_id,
                    "away_team_id": row.away_team_id,
                }
            )
            continue

        mart_date = row.date.strftime("%Y-%m-%d")
        open_dates = sorted(
            candidate.match_date.strftime("%Y-%m-%d") for candidate in candidates
        )
        if mart_date not in open_dates:
            disagreements.append(
                {
                    "type": "date_mismatch",
                    "martj42_date": mart_date,
                    "openfootball_dates": open_dates,
                    "home_team_id": row.home_team_id,
                    "away_team_id": row.away_team_id,
                }
            )

    return {
        "martj42_fixture_rows_checked": int(len(martj42)),
        "martj42_fixture_disagreement_count": len(disagreements),
        "martj42_fixture_disagreements": disagreements,
        "martj42_reconciliation_note": (
            "openfootball is the fixture source of truth; martj42 blank-score "
            "fixtures are cross-validation only"
        ),
    }


def summarize_quality(
    fixtures: pd.DataFrame,
    group_teams: dict[str, list[str]],
    reconciliation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    group_fixtures = fixtures[fixtures["stage"] == "group"]
    knockout_fixtures = fixtures[fixtures["stage"] != "group"]
    stage_counts = {
        str(stage): int(count)
        for stage, count in fixtures["stage"].value_counts().sort_index().items()
    }
    summary = {
        "group_count": int(len(group_teams)),
        "group_stage_team_count": int(
            len({team for teams in group_teams.values() for team in teams})
        ),
        "group_fixture_count": int(len(group_fixtures)),
        "knockout_fixture_count": int(len(knockout_fixtures)),
        "total_fixture_count": int(len(fixtures)),
        "stage_counts": stage_counts,
        "date_min": fixtures["match_date"].min().strftime("%Y-%m-%d"),
        "date_max": fixtures["match_date"].max().strftime("%Y-%m-%d"),
        "resolved_group_team_id_count": int(
            pd.concat(
                [group_fixtures["home_team_id"], group_fixtures["away_team_id"]],
                ignore_index=True,
            ).nunique()
        ),
        "fixture_id_unique": bool(fixtures["fixture_id"].is_unique),
    }
    if reconciliation:
        summary.update(reconciliation)
    return summary


def write_quality_report(
    summary: dict[str, Any],
    report_dir: str | Path = settings.REPORTS_DIR / "data_quality",
) -> Path:
    report_path = Path(report_dir) / "openfootball_worldcup_2026_i4.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    disagreements = summary.get("martj42_fixture_disagreements", [])
    lines = [
        "# I4 openfootball World Cup 2026 fixture data quality",
        "",
        f"- Source files: `{CUP_URL}` and `{CUP_FINALS_URL}`",
        f"- Ingest UTC: `{summary['ingest_utc']}`",
        f"- Raw cup SHA-256: `{summary['raw_sha256']['cup']}`",
        f"- Raw cup_finals SHA-256: `{summary['raw_sha256']['cup_finals']}`",
        f"- Groups parsed: {summary['group_count']}",
        f"- Distinct group-stage teams resolved: {summary['group_stage_team_count']}",
        f"- Resolved canonical group team ids: {summary['resolved_group_team_id_count']}",
        f"- Group fixtures: {summary['group_fixture_count']}",
        f"- Knockout fixtures: {summary['knockout_fixture_count']}",
        f"- Total fixtures: {summary['total_fixture_count']}",
        f"- Date range: {summary['date_min']} to {summary['date_max']}",
        f"- Fixture ID unique: {summary['fixture_id_unique']}",
        f"- Martj42 blank-score fixture rows checked: {summary['martj42_fixture_rows_checked']}",
        f"- Martj42 reconciliation disagreements: {summary['martj42_fixture_disagreement_count']}",
        "",
        "Stage counts:",
    ]
    for stage, count in sorted(summary["stage_counts"].items()):
        lines.append(f"- {stage}: {count}")

    lines.extend(
        [
            "",
            "Openfootball (D2) is the 2026 fixture source of truth. Martj42 blank-score",
            "fixture rows are used only as a cross-validation input and do not override",
            "stage, group, venue, or bracket slots from openfootball.",
            "",
            "Martj42 reconciliation details:",
        ]
    )
    if disagreements:
        for disagreement in disagreements:
            lines.append(f"- `{json.dumps(disagreement, sort_keys=True)}`")
    else:
        lines.append("- No date or pairing disagreements found.")

    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def ingest(
    cup_url: str = CUP_URL,
    cup_finals_url: str = CUP_FINALS_URL,
    *,
    raw_dir: str | Path = settings.RAW_DIR,
    silver_dir: str | Path = settings.SILVER_DIR,
) -> tuple[RawSnapshot, pd.DataFrame, dict[str, Any]]:
    snapshot = download_raw(cup_url=cup_url, cup_finals_url=cup_finals_url, raw_dir=raw_dir)
    files_by_name = {file.name: file for file in snapshot.files}

    fixtures = combine_and_validate(
        files_by_name["cup"].raw_path,
        files_by_name["cup_finals"].raw_path,
        silver_dir=silver_dir,
        write=True,
        require_expected_counts=True,
    )
    groups = _group_declarations(files_by_name["cup"].raw_path)
    reconciliation = reconcile_martj42_fixtures(fixtures, silver_dir=silver_dir)
    summary = summarize_quality(fixtures, groups, reconciliation)
    summary.update(
        {
            "ingest_utc": snapshot.ingest_utc,
            "raw_manifest_path": snapshot.manifest_path,
            "raw_paths": {name: file.raw_path for name, file in files_by_name.items()},
            "raw_sha256": {name: file.sha256 for name, file in files_by_name.items()},
        }
    )
    report_path = write_quality_report(summary)
    summary["report_path"] = str(report_path)
    return snapshot, fixtures, summary


if __name__ == "__main__":
    _, _, ingestion_summary = ingest()
    print(json.dumps(ingestion_summary, indent=2, sort_keys=True))
