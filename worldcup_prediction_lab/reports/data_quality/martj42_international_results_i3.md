# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-09T13:00:04Z`
- Raw SHA-256: `b58624fd0b746f8fb1542633c4a4914a3f396394eb2ab71424c263825f5cded6`
- Total source rows: 49,505
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,505
- Completed matches after dedupe: 49,501
- Blank-score fixtures: 4
- Completed match date range: 1872-11-30 to 2026-07-07
- Fixture date range: 2026-07-09 to 2026-07-11
- All-row date range after dedupe: 1872-11-30 to 2026-07-11
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,409
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
