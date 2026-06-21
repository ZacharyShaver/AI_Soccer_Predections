# Discovery Report

## What's Actually Usable for Milestone 1

Milestone 1 should stay narrow:

- **D1 martj42 international results** for historical international results and the Elo training history. It has 49,477 `results.csv` rows, spans 1872-11-30 to 2026-06-27, has scored results through 2026-06-20, and includes 1,385 rows in 2025-2026.
- **D2 openfootball World Cup 2026 fixtures** for the 2026 schedule and bracket. It has 104 fixtures: 72 group-stage fixtures, 32 knockout fixtures, all 12 groups, all 48 teams, and dates from 2026-06-11 to 2026-07-19.
- **Build our own Elo from D1.** D8 found no legally clean external rating feed selected for ingestion, so Elo should be deterministic internal features, not a dependency on FIFA/eloratings mirrors.

Everything else is benchmark or later-phase material: Football-Data, Polymarket, and The Odds API are Phase 2 market/odds comparators; StatsBomb, GDELT/news, and social aggregates are Phase 3 deferred context/features.

## Source Summary

| Source | Status | Phase | Reachable | Auth / requires_secret | 2026 relevance | Key gotcha | Retention rec |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| D1 martj42 international results | ⚠️ usable-with-caveats | 1 | yes | none / false | high: historical results plus 2025-2026 freshness | `results.csv` includes 36 blank-score future fixture rows; split fixtures from completed results before training | raw 30d, bronze 3650d |
| D2 openfootball World Cup 2026 fixtures | ⚠️ usable-with-caveats | 1 | yes | none / false | high: direct 2026 fixture and bracket source | discovered path is `2026--usa`; knockout bracket is in `cup_finals.txt`; alias seeds include `Bosnia & Herzegovina` and `USA` | raw 30d, bronze 3650d |
| D3 FiveThirtyEight SPI | ⛔ drop | drop | partial only | none / false | low: no current parseable international CSV | documented CSVs 404 or redirect to ABC News HTML despite HTTP 200; no live path should use SPI | raw 0d unless an approved archive is selected |
| D4 Football-Data.co.uk odds | ⚠️ usable-with-caveats | 2 | yes | none / false | medium: has `WorldCup2026.xlsx`, qualifiers, and historical WC sheets | no CC-style open license found; do not redistribute raw files; WC workbook odds names differ from club CSV names and lacks probed closing H/D/A columns | raw 30d, bronze 3650d |
| D5 Polymarket public market data | ⚠️ usable-with-caveats | 2 | yes | none / false | high for market-implied benchmarks: 431 events and 10,573 markets under the active WC tag | `outcomes` and `outcomePrices` are often JSON strings; 250 markets had null/invalid prices; event-level Yes prices need de-vig for exclusive groups | raw 7d, bronze 3650d |
| D6 The Odds API | ⚠️ usable-with-caveats | 2 | not live-tested; docs only | `THE_ODDS_API_KEY` / true | high if keyed: documented WC, qualifier, and outright winner sport keys | no key was present, so 0 live calls; future runner needs budget guards and must never log `apiKey` | raw 7d, bronze 3650d |
| D7 StatsBomb open data | ⚠️ usable-with-caveats | 3 | yes | none / false | medium: historical event features, not live 2026 | one sampled event file was 2,799,478 bytes; attribution required; 2026 open data not present | raw 30d, bronze 3650d |
| D8 Team ratings / Elo / FIFA rankings | ⚠️ usable-with-caveats | 2 | partial | none for survey / false | high as a concept; external feeds not selected | no legal external rating feed selected; FIFA API paths disallowed and mirrors do not cure upstream rights | external raw 0d; internal Elo bronze 3650d |
| D9 News / injury RSS feeds | ⚠️ usable-with-caveats | 3 | partial | none for GDELT; Guardian API key not used | medium: optional context, not core probability path | publisher feeds are restrictive; GDELT 429'd on broad query, so future use needs strict rate limits and metadata-only storage | publisher raw 0d; GDELT raw 7d, bronze 365d |
| D10 X / Reddit social compliance | ⚠️ usable-with-caveats | 3 | docs reachable only | future API secrets required / true | medium: optional aggregate context only | no raw user text, no training on Reddit user content without permission, and no X Content training for foundation/frontier models | raw text 0d, aggregate bronze 365d |

## P1 Definition Of Done Check

- [x] Every source D1-D10 has a findings note present under `discovery/findings/`.
- [x] `DISCOVERY_REPORT.md` gives a clear Milestone-1 shortlist: D1 martj42 plus D2 openfootball, with internal Elo derived from D1.
- [x] `sources_evidence.yaml` exists and is backed by D1-D10 observations.
- [x] No secrets were added to this report or registry. D0 gitignored `discovery/samples/`, `.env`, `.venv/`, and `__pycache__/`; raw payloads remain under the sample path by convention.
- [x] `co-op.md` log is updated for D11.

Gap: Codex did not run git, per the standing co-op rule. Claude still owns commit verification.

## Recommendations to Claude

### Drop

- **Drop D3 SPI from the sourceable benchmark path.** Current documented public endpoints do not serve parseable CSVs: GitHub raw paths returned 404 and legacy project URLs returned ABC News HTML.
- **Do not ingest external ratings feeds yet.** D8 selected no FIFA, World Football Elo, Kaggle, or GitHub mirror because documented access/reuse rights were insufficient.
- **Do not automate publisher RSS, FIFA/UEFA news, or social raw text ingestion.** D9 and D10 support metadata/aggregate-only Phase 3 experiments, not raw-content datasets.

### Promote

- **Promote D1 martj42 and D2 openfootball to P2 ingestion planning.** They are the only Milestone-1 essentials.
- **Promote build-our-own-Elo as the first model bar.** Use D1 completed results, not external ranking feeds.
- **Promote D5 Polymarket to Phase 2 market benchmark.** It has broader-than-expected World Cup coverage: outright winner, individual matches, group advancement/winners, and exact scorelines.
- **Promote D4 Football-Data to Phase 2 odds benchmark with redistribution limits.** Its `WorldCup2026.xlsx` is useful, but raw files should stay local/gitignored unless Claude approves terms handling.
- **Keep D6 The Odds API as optional Phase 2 live odds only behind a key, quota guard, and request allowlist.**

### Surprises

- SPI is effectively dead from current public endpoints, not merely frozen.
- Polymarket coverage is full enough to be a serious market-implied benchmark: 431 events and 10,573 markets in the active World Cup tag crawl.
- Football-Data has a real World Cup workbook with 2026 tournament rows and 889 qualifier rows, not just club leagues.
- There is no clean selected external Elo/rating feed, which makes the reproducible D1-derived Elo path the right default.
- GDELT is the only surveyed news option selected for possible Phase 3 programmatic metadata, but even it needs narrow queries and rate limiting because a broad query hit HTTP 429.

### Decisions Needed Before P2

- Define the team alias table seeded by D2: at minimum `Bosnia & Herzegovina` and `USA`, plus FIFA display-name variants such as `Korea Republic`, `IR Iran`, `Cabo Verde`, `Congo DR`, `Cote d'Ivoire`, `Czechia`, and `Turkiye`.
- Decide the ingestion contract for D1's fixtures-vs-results split: completed-score rows for model labels, blank-score future rows as fixtures only.
- Specify Polymarket de-vig rules before using market prices as calibrated probabilities. Binary markets sum to 1.0 in D5, but event-level mutually exclusive Yes prices can have overround, including World Cup Winner Yes prices summing to 1.029.
- Decide how P2 handles Football-Data's non-CC0 posture: keep raw files local/gitignored, avoid redistribution, and encode per-file column maps for club CSVs vs World Cup workbooks.
- Decide whether P2 needs `THE_ODDS_API_KEY`; if yes, define the monthly credit budget, minimum poll interval, region/market allowlist, and no-key logging rules.
- Confirm that news/social remain Phase 3 deferred and outside the probability path until compliance, leakage controls, and aggregate-only tests exist.
