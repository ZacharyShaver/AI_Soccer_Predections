# Source: FiveThirtyEight SPI international soccer (spi)

- **Reachable:** partial
- **Access method:** public file links documented by the `fivethirtyeight/data` GitHub repo plus legacy FiveThirtyEight project URLs
- **Auth required:** none
- **License / terms URL:** https://github.com/fivethirtyeight/data/blob/master/LICENSE
- **Allowed use (1 line):** FiveThirtyEight data repo license is CC BY 4.0; keep attribution and source provenance if any usable CSV is later recovered.
- **Endpoint(s) / URL(s) probed:**
  - https://api.github.com/repos/fivethirtyeight/data/contents/soccer-spi - HTTP 200; current directory contains `README.md` only, not the documented CSV files.
  - https://raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/README.md - HTTP 200; documents the legacy soccer API CSV URLs.
  - https://raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/spi_matches_intl.csv - HTTP 404.
  - https://raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/spi_global_rankings_intl.csv - HTTP 404.
  - https://raw.githubusercontent.com/fivethirtyeight/data/main/soccer-spi/spi_matches_intl.csv - HTTP 404.
  - https://raw.githubusercontent.com/fivethirtyeight/data/main/soccer-spi/spi_global_rankings_intl.csv - HTTP 404.
  - https://projects.fivethirtyeight.com/soccer-api/international/spi_matches_intl.csv - HTTP 200 but final URL is `https://abcnews.com/politics`, content type `text/html; charset=utf-8`, not CSV.
  - https://projects.fivethirtyeight.com/soccer-api/international/spi_global_rankings_intl.csv - HTTP 200 but final URL is `https://abcnews.com/politics`, content type `text/html; charset=utf-8`, not CSV.
  - https://projects.fivethirtyeight.com/soccer-api/international/spi_matches.csv - HTTP 200 but final URL is `https://abcnews.com/politics`, content type `text/html; charset=utf-8`, not CSV.
  - https://projects.fivethirtyeight.com/soccer-api/international/spi_global_rankings.csv - HTTP 200 but final URL is `https://abcnews.com/politics`, content type `text/html; charset=utf-8`, not CSV.
- **Schema (key columns/fields):** No parseable current CSV downloaded. The documented README says match files should contain `season`, `date`, `league_id`, `league`, `team1`, `team2`, `spi1`, `spi2`, `prob1`, `prob2`, `probtie`, projected score, importance, score, and xG-style fields; ranking files should contain `rank`, `prev_rank`, `name`, `league`, `off`, `def`, `spi`.
- **Row / record count in sample:** 0 parseable CSV rows downloaded. No schema sample was emitted because every CSV candidate either returned 404 or HTML.
- **Date range / freshness (latest record date):** Not verified. The current documented public endpoints did not provide parseable match or ranking rows, so the latest match/ranking date could not be measured.
- **Frozen?** yes - treat SPI as frozen/not live for planning, but date-based freeze verification is blocked because the documented CSV endpoints no longer return CSV data.
- **2026 World Cup relevance:** low - no current international SPI data could be downloaded, and the source must not be used for live 2026 paths.
- **Gotchas:** Legacy FiveThirtyEight URLs can return HTTP 200 while serving an ABC News HTML page after redirects; probes must validate content type/header rows and not assume status 200 means CSV. GitHub raw CSV URLs for both `master` and `main` return 404. The GitHub repo currently documents the CSV URLs in `README.md` but does not contain the CSV blobs in `soccer-spi`.
- **Recommended phase:** historical-benchmark only (not live)
- **Retention recommendation:** raw_retention_days=0 until a usable CSV is recovered; bronze_retention_days=3650 only for an approved historical benchmark snapshot.
- **Sample saved at:** `discovery/samples/spi/README.md`; no CSV raw sample or schema sample was saved.
- **Status:** blocked - no parseable current CSV available from documented public endpoints

## Probe output highlights

- Required command passed: `uv run --with httpx --with pandas python discovery/probes/probe_spi.py`
- `downloaded_csv_count`: 0
- `parseable_csvs_found`: false
- GitHub contents API names under `soccer-spi`: `README.md`
- Documented international CSVs present in current GitHub directory: `spi_matches_intl.csv=false`, `spi_global_rankings_intl.csv=false`
- Latest downloaded date: null
