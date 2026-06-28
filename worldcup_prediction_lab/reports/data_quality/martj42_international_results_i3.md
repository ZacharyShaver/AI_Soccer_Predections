# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-06-28T13:55:52Z`
- Raw SHA-256: `a30f5a34fd339d67563289e1ef745028663f5f12b2aad6eba7765efc5bc6823e`
- Total source rows: 49,493
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,493
- Completed matches after dedupe: 49,477
- Blank-score fixtures: 16
- Completed match date range: 1872-11-30 to 2026-06-27
- Fixture date range: 2026-06-28 to 2026-07-03
- All-row date range after dedupe: 1872-11-30 to 2026-07-03
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,385
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
