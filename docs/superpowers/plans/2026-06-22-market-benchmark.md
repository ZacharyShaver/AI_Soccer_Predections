# Plan P6: Market Benchmark (Elo vs the market)

> The real competitiveness test: how does our Elo compare to bookmaker / prediction-market
> implied probabilities? Built on P3 (Elo + metrics + backtest). Codex builds; Claude reviews/commits.

## Why

Markets aggregate everyone's information (including injuries and lineups), so market-implied
probabilities are the strongest realistic benchmark. Two questions:
1. **Historical:** does Elo match/beat the bookmaker on past matches where we have odds?
2. **Live:** where does our current 2026 Elo forecast disagree with the market right now?

## Sources (from discovery; both NOT CC0 / quota-aware)

- **Football-Data.co.uk** (D4): historical odds incl `WorldCup2026.xlsx` (2026 + qualifiers +
  WC sheets 2014/2018/2022). **Raw files stay local/gitignored, never redistributed.** Different
  odds column naming per file (club `B365H` vs WC `bet365-H`).
- **Polymarket Gamma** (D5): live 2026 market prices, public no-auth. Outcome prices carry overround
  (~2.9% on outright) → **de-vig required**. `outcomes`/`outcomePrices` are JSON strings.
- The Odds API (D6): optional/keyed/quota-limited — out of scope unless a key exists; skip gracefully.

## Constraints (locked)

- De-vig before any comparison: bookmaker decimal odds → implied → remove margin (normalize the
  home/draw/away book to sum 1). Document the de-vig method (proportional/Shin optional later).
- Raw Football-Data files gitignored; only committed = code, tests, small schema samples, reports.
- Point-in-time honesty: compare market vs Elo on the SAME matches; for historical, use closing/
  pre-match odds only. Predictions-not-labels.

## Outputs

- `src/wc_predictor/data/devig.py` (+ tests) — odds → no-vig probabilities.
- `src/wc_predictor/data/ingest_footballdata.py` (+ tests) — historical WC/qualifier odds → silver.
- `reports/backtests/elo_vs_market.md` — historical Elo-vs-bookmaker comparison.
- `src/wc_predictor/data/ingest_polymarket.py` (+ tests) + `reports/backtests/market_disagreement_2026-06-21.md`
  — live market vs current Elo forecast.

---

## Task Q0: De-vig utility

**Files:** `src/wc_predictor/data/devig.py`, `tests/data/test_devig.py`.

- [x] **Step 1: Tests first** — known odds → known no-vig probabilities. Cover: 3-way decimal odds
  (home/draw/away) with a margin → probabilities sum to 1 and preserve relative order; a fair book
  (no margin) is unchanged; Polymarket-style outcome prices (already ~probabilities, but a mutually-
  exclusive set with overround) → normalized to sum 1; reject malformed/zero odds.
- [x] **Step 2: Implement** `implied_from_decimal(odds)`, `remove_vig(probs)` (proportional
  normalization), and a `no_vig_three_way(home_odds, draw_odds, away_odds)` convenience. Pure funcs.
- [x] **Step 3: Run tests; Claude commits.**

---

## Task Q1: Football-Data historical odds ingestion

**Files:** `src/wc_predictor/data/ingest_footballdata.py`, `tests/data/test_ingest_footballdata.py`.

- [x] **Step 1: Tests first** — parse a small embedded sample of both the WC workbook schema
  (`bet365-H/D/A`) and (optionally) a club CSV schema (`B365H/D/A`); map to a common odds shape;
  apply Q0 de-vig. Offline/deterministic.
- [x] **Step 2: Implement** download of `WorldCup2026.xlsx` (WC 2014/2018/2022 + qualifiers sheets)
  to gitignored `data/raw/footballdata/`; parse to a silver `market_odds` table keyed by
  (date, home_team_id, away_team_id, bookmaker) with no-vig home/draw/away. Resolve team names via
  the I2 alias resolver; report unmatched names. Raw files stay local; commit only a tiny schema
  sample + the code.
- [x] **Step 3: DQ + commit** — row counts, date coverage, unmatched-name count to a DQ report.

---

## Task Q2: Historical Elo-vs-market backtest

**Files:** `src/wc_predictor/evaluation/elo_vs_market.py`, `reports/backtests/elo_vs_market.md`.

- [x] **Step 1: Align** matches that have BOTH a silver result and Football-Data no-vig odds
  (historical WC + qualifiers). For each, get the Elo prediction (train Elo on results strictly
  before the match date — reuse walk-forward / as-of training to avoid leakage).
- [x] **Step 2: Compare** market-implied vs Elo on RPS / H-D-A log loss / Brier, with bootstrap CIs
  and the paired mean-difference (market minus Elo). Honest verdict: does Elo match the market, lose
  a little, or beat it? (Prior: market is hard to beat; measuring the gap is the value.)
- [x] **Step 3: Write report + commit.**

---

## Task Q3: Live market vs current Elo forecast

**Files:** `src/wc_predictor/data/ingest_polymarket.py`,
`reports/backtests/market_disagreement_2026-06-21.md`.

- [x] **Step 1: Tests first** — parse a Polymarket event fixture (`outcomes`/`outcomePrices` as JSON
  strings), filter null/placeholder prices, de-vig the mutually-exclusive market (Q0). Offline.
- [x] **Step 2: Fetch** current 2026 WC match markets from the public Gamma API (no key); map to
  fixtures via the alias resolver; de-vig to home/draw/away (or match-winner) probabilities.
- [x] **Step 3: Compare** to the M7 live Elo forecast per remaining match; report the biggest
  disagreements (where Elo and the market most differ) with a short interpretation. Commit.

---

## Definition of done for P6

- De-vig utility + tests; Football-Data historical odds in silver (raw local-only); Polymarket live
  ingestion + tests.
- `elo_vs_market.md` (historical, paired CIs) + `market_disagreement_2026-06-21.md` (live).
- No secrets; raw odds payloads gitignored; full suite green.
- co-op.md updated; Claude reviews before P7.
