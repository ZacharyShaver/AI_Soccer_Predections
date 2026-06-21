from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from _common import ROOT, USER_AGENT, now_utc_iso, save_sample


SOURCE_ID = "oddsapi"
API_BASE = "https://api.the-odds-api.com"
FINDINGS_DIR = ROOT / "discovery" / "findings"
FINDINGS_PATH = FINDINGS_DIR / "d6-oddsapi.md"
SCHEMA_EXCERPT_PATH = FINDINGS_DIR / "d6-oddsapi-schema-excerpt.json"
DOCS_URL = "https://the-odds-api.com/liveapi/guides/v4/"
SPORTS_DOC_URL = "https://the-odds-api.com/sports-odds-data/sports-apis.html"
PLANS_URL = "https://the-odds-api.com/#plans"

DOCUMENTED_SOCCER_KEYS = [
    ("soccer_fifa_world_cup", "FIFA World Cup"),
    ("soccer_fifa_world_cup_qualifiers_europe", "FIFA World Cup Qualifiers - Europe"),
    (
        "soccer_fifa_world_cup_qualifiers_south_america",
        "FIFA World Cup Qualifiers - South America",
    ),
    ("soccer_fifa_world_cup_womens", "FIFA Women's World Cup"),
    ("soccer_fifa_world_cup_winner", "FIFA World Cup Winner"),
    ("soccer_fifa_club_world_cup", "FIFA Club World Cup"),
    ("soccer_uefa_champs_league", "UEFA Champions League"),
    ("soccer_conmebol_copa_america", "Copa America"),
    ("soccer_concacaf_gold_cup", "CONCACAF Gold Cup"),
    ("soccer_usa_mls", "MLS"),
]

QUOTA_HEADER_KEYS = [
    "x-requests-remaining",
    "x-requests-used",
    "x-requests-last",
]


def quota_headers(response: httpx.Response) -> dict[str, str | None]:
    return {key: response.headers.get(key) for key in QUOTA_HEADER_KEYS}


def response_facts(
    endpoint: str, params_without_secret: dict[str, Any], response: httpx.Response
) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "params_without_secret": params_without_secret,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
        "quota_headers": quota_headers(response),
    }


def api_get_json(
    client: httpx.Client,
    endpoint: str,
    params_without_secret: dict[str, Any],
    api_key: str,
) -> tuple[Any, dict[str, Any], httpx.Response]:
    params = {**params_without_secret, "apiKey": api_key}
    response = client.get(f"{API_BASE}{endpoint}", params=params)
    facts = response_facts(endpoint, params_without_secret, response)

    if response.status_code != 200:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(
            f"GET {endpoint} returned HTTP {response.status_code}: {preview}"
        )

    content_type = response.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(
            f"GET {endpoint} returned HTTP 200 but non-JSON content-type "
            f"{content_type!r}: {preview}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"GET {endpoint} returned invalid JSON: {preview}") from exc

    return payload, facts, response


def require_list_of_dicts(payload: Any, endpoint: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(
            f"GET {endpoint} returned JSON {type(payload).__name__}, expected list"
        )
    bad_item = next((item for item in payload if not isinstance(item, dict)), None)
    if bad_item is not None:
        raise RuntimeError(f"GET {endpoint} returned list with non-object item")
    return payload


def validate_sports_payload(payload: Any, endpoint: str) -> list[dict[str, Any]]:
    sports = require_list_of_dicts(payload, endpoint)
    required_keys = {"key", "group", "title", "description", "active", "has_outrights"}
    for sport in sports:
        missing = sorted(required_keys - set(sport))
        if missing:
            raise RuntimeError(f"GET {endpoint} sport object missing keys: {missing}")
    return sports


def validate_odds_payload(payload: Any, endpoint: str) -> list[dict[str, Any]]:
    events = require_list_of_dicts(payload, endpoint)
    event_keys = {"id", "sport_key", "commence_time", "home_team", "away_team", "bookmakers"}
    for event in events:
        missing = sorted(event_keys - set(event))
        if missing:
            raise RuntimeError(f"GET {endpoint} odds event missing keys: {missing}")
        if not isinstance(event.get("bookmakers"), list):
            raise RuntimeError(f"GET {endpoint} event bookmakers field is not a list")
        for bookmaker in event.get("bookmakers") or []:
            if not isinstance(bookmaker, dict):
                raise RuntimeError(f"GET {endpoint} bookmaker entry is not an object")
            if not isinstance(bookmaker.get("markets", []), list):
                raise RuntimeError(f"GET {endpoint} bookmaker markets field is not a list")
    return events


def compact_sport(sport: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": sport.get("key"),
        "group": sport.get("group"),
        "title": sport.get("title"),
        "description": sport.get("description"),
        "active": sport.get("active"),
        "has_outrights": sport.get("has_outrights"),
    }


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    bookmakers = event.get("bookmakers") or []
    return {
        "id": event.get("id"),
        "sport_key": event.get("sport_key"),
        "sport_title": event.get("sport_title"),
        "commence_time": event.get("commence_time"),
        "home_team": event.get("home_team"),
        "away_team": event.get("away_team"),
        "bookmaker_count": len(bookmakers),
        "bookmakers": [
            {
                "key": bookmaker.get("key"),
                "title": bookmaker.get("title"),
                "last_update": bookmaker.get("last_update"),
                "markets": [
                    {
                        "key": market.get("key"),
                        "last_update": market.get("last_update"),
                        "outcomes": market.get("outcomes"),
                    }
                    for market in (bookmaker.get("markets") or [])[:2]
                ],
            }
            for bookmaker in bookmakers[:3]
        ],
    }


def choose_odds_sport(soccer_sports: list[dict[str, Any]]) -> dict[str, Any] | None:
    for key in ("soccer_fifa_world_cup", "soccer_fifa_world_cup_qualifiers_europe"):
        for sport in soccer_sports:
            if sport.get("key") == key and sport.get("active") is True:
                return sport
    for sport in soccer_sports:
        if sport.get("active") is True:
            return sport
    return soccer_sports[0] if soccer_sports else None


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def docs_soccer_keys_md() -> str:
    return "\n".join(
        f"  - `{key}` - {title}" for key, title in DOCUMENTED_SOCCER_KEYS
    )


def quota_budget_md() -> str:
    return (
        "Starter/free plan is documented as 500 credits per month. For `/v4/odds`, "
        "each market costs 1 credit for each requested region, so one sport with "
        "`regions=us` and `markets=h2h` costs 1 credit per poll. A realistic World "
        "Cup match-day runner can exceed that quickly: hourly polling for a 12-hour "
        "active window across 25 match days costs about 300 credits for one "
        "region/market, while 15-minute polling for the same window costs about "
        "1,200 credits. Multiple regions or markets multiply the cost linearly. "
        "The future live runner needs a hard monthly budget guard, a minimum poll "
        "interval, and explicit region/market allowlists."
    )


def write_findings_no_key(generated_at: str) -> None:
    content = f"""# Source: The Odds API (oddsapi)

- **Reachable:** not tested live; API key absent, so this is a docs-backed finding only
- **Access method:** REST + API key
- **Auth required:** API key (`THE_ODDS_API_KEY`)
- **requires_secret:** true
- **License / terms URL:** {DOCS_URL}, {SPORTS_DOC_URL}, {PLANS_URL}, and https://the-odds-api.com/terms/
- **Allowed use (1 line):** Use as a paid/live odds signal only through the documented API, with the key read from `THE_ODDS_API_KEY`, no key committed, and quota guarded.
- **Endpoint(s) / URL(s) probed:** none, because `THE_ODDS_API_KEY` was absent. Documentation reviewed for `/v4/sports/` and `/v4/sports/{{sport}}/odds/`.
- **Schema (key columns/fields):**
  - `/v4/sports/` sport object fields documented and/or expected by the probe: `key`, `group`, `title`, `description`, `active`, `has_outrights`.
  - `/v4/odds` event fields documented by The Odds API: `id`, `sport_key`, `sport_title`, `commence_time`, `home_team`, `away_team`, and nested `bookmakers[]` with `key`, `title`, `last_update`, `markets[]`, `outcomes[]`.
  - Documented soccer keys relevant to this project include:
{docs_soccer_keys_md()}
- **Row / record count in sample:** no live sample fetched; docs-only soccer key excerpt contains {len(DOCUMENTED_SOCCER_KEYS)} keys.
- **Date range / freshness (latest record date):** no live data fetched. Findings generated at {generated_at}.
- **Frozen?** no - this is a live odds API, but no live response was fetched in this no-key run.
- **2026 World Cup relevance:** high if keyed and budgeted. The documented `soccer_fifa_world_cup`, qualifier, and outright winner sport keys directly match World Cup betting markets.
- **Gotchas:** `THE_ODDS_API_KEY` was absent, so the probe intentionally skipped `/v4/sports/` and all `/v4/odds` calls. A HTTP 200 is not considered valid until `content-type` includes `application/json` and the top-level JSON shape matches the endpoint. The documented quota response headers to capture are `x-requests-remaining`, `x-requests-used`, and `x-requests-last`. `/v4/sports/` is documented as free; `/v4/odds` costs 1 credit per region per market per call. Do not include `apiKey` in logged URLs or committed artifacts.
- **Recommended phase:** 2
- **Retention recommendation:** raw_retention_days=7, bronze_retention_days=3650. Keep normalized timestamped odds snapshots with quota headers and request parameters, but keep raw responses short-lived because odds stale quickly.
- **Sample saved at:** none; no key was present and no live sample was fetched.
- **Status:** usable with caveats

## Probe output highlights

- Required command path: `uv run --with httpx python discovery/probes/probe_oddsapi.py`
- Key present: no
- API credits consumed by this run: 0
- Documentation evidence:
  - Sports endpoint is documented at `{DOCS_URL}` and does not count against quota.
  - Sports list/key reference is documented at `{SPORTS_DOC_URL}`.
  - Starter plan is documented at `{PLANS_URL}` as 500 credits per month.

## Credit budget

{quota_budget_md()}
"""
    FINDINGS_PATH.write_text(content, encoding="utf-8")


def write_findings_with_key(summary: dict[str, Any]) -> None:
    chosen_sport = summary["chosen_odds_sport"]
    odds_event_count = summary["odds_event_count"]
    odds_sample_text = (
        f"`{summary['raw_samples']['odds']['path']}`"
        if summary.get("raw_samples", {}).get("odds")
        else "none"
    )
    soccer_lines = "\n".join(
        f"  - `{sport['key']}` - {sport['title']} "
        f"(active={sport['active']}, has_outrights={sport['has_outrights']})"
        for sport in summary["soccer_sports"][:20]
    )
    schema_excerpt = summary.get("schema_excerpt_path") or "none"
    first_event = summary.get("first_odds_event_excerpt")
    first_event_line = (
        "No event object was returned by the single odds call; only the top-level list "
        "shape was confirmed."
        if first_event is None
        else "First event schema excerpt saved with event/bookmaker/market/outcome fields."
    )
    content = f"""# Source: The Odds API (oddsapi)

- **Reachable:** yes
- **Access method:** REST + API key
- **Auth required:** API key (`THE_ODDS_API_KEY`)
- **requires_secret:** true
- **License / terms URL:** {DOCS_URL}, {SPORTS_DOC_URL}, {PLANS_URL}, and https://the-odds-api.com/terms/
- **Allowed use (1 line):** Use as a paid/live odds signal only through the documented API, with the key read from `THE_ODDS_API_KEY`, no key committed, and quota guarded.
- **Endpoint(s) / URL(s) probed:**
  - `GET https://api.the-odds-api.com/v4/sports/?all=true&apiKey=...` (free; sanitized in committed artifacts)
  - `GET https://api.the-odds-api.com/v4/sports/{chosen_sport['key']}/odds/?regions=us&markets=h2h&oddsFormat=decimal&apiKey=...` (one paid call; sanitized in committed artifacts)
- **Schema (key columns/fields):**
  - `/v4/sports/`: `key`, `group`, `title`, `description`, `active`, `has_outrights`.
  - `/v4/odds`: top-level list of event objects. Expected event fields validated when present: `id`, `sport_key`, `commence_time`, `home_team`, `away_team`, `bookmakers[]`; nested bookmakers expose `key`, `title`, `last_update`, `markets[]`; markets expose `key`, `last_update`, `outcomes[]`.
  - {first_event_line}
- **Row / record count in sample:** `/v4/sports/?all=true` returned {summary['sports_count']} sports, including {summary['soccer_sports_count']} soccer sports. The single `/v4/odds` call for `{chosen_sport['key']}` returned {odds_event_count} events.
- **Date range / freshness (latest record date):** Probe generated at {summary['generated_at']}. Latest `commence_time` in the single odds response: {summary.get('latest_commence_time') or 'not available'}.
- **Frozen?** no - live odds endpoint, response changes by market and bookmaker update cadence.
- **2026 World Cup relevance:** high if budgeted. Live sports list included `{chosen_sport['key']}` for the paid schema probe. Documented World Cup-related soccer keys include `soccer_fifa_world_cup`, qualifiers, and `soccer_fifa_world_cup_winner`.
- **Gotchas:** A HTTP 200 was not trusted until `content-type: application/json` and JSON shape were validated. The API key was read only from `THE_ODDS_API_KEY` and omitted from logged URLs, raw metadata, and committed artifacts. `/v4/sports/` is documented as free; `/v4/odds` costs 1 credit per region per market per call. Quota headers from the paid response: `x-requests-remaining={summary['odds_request']['quota_headers'].get('x-requests-remaining')}`, `x-requests-used={summary['odds_request']['quota_headers'].get('x-requests-used')}`, `x-requests-last={summary['odds_request']['quota_headers'].get('x-requests-last')}`.
- **Recommended phase:** 2
- **Retention recommendation:** raw_retention_days=7, bronze_retention_days=3650. Keep normalized timestamped odds snapshots with quota headers and request parameters, but keep raw responses short-lived because odds stale quickly.
- **Sample saved at:** raw sports list `{summary['raw_samples']['sports']['path']}`, raw odds response {odds_sample_text}, committed schema excerpt `{schema_excerpt}`
- **Status:** usable with caveats

## Probe output highlights

- Required command path: `uv run --with httpx python discovery/probes/probe_oddsapi.py`
- Key present: yes
- API credits consumed by this run: {summary['credits_consumed']}
- Sports quota headers: `x-requests-remaining={summary['sports_request']['quota_headers'].get('x-requests-remaining')}`, `x-requests-used={summary['sports_request']['quota_headers'].get('x-requests-used')}`, `x-requests-last={summary['sports_request']['quota_headers'].get('x-requests-last')}`
- Odds quota headers: `x-requests-remaining={summary['odds_request']['quota_headers'].get('x-requests-remaining')}`, `x-requests-used={summary['odds_request']['quota_headers'].get('x-requests-used')}`, `x-requests-last={summary['odds_request']['quota_headers'].get('x-requests-last')}`
- Soccer competitions from the sports response, first 20:
{soccer_lines}

## Credit budget

{quota_budget_md()}
"""
    FINDINGS_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    generated_at = now_utc_iso()
    api_key = os.environ.get("THE_ODDS_API_KEY")
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)

    if not api_key:
        write_findings_no_key(generated_at)
        summary = {
            "source_id": SOURCE_ID,
            "generated_at": generated_at,
            "requires_secret": True,
            "key_present": False,
            "credits_consumed": 0,
            "live_calls_made": [],
            "documented_soccer_keys": [
                {"key": key, "title": title} for key, title in DOCUMENTED_SOCCER_KEYS
            ],
            "documentation": {
                "v4_docs": DOCS_URL,
                "sports_keys": SPORTS_DOC_URL,
                "plans": PLANS_URL,
            },
            "findings_path": FINDINGS_PATH.relative_to(ROOT).as_posix(),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        sports_payload, sports_request, sports_response = api_get_json(
            client, "/v4/sports/", {"all": "true"}, api_key
        )
        sports = validate_sports_payload(sports_payload, "/v4/sports/")
        soccer_sports = [
            compact_sport(sport)
            for sport in sports
            if str(sport.get("group")).lower() == "soccer"
        ]
        selected = choose_odds_sport(soccer_sports)
        if selected is None:
            raise RuntimeError("GET /v4/sports/ returned no soccer sports")

        odds_endpoint = f"/v4/sports/{selected['key']}/odds/"
        odds_params = {
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }
        odds_payload, odds_request, odds_response = api_get_json(
            client, odds_endpoint, odds_params, api_key
        )
        odds_events = validate_odds_payload(odds_payload, odds_endpoint)

    raw_sports = save_sample(
        SOURCE_ID,
        "sports-all.json",
        json.dumps(sports_payload, indent=2, sort_keys=True).encode("utf-8"),
    )
    raw_odds = save_sample(
        SOURCE_ID,
        f"odds-{selected['key']}-us-h2h.json",
        json.dumps(odds_payload, indent=2, sort_keys=True).encode("utf-8"),
    )
    first_event = compact_event(odds_events[0]) if odds_events else None
    latest_commence_time = max(
        (event.get("commence_time") for event in odds_events if event.get("commence_time")),
        default=None,
    )
    schema_excerpt_path = write_json(
        SCHEMA_EXCERPT_PATH,
        {
            "generated_at": generated_at,
            "source": "The Odds API",
            "key_present": True,
            "credits_consumed": 1,
            "sports_request": sports_request,
            "odds_request": odds_request,
            "chosen_odds_sport": selected,
            "sports_count": len(sports),
            "soccer_sports_count": len(soccer_sports),
            "soccer_sports_excerpt": soccer_sports[:20],
            "odds_event_count": len(odds_events),
            "first_odds_event_excerpt": first_event,
            "latest_commence_time": latest_commence_time,
        },
    )

    summary = {
        "source_id": SOURCE_ID,
        "generated_at": generated_at,
        "requires_secret": True,
        "key_present": True,
        "credits_consumed": 1,
        "sports_count": len(sports),
        "soccer_sports_count": len(soccer_sports),
        "soccer_sports": soccer_sports,
        "chosen_odds_sport": selected,
        "odds_event_count": len(odds_events),
        "first_odds_event_excerpt": first_event,
        "latest_commence_time": latest_commence_time,
        "sports_request": sports_request,
        "odds_request": odds_request,
        "raw_samples": {
            "sports": raw_sports,
            "odds": raw_odds,
        },
        "schema_excerpt_path": schema_excerpt_path,
        "findings_path": FINDINGS_PATH.relative_to(ROOT).as_posix(),
    }
    write_findings_with_key(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
