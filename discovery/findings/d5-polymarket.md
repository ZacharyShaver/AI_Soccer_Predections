# Source: Polymarket public market data (polymarket)

- **Reachable:** yes
- **Access method:** public REST via Polymarket Gamma API
- **Auth required:** none
- **requires_secret:** false
- **License / terms URL:** https://docs.polymarket.com/market-data/overview, https://docs.polymarket.com/market-data/fetching-markets, and https://polymarket.com/terms
- **Allowed use (1 line):** Polymarket documents market-data REST endpoints as public/no-auth; use snapshots as public market-derived signals while respecting Polymarket terms and preserving timestamp/provenance.
- **Endpoint(s) / URL(s) probed:**
  - `https://gamma-api.polymarket.com/sports`
  - `https://gamma-api.polymarket.com/public-search?q=World+Cup`
  - `https://gamma-api.polymarket.com/public-search?q=FIFA`
  - `https://gamma-api.polymarket.com/events?tag_id=102232&limit=100&offset=0&active=true&closed=false&order=volume&ascending=false`
  - Same events query with offsets `100`, `200`, `300`, and `400`.
- **Schema (key columns/fields):**
  - Event fields seen: `id`, `title`, `slug`, `active`, `closed`, `endDate`, `volume`, `openInterest`, `volume24hr`, `volume1wk`, `volume1mo`, `volume1yr`, `liquidity`, `liquidityClob`, `enableOrderBook`, `negRisk`, and nested `markets`.
  - Market fields seen: `id`, `question`, `slug`, `outcomes`, `outcomePrices`, `volume`, `volumeNum`, `volume24hr`, `volume1wk`, `volume1mo`, `volume1yr`, `volumeClob`, `liquidity`, `liquidityNum`, `liquidityClob`, `bestBid`, `bestAsk`, `lastTradePrice`, `enableOrderBook`, and `acceptingOrders`.
  - `outcomes` and `outcomePrices` are usually JSON-encoded arrays in string fields, for example `["Yes", "No"]` and `["0.1425", "0.8575"]`.
- **Row / record count in sample:** Active open FIFA World Cup tag `102232` returned 431 events and 10,573 nested markets across five paged event requests. Public search cross-check returned first pages only but reported `World Cup` totalResults=1,168 and `FIFA` totalResults=849.
- **Date range / freshness (latest record date):** Probe generated at 2026-06-21T18:47:31+00:00. The saved `World Cup Winner` event was created 2025-07-02, updated 2026-06-21T18:47:26.214429Z, and ends 2026-07-20.
- **Frozen?** no - this is live market data and prices/liquidity move over time.
- **2026 World Cup relevance:** high for market-implied Phase 2 signals. Coverage found:
  - Outright tournament winner: exists, 1 event / 60 markets. Sample: `World Cup Winner`, volume 2,838,846,548.77629, liquidity 550,789,852.90149.
  - Individual match results: exists, 35 events / 105 markets. Samples include `Belgium vs. IR Iran` with 3 markets, volume 5,585,254.013978046, liquidity 9,278,266.3835.
  - Group winners / advancement: exists, 11 events / 98 markets. Samples include `World Cup: Team to advance to Knockout Stages` with 48 markets and multiple `World Cup Group <letter> Winner` events.
  - Exact scorelines: exists, 35 events / 595 markets. Samples include `Belgium vs. IR Iran - Exact Score` with 17 markets, volume 994,483.4537299996, liquidity 4,027,545.50346.
- **Gotchas:** HTTP 200 was not trusted until `content-type: application/json` and top-level JSON shape were validated. `outcomes` / `outcomePrices` may be JSON strings, not native arrays. 10,323 markets had valid numeric `outcomePrices`; 250 markets were missing or had null/invalid `outcomePrices`, mostly placeholder/zero-liquidity markets such as `Will Team AM win the 2026 FIFA World Cup?`. Every valid market's outcome-price array summed to exactly 1.0 in this probe (`min=1.0`, `max=1.0`), so binary Yes/No markets are already normalized at the market level. Event-level mutually exclusive Yes prices are close but not always exactly 1.0 (`World Cup Winner` priced Yes sum 1.029 across 52 priced markets; `Belgium vs. IR Iran` 1.005; `Uruguay vs. Cabo Verde` 0.995). Do not sum event-level Yes prices for non-exclusive prop/advancement groups.
- **Recommended phase:** 2
- **Retention recommendation:** raw_retention_days=7, bronze_retention_days=3650. Raw Gamma responses are large and quickly stale; normalized snapshots should keep `observed_at`, endpoint URL, event/market IDs, prices, bid/ask, liquidity, and volume.
- **Sample saved at:** raw samples `discovery/samples/polymarket/sample-event-world-cup-winner.json` and `discovery/samples/polymarket/probe-output.json`; committed excerpt `discovery/findings/d5-polymarket-event-excerpt.json`
- **Status:** usable with caveats

## Probe output highlights

- Required command passed: `uv run --with httpx python discovery/probes/probe_polymarket.py`
- Because Windows denied `uv`'s default cache path, the command was run with `UV_CACHE_DIR=C:\Users\ztsha\.codex\memories\uv-cache`; no source data or secrets were written there.
- `/sports` exposed World Cup sport metadata `sport=fifwc`, `series=11433`, and tags `1, 100639, 100350, 102232`; tag `102232` was used for the active event crawl.
- Event crawl page sizes: offset `0` = 100 events, `100` = 100, `200` = 100, `300` = 100, `400` = 31.
- Saved raw sample SHA-256 for `sample-event-world-cup-winner.json`: `b38f308403f80d4e51c3997eb53658eafe8163fe3ca00b0f3e78e4322de48bde`.
