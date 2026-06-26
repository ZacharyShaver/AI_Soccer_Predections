# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-06-26T13:00:04Z`
- Raw SHA-256: `a2efa2b9e280a40d58e7d9272bd6e34a181436efda718022cc2c2e9430727106`
- Total source rows: 49,477
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,477
- Completed matches after dedupe: 49,465
- Blank-score fixtures: 12
- Completed match date range: 1872-11-30 to 2026-06-25
- Fixture date range: 2026-06-26 to 2026-06-27
- All-row date range after dedupe: 1872-11-30 to 2026-06-27
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 288
- Completed matches in 2025-2026: 1,373
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
