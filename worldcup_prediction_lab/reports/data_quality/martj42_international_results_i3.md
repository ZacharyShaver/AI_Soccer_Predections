# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-06T13:00:06Z`
- Raw SHA-256: `c268d1583c0ac4e2e6ec4452a1d3baf61fa8ead60c13ce6f785256a82c5dc8a2`
- Total source rows: 49,503
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,503
- Completed matches after dedupe: 49,497
- Blank-score fixtures: 6
- Completed match date range: 1872-11-30 to 2026-07-05
- Fixture date range: 2026-07-06 to 2026-07-11
- All-row date range after dedupe: 1872-11-30 to 2026-07-11
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,405
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
