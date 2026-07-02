# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-01T13:00:03Z`
- Raw SHA-256: `4f7e81ff3dd8875c265d099de860ba8e34f8f7b6efc353d0212e4b1569c1461e`
- Total source rows: 49,496
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,496
- Completed matches after dedupe: 49,484
- Blank-score fixtures: 12
- Completed match date range: 1872-11-30 to 2026-06-30
- Fixture date range: 2026-07-01 to 2026-07-05
- All-row date range after dedupe: 1872-11-30 to 2026-07-05
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,392
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
