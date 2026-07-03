# I3 martj42 international results data quality

- Source: `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- Ingest UTC: `2026-07-03T11:01:19Z`
- Raw SHA-256: `f9ef115176f9827c653a7141717e06af20fd70463d30c3f3d560d73e81a07156`
- Total source rows: 49,499
- Exact-identical duplicate rows dropped: 0
- Rows after exact dedupe: 49,499
- Completed matches after dedupe: 49,490
- Blank-score fixtures: 9
- Completed match date range: 1872-11-30 to 2026-07-02
- Fixture date range: 2026-07-03 to 2026-07-06
- All-row date range after dedupe: 1872-11-30 to 2026-07-06
- Multi-match same-day natural-key groups: 1
- Distinct canonical teams: 336
- Auto-registered martj42 teams: 129
- Completed matches in 2025-2026: 1,398
- Match ID unique across silver matches: True
- Contains 2025 completed matches: True
- Contains 2026 completed matches: True

Natural-key duplicates are not rejected. They are retained as legitimate double-headers
when the score or another source field differs, with `occurrence_index` assigned by
original source row order and `match_id` asserted unique.
