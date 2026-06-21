# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-06-21T21:24:35Z`
- Raw SHA-256: `ceba28c9203f1ad6ebdd926d6eda26b48b0f605d25c74accaa6920cf77167b67`
- Total source rows: 49,477
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,477
- Completed matches after dedupe: 49,441
- Blank-score fixtures: 36
- Completed match date range: 1872-11-30 to 2026-06-20
- Fixture date range: 2026-06-21 to 2026-06-27
- All-row date range after dedupe: 1872-11-30 to 2026-06-27
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 288
- Completed matches in 2025-2026: 1,349
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
