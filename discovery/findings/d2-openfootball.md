# Source: openfootball World Cup 2026 fixtures (openfootball)

- **Reachable:** yes
- **Access method:** public REST metadata via GitHub contents API plus public raw files
- **Auth required:** none
- **License / terms URL:** https://github.com/openfootball/worldcup/blob/master/LICENSE.md
- **Allowed use (1 line):** Repository uses CC0 1.0 Universal / public domain dedication; data can be reused freely, while retaining source provenance in this project.
- **Endpoint(s) / URL(s) probed:**
  - https://api.github.com/repos/openfootball/worldcup/contents/
  - https://api.github.com/repos/openfootball/worldcup/contents/2026--usa
  - https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup.txt
  - https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup_finals.txt
  - https://raw.githubusercontent.com/openfootball/worldcup/master/LICENSE.md
- **Schema (key columns/fields):** Plain text football.db-style fixture files. Parsed fields are `file_path`, `section` / stage, `match_date`, `home_team`, `away_team`, `venue`, and optional `match_number` for knockout matches. Group declarations encode 12 groups and 48 team names. Knockout fixtures use placeholders such as `1A`, `2B`, `W74`, and `L101`.
- **Row / record count in sample:** 104 fixtures parsed total: 72 group-stage fixtures from `2026--usa/cup.txt` and 32 knockout fixtures from `2026--usa/cup_finals.txt`. All 12 groups and all 48 teams were present. Raw files saved locally: `cup.txt` 11,482 bytes; `cup_finals.txt` 2,415 bytes. Committed excerpt: `discovery/findings/d2-openfootball-fixture-excerpt.txt`.
- **Date range / freshness (latest record date):** Parsed fixture dates span 2026-06-11 to 2026-07-19. Venue/city labels parsed: 16. Sample labels: Atlanta; Boston (Foxborough); Dallas (Arlington); Guadalajara (Zapopan); Houston; Kansas City; Los Angeles (Inglewood); Mexico City.
- **Frozen?** no - the 2026 directory and fixture files are present in the live repo. Treat result scores inside the fixture text as source data that still needs cross-validation before completed-match ingestion.
- **2026 World Cup relevance:** high - direct fixture and bracket source for the 2026 World Cup, including group assignments, host-city labels, scheduled dates, and knockout placeholders.
- **Gotchas:** The 2026 directory discovered through the contents API is `2026--usa`, not a generic North America path. Knockout structure is in the companion `cup_finals.txt`, not in `cup.txt` alone. Exact-name cross-check against martj42 `results.csv` found 2 fixture team names absent from martj42 `home_team` / `away_team`: `Bosnia & Herzegovina`, `USA`. These need alias-table handling, likely to martj42-style names such as `Bosnia and Herzegovina` and `United States`. The fixture file itself also notes FIFA-normalized alternatives including `Korea Republic`, `IR Iran`, `Cabo Verde`, `Congo DR`, `Cote d'Ivoire`, `Czechia`, and `Turkiye`, so ingestion should separate display names from canonical team ids.
- **Recommended phase:** 1
- **Retention recommendation:** raw_retention_days=30, bronze_retention_days=3650
- **Sample saved at:** `discovery/samples/openfootball/cup.txt`, `discovery/samples/openfootball/cup_finals.txt`; committed excerpt: `discovery/findings/d2-openfootball-fixture-excerpt.txt`
- **Status:** usable with caveats

## Probe output highlights

- Required command passed: `uv run --with httpx python discovery/probes/probe_openfootball.py`
- GitHub contents API discovered exact 2026 fixture paths: `2026--usa/cup.txt`, `2026--usa/cup_finals.txt`
- Knockout bracket structure present: yes, 32 fixtures with round counts `Round of 32=16`, `Round of 16=8`, `Quarter-final=4`, `Semi-final=2`, `Match for third place=1`, `Final=1`; match numbers span 73 to 104.
- Martj42 cross-check source: local `discovery/samples/martj42/results.csv`; martj42 distinct team names loaded: 336; unmatched exact fixture names: `Bosnia & Herzegovina`, `USA`.
