# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-04T20:06:50Z`
- Raw SHA-256: `bcf26ebc26bd911fd8e68009c8606aa2cca09a52bde4cf739bdbddfadb014f49`
- Total source rows: 49,501
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,501
- Completed matches after dedupe: 49,493
- Blank-score fixtures: 8
- Completed match date range: 1872-11-30 to 2026-07-03
- Fixture date range: 2026-07-04 to 2026-07-06
- All-row date range after dedupe: 1872-11-30 to 2026-07-06
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,401
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
