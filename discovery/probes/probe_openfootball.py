from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from _common import ROOT, http_get, now_utc_iso, save_sample


SOURCE_ID = "openfootball"
CONTENTS_API_ROOT = "https://api.github.com/repos/openfootball/worldcup/contents"
RAW_ROOT = "https://raw.githubusercontent.com/openfootball/worldcup/master"
MARTJ42_RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)
EXCERPT_PATH = ROOT / "discovery" / "findings" / "d2-openfootball-fixture-excerpt.txt"

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
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class Fixture:
    file_path: str
    section: str
    match_date: str
    home_team: str
    away_team: str
    venue: str
    match_number: int | None = None


def github_contents(path: str = "") -> list[dict[str, Any]]:
    suffix = f"/{path}" if path else ""
    response = http_get(f"{CONTENTS_API_ROOT}{suffix}")
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Expected contents list for {path!r}, got {type(payload)!r}")
    return payload


def find_2026_fixture_files() -> tuple[str, list[dict[str, Any]]]:
    root_items = github_contents()
    candidate_dirs = [
        item
        for item in root_items
        if item.get("type") == "dir" and "2026" in str(item.get("name", ""))
    ]
    if not candidate_dirs:
        raise RuntimeError("No 2026 directory found through GitHub contents API")

    candidate_dirs.sort(key=lambda item: str(item["path"]))
    selected_dir = str(candidate_dirs[0]["path"])
    dir_items = github_contents(selected_dir)
    fixture_files = [
        item
        for item in dir_items
        if item.get("type") == "file"
        and str(item.get("name", "")).lower() in {"cup.txt", "cup_finals.txt"}
    ]
    fixture_files.sort(key=lambda item: str(item["path"]))
    if not fixture_files:
        raise RuntimeError(f"No cup fixture text files found under {selected_dir}")
    return selected_dir, fixture_files


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def parse_group_declarations(text: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = re.match(r"^Group\s+([A-L])\s+\|\s+(.+)$", line.strip())
        if not match:
            continue
        group_id, team_blob = match.groups()
        teams = [normalize_spaces(team) for team in re.split(r"\s{2,}", team_blob)]
        groups[group_id] = [team for team in teams if team]
    return groups


def parse_date_line(line: str) -> date | None:
    match = re.match(
        r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]+)\s+(\d{1,2})\s*$",
        line.strip(),
    )
    if not match:
        return None
    _, month_name, day = match.groups()
    month = MONTHS.get(month_name.lower())
    if not month:
        return None
    return date(2026, month, int(day))


def parse_fixture_line(line: str) -> tuple[int | None, str, str, str] | None:
    match = re.match(
        r"^\s*(?:\((?P<num>\d+)\)\s*)?"
        r"\d{1,2}:\d{2}\s+UTC[+-]\d{1,2}\s+"
        r"(?P<body>.*?)\s+@\s+(?P<venue>.+?)\s*$",
        line,
    )
    if not match:
        return None

    body = normalize_spaces(match.group("body"))
    split_match = re.match(
        r"^(?P<home>.+?)\s+"
        r"(?P<marker>v|\d+\s*-\s*\d+(?:\s+\([^)]+\))?)\s+"
        r"(?P<away>.+)$",
        body,
    )
    if not split_match:
        raise RuntimeError(f"Could not split fixture teams from line: {line}")

    match_number = int(match.group("num")) if match.group("num") else None
    return (
        match_number,
        normalize_spaces(split_match.group("home")),
        normalize_spaces(split_match.group("away")),
        normalize_spaces(match.group("venue")),
    )


def parse_fixtures(file_path: str, text: str) -> list[Fixture]:
    fixtures: list[Fixture] = []
    current_section = ""
    current_date: date | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        section_match = re.match(r"^▪\s+(.+)$", stripped)
        if section_match:
            current_section = normalize_spaces(section_match.group(1))
            continue
        parsed_date = parse_date_line(stripped)
        if parsed_date:
            current_date = parsed_date
            continue
        fixture_parts = parse_fixture_line(raw_line)
        if not fixture_parts:
            continue
        if current_date is None:
            raise RuntimeError(f"Fixture appears before a date in {file_path}: {raw_line}")
        match_number, home_team, away_team, venue = fixture_parts
        fixtures.append(
            Fixture(
                file_path=file_path,
                section=current_section,
                match_date=current_date.isoformat(),
                home_team=home_team,
                away_team=away_team,
                venue=venue,
                match_number=match_number,
            )
        )

    return fixtures


def fetch_and_save_fixture_files(files: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    texts: dict[str, str] = {}
    sample_meta: dict[str, str] = {}
    for item in files:
        path = str(item["path"])
        download_url = item.get("download_url") or f"{RAW_ROOT}/{path}"
        response = http_get(str(download_url))
        filename = Path(path).name
        sample = save_sample(SOURCE_ID, filename, response.content)
        texts[path] = response.text
        sample_meta[path] = sample["path"]
    return texts, sample_meta


def load_martj42_team_names() -> tuple[set[str], str]:
    local_path = ROOT / "discovery" / "samples" / "martj42" / "results.csv"
    if local_path.exists():
        csv_text = local_path.read_text(encoding="utf-8")
        source = local_path.relative_to(ROOT).as_posix()
    else:
        response = http_get(MARTJ42_RESULTS_URL)
        csv_text = response.text
        source = MARTJ42_RESULTS_URL

    reader = csv.DictReader(csv_text.splitlines())
    teams: set[str] = set()
    for row in reader:
        for column in ("home_team", "away_team"):
            value = normalize_spaces(row.get(column, ""))
            if value:
                teams.add(value)
    return teams, source


def write_excerpt(texts: dict[str, str], fixtures: list[Fixture]) -> None:
    EXCERPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "openfootball World Cup 2026 fixture excerpt",
        "",
        "Discovered fixture files:",
        *[f"- {path}" for path in sorted(texts)],
        "",
        "First 20 non-comment fixture/group lines from cup.txt:",
    ]

    cup_lines = []
    for line in texts.get("2026--usa/cup.txt", "").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            cup_lines.append(line.rstrip())
        if len(cup_lines) >= 20:
            break
    lines.extend(cup_lines)

    lines.extend(["", "First 8 parsed knockout fixtures:"])
    knockout = [fixture for fixture in fixtures if fixture.match_number is not None][:8]
    for fixture in knockout:
        lines.append(
            f"- ({fixture.match_number}) {fixture.match_date} "
            f"{fixture.home_team} v {fixture.away_team} @ {fixture.venue}"
        )

    EXCERPT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    discovered_dir, fixture_files = find_2026_fixture_files()
    fixture_paths = [str(item["path"]) for item in fixture_files]
    texts, sample_paths = fetch_and_save_fixture_files(fixture_files)

    groups = parse_group_declarations(texts.get(f"{discovered_dir}/cup.txt", ""))
    group_teams = sorted({team for teams in groups.values() for team in teams})
    fixtures = [
        fixture
        for path, text in texts.items()
        for fixture in parse_fixtures(path, text)
    ]
    group_fixtures = [fixture for fixture in fixtures if fixture.section.startswith("Group ")]
    knockout_fixtures = [fixture for fixture in fixtures if fixture.match_number is not None]
    knockout_rounds: dict[str, int] = {}
    for fixture in knockout_fixtures:
        knockout_rounds[fixture.section] = knockout_rounds.get(fixture.section, 0) + 1

    martj42_teams, martj42_source = load_martj42_team_names()
    unmatched_teams = sorted(team for team in group_teams if team not in martj42_teams)

    write_excerpt(texts, fixtures)

    dates = sorted(fixture.match_date for fixture in fixtures)
    venues = sorted({fixture.venue for fixture in fixtures})
    summary = {
        "source_id": SOURCE_ID,
        "generated_at": now_utc_iso(),
        "contents_api_root": f"{CONTENTS_API_ROOT}/",
        "discovered_2026_directory": discovered_dir,
        "discovered_fixture_paths": fixture_paths,
        "sample_saved_at": sample_paths,
        "excerpt_path": EXCERPT_PATH.relative_to(ROOT).as_posix(),
        "fixtures": {
            "total_parsed": len(fixtures),
            "group_stage_parsed": len(group_fixtures),
            "knockout_parsed": len(knockout_fixtures),
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "distinct_venue_city_labels": len(venues),
            "sample_venue_city_labels": venues[:8],
        },
        "groups": {
            "group_count": len(groups),
            "all_12_groups_present": set(groups) == set("ABCDEFGHIJKL"),
            "team_count": len(group_teams),
            "all_48_teams_present": len(group_teams) == 48,
            "teams": group_teams,
        },
        "knockout": {
            "structure_present": bool(knockout_fixtures),
            "round_counts": knockout_rounds,
            "match_numbers_min": min(
                (fixture.match_number for fixture in knockout_fixtures if fixture.match_number),
                default=None,
            ),
            "match_numbers_max": max(
                (fixture.match_number for fixture in knockout_fixtures if fixture.match_number),
                default=None,
            ),
        },
        "martj42_crosscheck": {
            "source": martj42_source,
            "martj42_distinct_team_names": len(martj42_teams),
            "unmatched_fixture_team_names": unmatched_teams,
            "unmatched_count": len(unmatched_teams),
        },
    }

    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
