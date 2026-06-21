# Source: Football-Data.co.uk odds (footballdata)

- **Reachable:** yes
- **Access method:** public HTML index pages plus public CSV/XLSX files
- **Auth required:** none
- **License / terms URL:** https://www.football-data.co.uk/data.php and https://www.football-data.co.uk/notes.txt
- **Allowed use (1 line):** Football-Data describes the files as free and computer-ready for spreadsheet/model testing, but I did not find a CC-style open license; keep provenance, avoid raw redistribution, and treat as a caveated benchmark/source-schema reference.
- **Endpoint(s) / URL(s) probed:**
  - https://www.football-data.co.uk/data.php
  - https://www.football-data.co.uk/downloadm.php
  - https://www.football-data.co.uk/all_new_data.php
  - https://www.football-data.co.uk/englandm.php
  - https://www.football-data.co.uk/notes.txt
  - https://www.football-data.co.uk/WorldCup2026.xlsx
  - https://www.football-data.co.uk/mmz4281/2526/E0.csv
- **Schema (key columns/fields):**
  - Current English Premier League CSV sample `E0.csv`: `Div`, `Date`, `Time`, `HomeTeam`, `AwayTeam`, score/result columns, match-stat columns, bookmaker home/draw/away odds such as `B365H`, `B365D`, `B365A`, market maximum/average odds `MaxH`, `MaxD`, `MaxA`, `AvgH`, `AvgD`, `AvgA`, exchange odds `BFEH`, `BFED`, `BFEA`, over/under columns, Asian handicap columns, and closing odds columns such as `B365CH`, `B365CD`, `B365CA`, `MaxCH`, `MaxCD`, `MaxCA`, `AvgCH`, `AvgCD`, `AvgCA`.
  - World Cup workbook `WorldCup2026.xlsx`: sheets `WorldCup2026`, `WorldCup2026Qualifiers`, `WorldCup2022`, `WorldCup2018`, `WorldCup2014`. Main tournament sheets include `Competition`, `Home`, `Away`, `Date`, `Time`, score/result/stat columns, and odds columns such as `bet365-H`, `bet365-D`, `bet365-A`, `Betfair_Exch-H`, `Betfair_Exch-D`, `Betfair_Exch-A`, `H-Max`, `D-Max`, `A-Max`, `H-Avg`, `D-Avg`, `A-Avg`.
- **Row / record count in sample:** `E0-2526.csv` parsed as 380 rows and 132 columns. `WorldCup2026.xlsx` parsed with openpyxl: `WorldCup2026` 24 rows / 42 columns, `WorldCup2026Qualifiers` 889 rows / 25 columns, `WorldCup2022` 64 rows / 40 columns, `WorldCup2018` 64 rows / 37 columns, `WorldCup2014` 64 rows / 40 columns.
- **Date range / freshness (latest record date):** `E0-2526.csv` spans 2025-08-15 to 2026-05-24. `WorldCup2026` spans 2026-06-11 to 2026-06-18; `WorldCup2026Qualifiers` spans 2023-09-07 to 2026-04-01; historical World Cup sheets span 2014-06-12 to 2022-12-18 depending on sheet.
- **Frozen?** no - current league and World Cup files are live public files, but they are snapshot-style downloads rather than a documented API.
- **2026 World Cup relevance:** medium - Football-Data is still primarily club/domestic league oriented (27 documented country-league pages plus current/historical league CSV/XLSX files), but it does have a documented `WorldCup2026.xlsx` workbook with 2026 tournament rows, 2026 qualifiers, and historical World Cup sheets back to 2014. Use it as an odds/stat benchmark and schema reference, not as the primary fixture or results source.
- **Gotchas:** A HTTP 200 was validated by content type and header/magic bytes before parsing. The main league CSV and World Cup workbook use different odds column naming (`B365H/B365D/B365A` vs `bet365-H/bet365-D/bet365-A`). Club CSVs include closing odds with `C` in the heading; the World Cup workbook sheets probed did not expose closing home/draw/away columns. Football-Data notes that Pinnacle public API odds became unreliable after 2025-07-23, so Pinnacle-derived columns need caution. Terms are not as permissive/explicit as CC0 sources.
- **Recommended phase:** 2
- **Retention recommendation:** raw_retention_days=30, bronze_retention_days=3650; do not redistribute raw files outside local discovery/ingestion without a separate terms decision.
- **Sample saved at:** raw samples `discovery/samples/footballdata/E0-2526.csv` and `discovery/samples/footballdata/WorldCup2026.xlsx`; committed schema samples `discovery/findings/d4-footballdata-e0-2526-schema-sample.csv` and `discovery/findings/d4-footballdata-worldcup2026-schema-sample.csv`
- **Status:** usable with caveats

## Probe output highlights

- Required command passed: `uv run --with httpx --with pandas --with openpyxl python discovery/probes/probe_footballdata.py`
- Official coverage pages returned parseable HTML/text: `data.php`, `downloadm.php`, `all_new_data.php`, `englandm.php`, and `notes.txt`.
- Coverage survey found 27 normalized domestic country-league pages and 1 documented World Cup workbook link: `https://www.football-data.co.uk/WorldCup2026.xlsx`.
- `WorldCup2026.xlsx` returned HTTP 200 with XLSX content type/magic bytes and parsed successfully through `openpyxl`.
- `E0.csv` returned HTTP 200 with `text/csv`; header validation confirmed `Div,Date,...` before `pandas.read_csv`.
