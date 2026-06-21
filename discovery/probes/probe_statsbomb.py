from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

from _common import ROOT, USER_AGENT, now_utc_iso, save_sample


SOURCE_ID = "statsbomb"
RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master"
FINDINGS_DIR = ROOT / "discovery" / "findings"
FINDINGS_PATH = FINDINGS_DIR / "d7-statsbomb.md"
EXCERPT_PATH = FINDINGS_DIR / "d7-statsbomb-excerpt.json"

COMPETITIONS_URL = f"{RAW_BASE}/data/competitions.json"
README_URL = f"{RAW_BASE}/README.md"
USER_AGREEMENT_URL = f"{RAW_BASE}/LICENSE.pdf"


def parse_json_response(response: httpx.Response, label: str) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if (
        "application/json" not in content_type
        and "text/plain" not in content_type
        and "application/octet-stream" not in content_type
    ):
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(
            f"GET {label} returned HTTP 200 but non-JSON content-type "
            f"{content_type!r}: {preview}"
        )
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"GET {label} returned invalid JSON: {preview}") from exc


def require_list_of_dicts(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(
            f"GET {label} returned JSON {type(payload).__name__}, expected list"
        )
    bad_item = next((item for item in payload if not isinstance(item, dict)), None)
    if bad_item is not None:
        raise RuntimeError(f"GET {label} returned list with non-object item")
    return payload


def http_get(client: httpx.Client, url: str) -> httpx.Response:
    response = client.get(url)
    if response.status_code != 200:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"GET {url} returned HTTP {response.status_code}: {preview}")
    return response


def fetch_json_list(client: httpx.Client, url: str, label: str) -> tuple[list[dict[str, Any]], dict[str, Any], bytes]:
    response = http_get(client, url)
    payload = require_list_of_dicts(parse_json_response(response, label), label)
    facts = {
        "url": url,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
        "record_count": len(payload),
    }
    return payload, facts, response.content


def competition_key(row: dict[str, Any]) -> tuple[int, int]:
    return int(row["competition_id"]), int(row["season_id"])


def compact_competition(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "competition_id": row.get("competition_id"),
        "season_id": row.get("season_id"),
        "competition_name": row.get("competition_name"),
        "season_name": row.get("season_name"),
        "country_name": row.get("country_name"),
        "match_available": row.get("match_available"),
        "match_updated": row.get("match_updated"),
    }


def is_world_cup(row: dict[str, Any]) -> bool:
    return "world cup" in str(row.get("competition_name") or "").lower()


def is_fifa_world_cup(row: dict[str, Any]) -> bool:
    return str(row.get("competition_name") or "") == "FIFA World Cup"


def is_international_competition(row: dict[str, Any]) -> bool:
    name = str(row.get("competition_name") or "")
    allowed_names = {
        "African Cup of Nations",
        "Copa America",
        "FIFA U20 World Cup",
        "FIFA World Cup",
        "UEFA Euro",
        "UEFA Women's Euro",
        "Women's World Cup",
    }
    return name in allowed_names


def choose_world_cup_sample(world_cups: list[dict[str, Any]]) -> dict[str, Any]:
    for preferred in ("2022", "2018", "2019"):
        for row in world_cups:
            if str(row.get("season_name")) == preferred:
                return row
    if not world_cups:
        raise RuntimeError("No World Cup competitions found in StatsBomb competitions.json")
    return world_cups[0]


def matches_url(competition_id: int, season_id: int) -> str:
    return f"{RAW_BASE}/data/matches/{competition_id}/{season_id}.json"


def events_url(match_id: int) -> str:
    return f"{RAW_BASE}/data/events/{match_id}.json"


def lineups_url(match_id: int) -> str:
    return f"{RAW_BASE}/data/lineups/{match_id}.json"


def compact_match(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_id": match.get("match_id"),
        "match_date": match.get("match_date"),
        "kick_off": match.get("kick_off"),
        "home_team": (match.get("home_team") or {}).get("home_team_name"),
        "away_team": (match.get("away_team") or {}).get("away_team_name"),
        "home_score": match.get("home_score"),
        "away_score": match.get("away_score"),
        "competition": (match.get("competition") or {}).get("competition_name"),
        "season": (match.get("season") or {}).get("season_name"),
        "stadium": (match.get("stadium") or {}).get("name"),
    }


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    result = {
        "id": event.get("id"),
        "index": event.get("index"),
        "period": event.get("period"),
        "timestamp": event.get("timestamp"),
        "type": (event.get("type") or {}).get("name"),
        "team": (event.get("team") or {}).get("name"),
        "player": (event.get("player") or {}).get("name"),
        "location": event.get("location"),
    }
    event_type = result["type"]
    if event_type == "Shot":
        shot = event.get("shot") or {}
        result["shot"] = {
            "statsbomb_xg": shot.get("statsbomb_xg"),
            "outcome": (shot.get("outcome") or {}).get("name"),
            "body_part": (shot.get("body_part") or {}).get("name"),
        }
    elif event_type == "Pass":
        pass_obj = event.get("pass") or {}
        result["pass"] = {
            "recipient": (pass_obj.get("recipient") or {}).get("name"),
            "length": pass_obj.get("length"),
            "angle": pass_obj.get("angle"),
            "height": (pass_obj.get("height") or {}).get("name"),
            "outcome": (pass_obj.get("outcome") or {}).get("name"),
        }
    return result


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_types = Counter(
        (event.get("type") or {}).get("name", "UNKNOWN") for event in events
    )
    shot_events = [event for event in events if (event.get("type") or {}).get("name") == "Shot"]
    pass_events = [event for event in events if (event.get("type") or {}).get("name") == "Pass"]
    lineups = [event for event in events if (event.get("type") or {}).get("name") == "Starting XI"]
    shots_with_xg = [
        event for event in shot_events if (event.get("shot") or {}).get("statsbomb_xg") is not None
    ]
    examples: list[dict[str, Any]] = []
    for desired in ("Starting XI", "Shot", "Pass", "Substitution"):
        event = next(
            (event for event in events if (event.get("type") or {}).get("name") == desired),
            None,
        )
        if event is not None:
            examples.append(compact_event(event))

    return {
        "event_count": len(events),
        "distinct_event_types": sorted(event_types),
        "event_type_counts": dict(sorted(event_types.items())),
        "shot_count": len(shot_events),
        "shots_with_statsbomb_xg": len(shots_with_xg),
        "pass_count": len(pass_events),
        "starting_xi_event_count": len(lineups),
        "example_events": examples,
    }


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_None found._"
    lines = [
        "| competition_id | season_id | competition_name | season_name | country_name |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {competition_id} | {season_id} | {competition_name} | {season_name} | {country_name} |".format(
                **{
                    key: str(row.get(key, "")).replace("|", "\\|")
                    for key in (
                        "competition_id",
                        "season_id",
                        "competition_name",
                        "season_name",
                        "country_name",
                    )
                }
            )
        )
    return "\n".join(lines)


def write_findings(summary: dict[str, Any]) -> None:
    fifa_world_cup_table = markdown_table(summary["fifa_world_cup_rows"])
    world_cup_table = markdown_table(summary["world_cup_rows"])
    international_table = markdown_table(summary["international_rows"])
    event_types = ", ".join(f"`{event_type}`" for event_type in summary["event_summary"]["distinct_event_types"])
    raw_samples = summary["raw_samples"]
    sample_match = summary["sample_match"]
    selected = summary["selected_competition"]
    content = f"""# Source: StatsBomb open data (statsbomb)

- **Reachable:** yes
- **Access method:** public files from GitHub raw (`statsbomb/open-data`)
- **Auth required:** none
- **requires_secret:** false
- **License / terms URL:** {USER_AGREEMENT_URL}, {README_URL}, and https://github.com/statsbomb/open-data
- **Allowed use (1 line):** Free open-data use requires StatsBomb attribution when publishing analysis, research, or derived outputs; respect the repository user agreement and do not redistribute raw samples beyond the intended open-data terms.
- **Endpoint(s) / URL(s) probed:**
  - `{COMPETITIONS_URL}`
  - `{matches_url(selected['competition_id'], selected['season_id'])}`
  - `{events_url(sample_match['match_id'])}`
  - `{README_URL}` for the attribution text.
- **Schema (key columns/fields):**
  - `competitions.json`: `competition_id`, `season_id`, `country_name`, `competition_name`, `competition_gender`, `season_name`, `match_updated`, `match_available`.
  - `matches/<competition_id>/<season_id>.json`: `match_id`, `match_date`, `home_team`, `away_team`, scores, competition/season metadata, venue/stadium metadata.
  - `events/<match_id>.json`: top-level event objects with `id`, `index`, `period`, `timestamp`, `type.name`, `team.name`, optional `player.name`, `location`, and type-specific payloads such as `shot.statsbomb_xg`, `pass.*`, `tactics.lineup`, and substitution fields.
- **Row / record count in sample:** `competitions.json` returned {summary['competitions_request']['record_count']} competition-season rows. Selected World Cup match index returned {summary['matches_request']['record_count']} matches. The one sampled events file returned {summary['event_summary']['event_count']} event records.
- **Date range / freshness (latest record date):** Competitions `match_available` max observed {summary['max_match_available']}; selected match `{sample_match['home_team']} vs {sample_match['away_team']}` was played {sample_match['match_date']} in {selected['competition_name']} {selected['season_name']}.
- **Frozen?** yes for historical open-data match/event releases; this is not a live source for 2026 fixtures or odds.
- **2026 World Cup relevance:** medium for model research and Phase 3 event-feature design, but not useful for 2026 pre-tournament coverage unless StatsBomb later releases 2026 open data. It provides historical event features such as shots, xG, passes, lineups/Starting XI, substitutions, and tactics.
- **Gotchas:** A HTTP 200 was not trusted until raw GitHub returned a JSON-compatible content type and the top-level JSON shape was validated. Raw GitHub served JSON as `{summary['competitions_request']['content_type']}` in this run, so shape validation matters. Events files are much larger than fixtures/results: the one sampled file was {summary['events_request']['bytes']:,} bytes ({summary['events_request']['kilobytes']:.1f} KB). Attribution is required for published work using the free data. Event features are explicitly deferred by the master plan.
- **Recommended phase:** 3
- **Retention recommendation:** raw_retention_days=30, bronze_retention_days=3650. Keep only small raw development samples during discovery; if Phase 3 uses StatsBomb events, store normalized bronze event tables and attribution/provenance metadata.
- **Sample saved at:** raw competitions `{raw_samples['competitions']['path']}`, raw match index `{raw_samples['matches']['path']}`, raw one-match events `{raw_samples['events']['path']}`, committed excerpt `{summary['excerpt_path']}`
- **Status:** usable with caveats

## World Cup competition rows

### FIFA World Cup entries

{fifa_world_cup_table}

### All World Cup-named entries

{world_cup_table}

## Other international competition rows found

{international_table}

## Sampled match and event file

- Match: `{sample_match['match_id']}` - {sample_match['home_team']} {sample_match['home_score']}-{sample_match['away_score']} {sample_match['away_team']} on {sample_match['match_date']}
- Events file size: {summary['events_request']['bytes']:,} bytes ({summary['events_request']['kilobytes']:.1f} KB)
- Distinct event types: {event_types}
- Shots: {summary['event_summary']['shot_count']} total, {summary['event_summary']['shots_with_statsbomb_xg']} with `shot.statsbomb_xg`
- Passes: {summary['event_summary']['pass_count']}
- Starting XI lineup events: {summary['event_summary']['starting_xi_event_count']}

## Attribution note

StatsBomb's open-data README says published analysis/research using this free data must credit StatsBomb. For this project, any report, notebook, dashboard, model card, or published metric derived from StatsBomb open data should include clear attribution such as "Data provided by StatsBomb open data" and link to the open-data repository/user agreement.
"""
    FINDINGS_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    generated_at = now_utc_iso()
    headers = {"Accept": "application/json,text/plain,*/*", "User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=60.0, follow_redirects=True) as client:
        competitions, competitions_request, competitions_bytes = fetch_json_list(
            client, COMPETITIONS_URL, "competitions.json"
        )
        world_cup_rows = sorted(
            [compact_competition(row) for row in competitions if is_world_cup(row)],
            key=lambda row: (
                str(row.get("competition_name") or ""),
                str(row.get("season_name") or ""),
            ),
        )
        fifa_world_cup_rows = sorted(
            [compact_competition(row) for row in competitions if is_fifa_world_cup(row)],
            key=lambda row: str(row.get("season_name") or ""),
        )
        international_rows = sorted(
            [
                compact_competition(row)
                for row in competitions
                if is_international_competition(row) and not is_fifa_world_cup(row)
            ],
            key=lambda row: (
                str(row.get("competition_name") or ""),
                str(row.get("season_name") or ""),
            ),
        )
        selected_competition = choose_world_cup_sample(world_cup_rows)
        competition_id, season_id = competition_key(selected_competition)

        matches, matches_request, matches_bytes = fetch_json_list(
            client,
            matches_url(competition_id, season_id),
            f"matches/{competition_id}/{season_id}.json",
        )
        if not matches:
            raise RuntimeError(
                f"World Cup competition {competition_id}/{season_id} returned no matches"
            )
        sample_match_raw = sorted(
            matches,
            key=lambda row: (
                str(row.get("match_date") or ""),
                int(row.get("match_id") or 0),
            ),
        )[0]
        sample_match = compact_match(sample_match_raw)
        match_id = int(sample_match["match_id"])

        events, events_request, events_bytes = fetch_json_list(
            client,
            events_url(match_id),
            f"events/{match_id}.json",
        )

        readme_response = http_get(client, README_URL)

    raw_competitions = save_sample(SOURCE_ID, "competitions.json", competitions_bytes)
    raw_matches = save_sample(
        SOURCE_ID,
        f"matches-{competition_id}-{season_id}.json",
        matches_bytes,
    )
    raw_events = save_sample(SOURCE_ID, f"events-{match_id}.json", events_bytes)
    raw_readme = save_sample(SOURCE_ID, "README.md", readme_response.content)

    events_request["kilobytes"] = round(events_request["bytes"] / 1024, 1)
    event_summary = summarize_events(events)
    max_match_available = max(
        (row.get("match_available") for row in competitions if row.get("match_available")),
        default=None,
    )
    excerpt_path = write_json(
        EXCERPT_PATH,
        {
            "generated_at": generated_at,
            "source": "StatsBomb open data",
            "fifa_world_cup_rows": fifa_world_cup_rows,
            "world_cup_rows": world_cup_rows,
            "selected_competition": selected_competition,
            "sample_match": sample_match,
            "event_summary": {
                key: event_summary[key]
                for key in (
                    "event_count",
                    "distinct_event_types",
                    "shot_count",
                    "shots_with_statsbomb_xg",
                    "pass_count",
                    "starting_xi_event_count",
                    "example_events",
                )
            },
            "events_file_bytes": events_request["bytes"],
            "events_file_kilobytes": events_request["kilobytes"],
        },
    )

    summary = {
        "source_id": SOURCE_ID,
        "generated_at": generated_at,
        "requires_secret": False,
        "competitions_request": competitions_request,
        "matches_request": matches_request,
        "events_request": events_request,
        "readme_request": {
            "url": README_URL,
            "status_code": readme_response.status_code,
            "content_type": readme_response.headers.get("content-type"),
            "bytes": len(readme_response.content),
        },
        "world_cup_rows": world_cup_rows,
        "fifa_world_cup_rows": fifa_world_cup_rows,
        "international_rows": international_rows,
        "selected_competition": selected_competition,
        "sample_match": sample_match,
        "max_match_available": max_match_available,
        "event_summary": event_summary,
        "raw_samples": {
            "competitions": raw_competitions,
            "matches": raw_matches,
            "events": raw_events,
            "readme": raw_readme,
        },
        "excerpt_path": excerpt_path,
        "findings_path": FINDINGS_PATH.relative_to(ROOT).as_posix(),
        "recommended_phase": 3,
        "attribution_required": True,
    }
    write_findings(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
