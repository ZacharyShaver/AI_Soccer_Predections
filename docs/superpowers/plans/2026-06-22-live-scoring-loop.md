# Plan P7: Live Scoring Loop

> Turn the lab into a living tournament system: as matches finish, score our ledger forecasts
> against reality, refresh ratings + forecasts for upcoming matches, and keep a running scorecard
> (us vs the market vs actual). Built on P3 (ledger/metrics/forecast) + P4 (odds) + P6 (market).
> Codex builds; Claude reviews/commits.

## Why

The World Cup is in progress. We have an immutable forecast ledger (M7, as-of 2026-06-21) but no
mechanism to (a) score those forecasts once results land, (b) pull new results and re-forecast the
remaining matches, or (c) track how we're doing over time vs the market. P7 closes that loop.

## Constraints (locked)

- **Immutability:** new forecasts go to NEW `runs/predictions/date=<as_of>/` partitions; never
  overwrite or mutate a prior prediction. Scoring joins results to predictions without changing them
  (predictions-not-labels).
- **As-of discipline:** every refresh records `as_of` + `training_cutoff`; only forecast matches with
  `match_date > as_of`; train only on results `<= training_cutoff`.
- **Determinism:** fixed seeds; canonical-JSON 6-dp prediction hashes; re-running a given as-of is
  idempotent (byte-identical predictions).
- Raw/runs payloads gitignored; reports + code committed. No tournament-only recalibration (the >=200
  floor from the master plan stays).

## Outputs

- `src/wc_predictor/evaluation/score_ledger.py` (+ tests) — score stored forecasts vs results.
- `src/wc_predictor/run_daily_update.py` (+ tests) — one-command refresh: ingest → retrain →
  re-forecast → refresh odds, all as-of-aware and immutable.
- `reports/backtests/forecast_scorecard.md` — running scorecard (our forecasts vs market vs actual).

---

## Task L0: Ledger scoring

**Files:** `src/wc_predictor/evaluation/score_ledger.py`, `tests/evaluation/test_score_ledger.py`.

- [x] **Step 1: Tests first** — given stored predictions (JSONL) and a results table, score each
  now-completed prediction (home/draw/away outcome) with log loss, Brier, RPS, and a "called it"
  (argmax) flag, WITHOUT mutating the prediction rows. Predictions for not-yet-played matches are
  left unscored. Deterministic.
- [x] **Step 2: Implement** `score_ledger(predictions_dir_or_jsonl, results_df)` reusing the M0
  `score_predictions` join + M1 metrics. Return a per-prediction evaluation table + aggregate
  (n scored, mean log loss/Brier/RPS, outcome accuracy on decisive matches, exact-score hits if a
  scoreline was stored).
- [x] **Step 3: Run tests; Claude commits.**

---

## Task L1: Daily refresh orchestrator

**Files:** `src/wc_predictor/run_daily_update.py`, `tests/test_run_daily_update.py`.

- [ ] **Step 1: Tests first** — on a small synthetic setup, assert the orchestrator: (a) writes
  forecasts only for matches after `as_of`; (b) is idempotent (re-running the same `as_of` produces
  byte-identical ledger rows, no duplicates); (c) does NOT overwrite a prior `as_of` partition;
  (d) records `as_of`/`training_cutoff` metadata.
- [ ] **Step 2: Implement** `run_daily_update(as_of=None)` that, for the given/today as-of:
  re-ingests latest martj42 results (reuse I3; network), retrains host-aware Elo through the latest
  completed date, regenerates forecasts for remaining fixtures (reuse forecast_live) into a new
  ledger partition, and refreshes championship odds (reuse P4). Skips gracefully if no new results.
- [ ] **Step 3: Run tests; Claude commits.**

---

## Task L2: Running scorecard (us vs market vs actual)

**Files:** extend `score_ledger.py` or add `src/wc_predictor/evaluation/scorecard.py`,
`reports/backtests/forecast_scorecard.md`.

- [ ] **Step 1: Build the scorecard** — across all scored ledger predictions to date, compare our
  Elo forecasts to actual outcomes and, where available, to the de-vigged Polymarket/Football-Data
  market probs on the same matches (reuse P6). Report per-metric (RPS/log loss/Brier) for us vs
  market, with bootstrap CIs once n is large enough (note when n is too small).
- [ ] **Step 2: Write the committed report** `forecast_scorecard.md`: matches scored so far, our
  running metrics, market comparison, notable hits/misses, and honest caveats (small in-tournament
  n; don't over-read a handful of matches).
- [ ] **Step 3: Commit.**

---

## Definition of done for P7

- Ledger scoring + daily refresh orchestrator + running scorecard, each tested; full suite green.
- Refresh is idempotent and immutability-preserving; as-of/training-cutoff recorded.
- `forecast_scorecard.md` shows how our live forecasts are doing vs actual (and vs market where
  available), with honest small-sample caveats.
- No secrets; raw/runs payloads gitignored. co-op.md updated. **Completes the P4–P7 roadmap.**
