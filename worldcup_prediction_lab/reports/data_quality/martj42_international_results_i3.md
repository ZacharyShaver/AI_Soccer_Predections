# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-02T13:56:35Z`
- Raw SHA-256: `cfe48bd9b40e1ff662ecfe62864d1acb7f1f66e966010eed3f531c3c17760a4e`
- Total source rows: 49,498
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,498
- Completed matches after dedupe: 49,487
- Blank-score fixtures: 11
- Completed match date range: 1872-11-30 to 2026-07-01
- Fixture date range: 2026-07-02 to 2026-07-06
- All-row date range after dedupe: 1872-11-30 to 2026-07-06
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,395
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
