# Q1 Football-Data market odds data quality

- Source: `https://www.football-data.co.uk/WorldCup2026.xlsx`
- Ingest UTC: `2026-06-22T11:29:32Z`
- Raw SHA-256: `f0ed32638c18b86e3473a1454ac0abc47135bfce0b02d24ed3f62aeec399f4ea`
- Total normalized odds rows: 1,098
- Distinct matches: 1,098
- Date range: 2014-06-12 to 2026-06-18
- Unmatched team-name count: 160
- Rows skipped for missing odds: 0
- Rows skipped for invalid odds: 7
- Rows skipped for missing required fields/schema: 0

Rows per workbook sheet:
- WorldCup2014: 64 source rows; 64 normalized odds rows
- WorldCup2018: 64 source rows; 64 normalized odds rows
- WorldCup2022: 64 source rows; 64 normalized odds rows
- WorldCup2026: 24 source rows; 24 normalized odds rows
- WorldCup2026Qualifiers: 889 source rows; 882 normalized odds rows

Unmatched team names are retained with null canonical ids so ingestion does not
silently drop historical matches. Q2 can either map these aliases or filter to
resolved matches before joining to Elo predictions.
