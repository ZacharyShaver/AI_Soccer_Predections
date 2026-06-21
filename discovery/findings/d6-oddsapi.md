# Source: The Odds API (oddsapi)

- **Reachable:** not tested live; API key absent, so this is a docs-backed finding only
- **Access method:** REST + API key
- **Auth required:** API key (`THE_ODDS_API_KEY`)
- **requires_secret:** true
- **License / terms URL:** https://the-odds-api.com/liveapi/guides/v4/, https://the-odds-api.com/sports-odds-data/sports-apis.html, https://the-odds-api.com/#plans, and https://the-odds-api.com/terms/
- **Allowed use (1 line):** Use as a paid/live odds signal only through the documented API, with the key read from `THE_ODDS_API_KEY`, no key committed, and quota guarded.
- **Endpoint(s) / URL(s) probed:** none, because `THE_ODDS_API_KEY` was absent. Documentation reviewed for `/v4/sports/` and `/v4/sports/{sport}/odds/`.
- **Schema (key columns/fields):**
  - `/v4/sports/` sport object fields documented and/or expected by the probe: `key`, `group`, `title`, `description`, `active`, `has_outrights`.
  - `/v4/odds` event fields documented by The Odds API: `id`, `sport_key`, `sport_title`, `commence_time`, `home_team`, `away_team`, and nested `bookmakers[]` with `key`, `title`, `last_update`, `markets[]`, `outcomes[]`.
  - Documented soccer keys relevant to this project include:
  - `soccer_fifa_world_cup` - FIFA World Cup
  - `soccer_fifa_world_cup_qualifiers_europe` - FIFA World Cup Qualifiers - Europe
  - `soccer_fifa_world_cup_qualifiers_south_america` - FIFA World Cup Qualifiers - South America
  - `soccer_fifa_world_cup_womens` - FIFA Women's World Cup
  - `soccer_fifa_world_cup_winner` - FIFA World Cup Winner
  - `soccer_fifa_club_world_cup` - FIFA Club World Cup
  - `soccer_uefa_champs_league` - UEFA Champions League
  - `soccer_conmebol_copa_america` - Copa America
  - `soccer_concacaf_gold_cup` - CONCACAF Gold Cup
  - `soccer_usa_mls` - MLS
- **Row / record count in sample:** no live sample fetched; docs-only soccer key excerpt contains 10 keys.
- **Date range / freshness (latest record date):** no live data fetched. Findings generated at 2026-06-21T19:00:51+00:00.
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
  - Sports endpoint is documented at `https://the-odds-api.com/liveapi/guides/v4/` and does not count against quota.
  - Sports list/key reference is documented at `https://the-odds-api.com/sports-odds-data/sports-apis.html`.
  - Starter plan is documented at `https://the-odds-api.com/#plans` as 500 credits per month.

## Credit budget

Starter/free plan is documented as 500 credits per month. For `/v4/odds`, each market costs 1 credit for each requested region, so one sport with `regions=us` and `markets=h2h` costs 1 credit per poll. A realistic World Cup match-day runner can exceed that quickly: hourly polling for a 12-hour active window across 25 match days costs about 300 credits for one region/market, while 15-minute polling for the same window costs about 1,200 credits. Multiple regions or markets multiply the cost linearly. The future live runner needs a hard monthly budget guard, a minimum poll interval, and explicit region/market allowlists.
