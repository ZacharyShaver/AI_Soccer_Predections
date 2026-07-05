# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-05T15:07:43Z`
- Raw SHA-256: `c211656dc8a64d61f2efeb6aa5427ea8b823acf16f619264988ea552e9cee1dc`
- Total source rows: 49,502
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,502
- Completed matches after dedupe: 49,495
- Blank-score fixtures: 7
- Completed match date range: 1872-11-30 to 2026-07-04
- Fixture date range: 2026-07-05 to 2026-07-09
- All-row date range after dedupe: 1872-11-30 to 2026-07-09
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,403
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
