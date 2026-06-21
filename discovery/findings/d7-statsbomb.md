# Source: StatsBomb open data (statsbomb)

- **Reachable:** yes
- **Access method:** public files from GitHub raw (`statsbomb/open-data`)
- **Auth required:** none
- **requires_secret:** false
- **License / terms URL:** https://raw.githubusercontent.com/statsbomb/open-data/master/LICENSE.pdf, https://raw.githubusercontent.com/statsbomb/open-data/master/README.md, and https://github.com/statsbomb/open-data
- **Allowed use (1 line):** Free open-data use requires StatsBomb attribution when publishing analysis, research, or derived outputs; respect the repository user agreement and do not redistribute raw samples beyond the intended open-data terms.
- **Endpoint(s) / URL(s) probed:**
  - `https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json`
  - `https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/43/106.json`
  - `https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/3857286.json`
  - `https://raw.githubusercontent.com/statsbomb/open-data/master/README.md` for the attribution text.
- **Schema (key columns/fields):**
  - `competitions.json`: `competition_id`, `season_id`, `country_name`, `competition_name`, `competition_gender`, `season_name`, `match_updated`, `match_available`.
  - `matches/<competition_id>/<season_id>.json`: `match_id`, `match_date`, `home_team`, `away_team`, scores, competition/season metadata, venue/stadium metadata.
  - `events/<match_id>.json`: top-level event objects with `id`, `index`, `period`, `timestamp`, `type.name`, `team.name`, optional `player.name`, `location`, and type-specific payloads such as `shot.statsbomb_xg`, `pass.*`, `tactics.lineup`, and substitution fields.
- **Row / record count in sample:** `competitions.json` returned 80 competition-season rows. Selected World Cup match index returned 64 matches. The one sampled events file returned 3299 event records.
- **Date range / freshness (latest record date):** Competitions `match_available` max observed 2026-05-15T15:54:04.598614; selected match `Qatar vs Ecuador` was played 2022-11-20 in FIFA World Cup 2022.
- **Frozen?** yes for historical open-data match/event releases; this is not a live source for 2026 fixtures or odds.
- **2026 World Cup relevance:** medium for model research and Phase 3 event-feature design, but not useful for 2026 pre-tournament coverage unless StatsBomb later releases 2026 open data. It provides historical event features such as shots, xG, passes, lineups/Starting XI, substitutions, and tactics.
- **Gotchas:** A HTTP 200 was not trusted until raw GitHub returned a JSON-compatible content type and the top-level JSON shape was validated. Raw GitHub served JSON as `text/plain; charset=utf-8` in this run, so shape validation matters. Events files are much larger than fixtures/results: the one sampled file was 2,799,478 bytes (2733.9 KB). Attribution is required for published work using the free data. Event features are explicitly deferred by the master plan.
- **Recommended phase:** 3
- **Retention recommendation:** raw_retention_days=30, bronze_retention_days=3650. Keep only small raw development samples during discovery; if Phase 3 uses StatsBomb events, store normalized bronze event tables and attribution/provenance metadata.
- **Sample saved at:** raw competitions `discovery/samples/statsbomb/competitions.json`, raw match index `discovery/samples/statsbomb/matches-43-106.json`, raw one-match events `discovery/samples/statsbomb/events-3857286.json`, committed excerpt `discovery/findings/d7-statsbomb-excerpt.json`
- **Status:** usable with caveats

## World Cup competition rows

### FIFA World Cup entries

| competition_id | season_id | competition_name | season_name | country_name |
| --- | --- | --- | --- | --- |
| 43 | 269 | FIFA World Cup | 1958 | International |
| 43 | 270 | FIFA World Cup | 1962 | International |
| 43 | 272 | FIFA World Cup | 1970 | International |
| 43 | 51 | FIFA World Cup | 1974 | International |
| 43 | 54 | FIFA World Cup | 1986 | International |
| 43 | 55 | FIFA World Cup | 1990 | International |
| 43 | 3 | FIFA World Cup | 2018 | International |
| 43 | 106 | FIFA World Cup | 2022 | International |

### All World Cup-named entries

| competition_id | season_id | competition_name | season_name | country_name |
| --- | --- | --- | --- | --- |
| 1470 | 274 | FIFA U20 World Cup | 1979 | International |
| 43 | 269 | FIFA World Cup | 1958 | International |
| 43 | 270 | FIFA World Cup | 1962 | International |
| 43 | 272 | FIFA World Cup | 1970 | International |
| 43 | 51 | FIFA World Cup | 1974 | International |
| 43 | 54 | FIFA World Cup | 1986 | International |
| 43 | 55 | FIFA World Cup | 1990 | International |
| 43 | 3 | FIFA World Cup | 2018 | International |
| 43 | 106 | FIFA World Cup | 2022 | International |
| 72 | 30 | Women's World Cup | 2019 | International |
| 72 | 107 | Women's World Cup | 2023 | International |

## Other international competition rows found

| competition_id | season_id | competition_name | season_name | country_name |
| --- | --- | --- | --- | --- |
| 1267 | 107 | African Cup of Nations | 2023 | Africa |
| 223 | 282 | Copa America | 2024 | South America |
| 1470 | 274 | FIFA U20 World Cup | 1979 | International |
| 55 | 43 | UEFA Euro | 2020 | Europe |
| 55 | 282 | UEFA Euro | 2024 | Europe |
| 53 | 106 | UEFA Women's Euro | 2022 | Europe |
| 53 | 315 | UEFA Women's Euro | 2025 | Europe |
| 72 | 30 | Women's World Cup | 2019 | International |
| 72 | 107 | Women's World Cup | 2023 | International |

## Sampled match and event file

- Match: `3857286` - Qatar 0-2 Ecuador on 2022-11-20
- Events file size: 2,799,478 bytes (2733.9 KB)
- Distinct event types: `50/50`, `Ball Receipt*`, `Ball Recovery`, `Block`, `Carry`, `Clearance`, `Dispossessed`, `Dribble`, `Dribbled Past`, `Duel`, `Foul Committed`, `Foul Won`, `Goal Keeper`, `Half End`, `Half Start`, `Injury Stoppage`, `Interception`, `Miscontrol`, `Offside`, `Pass`, `Player Off`, `Player On`, `Pressure`, `Shield`, `Shot`, `Starting XI`, `Substitution`, `Tactical Shift`
- Shots: 11 total, 11 with `shot.statsbomb_xg`
- Passes: 987
- Starting XI lineup events: 2

## Attribution note

StatsBomb's open-data README says published analysis/research using this free data must credit StatsBomb. For this project, any report, notebook, dashboard, model card, or published metric derived from StatsBomb open data should include clear attribution such as "Data provided by StatsBomb open data" and link to the open-data repository/user agreement.
