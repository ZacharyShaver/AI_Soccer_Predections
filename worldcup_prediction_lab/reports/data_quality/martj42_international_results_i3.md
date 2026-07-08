# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-07T13:00:04Z`
- Raw SHA-256: `3dee8298021fb4e1fa497df06feecbbe0973d8bff109358f40f7f6f20dfcb580`
- Total source rows: 49,504
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,504
- Completed matches after dedupe: 49,499
- Blank-score fixtures: 5
- Completed match date range: 1872-11-30 to 2026-07-06
- Fixture date range: 2026-07-06 to 2026-07-11
- All-row date range after dedupe: 1872-11-30 to 2026-07-11
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,407
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
