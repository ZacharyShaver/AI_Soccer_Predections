# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-06-29T13:00:05Z`
- Raw SHA-256: `df6a30676640fc647f2af51d387765996f75c7cda10d70d7c81ef9180c23df08`
- Total source rows: 49,493
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,493
- Completed matches after dedupe: 49,478
- Blank-score fixtures: 15
- Completed match date range: 1872-11-30 to 2026-06-28
- Fixture date range: 2026-06-29 to 2026-07-03
- All-row date range after dedupe: 1872-11-30 to 2026-07-03
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,386
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
