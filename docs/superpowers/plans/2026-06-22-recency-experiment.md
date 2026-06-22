# Plan P5: Recency Experiment (ship-of-Theseus test)

> Does down-weighting old matches improve Elo, or does sparse international data
> need the full history? Settle it empirically on the M6 walk-forward backtest.
> Built on P3 (Elo + backtest + metrics). Claude building directly while Codex is out.

## Hypothesis (Zach's)

A team is a ship of Theseus — results from 4-10 years ago may not reflect today's
side, so maybe only the last 1-2 years should count. Counter-prior (from the
comparator research): international teams play ~10 matches/year, so a hard short
window starves the model and loses the cross-linking that calibrates ratings;
Elo's K-factor already down-weights old results recursively. **Let the backtest decide.**

## Variants (all scored on the same M6 walk-forward window)

- `full_history_k20` — baseline (current default, K=20). M6 reference RPS 0.1776.
- `high_k40`, `high_k30` — faster recency (recent matches move ratings more).
- `low_k10` — slower (more weight on history), for contrast.
- `window_8y`, `window_4y`, `window_2y` — hard trailing windows (the literal hypothesis).

## Method

Run each variant through `run_backtest` (P3/M2) over the M6 window (train_start
1990-01-01, first_prediction 2010-01-01, final 2026-06-10, 30-day windows). Score
RPS / H-D-A log loss / Brier with bootstrap CIs, and compute the **paired
mean-difference vs `full_history_k20`** with a bootstrap CI (the real test of
whether a variant beats the baseline beyond noise). Honest verdict; no cherry-picking.

---

## Task R0: Windowed Elo model

**Files:** `src/wc_predictor/models/elo_windowed.py`, `tests/models/test_elo_windowed.py`.

- [ ] **Step 1: Tests first**

`WindowedEloModel(window_years=N)` trims its training set to the trailing N years
before the latest training date, then behaves like Elo. Assert: matches older than
the window do NOT affect ratings (a team whose only old results fall outside the
window reverts toward base); within-window behaviour matches `EloModel`; respects
the model protocol (fit / predict_match / predict_scoreline).

- [ ] **Step 2: Implement**

Subclass `EloModel`; override `fit` to filter `train_matches_df` to
`date >= max(date) - window_years` before the standard sequential update.

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task R1: Run experiment + report

**Files:** `src/wc_predictor/evaluation/recency_experiment.py`,
`reports/backtests/recency_experiment.md`.

- [ ] **Step 1: Run all variants** through the M6 walk-forward window; collect
  per-match metric arrays. (Background run — multi-variant backtest is slow.)

- [ ] **Step 2: Score + paired comparison** — per-variant RPS/log loss/Brier with
  bootstrap CIs, and paired mean-difference vs `full_history_k20` with CIs. Determine
  which (if any) variant beats the baseline beyond noise.

- [ ] **Step 3: Write the committed report** with the table, paired verdicts, and a
  plain-English conclusion on the ship-of-Theseus hypothesis. Commit.

---

## Definition of done for P5

- `WindowedEloModel` + tests; full suite green.
- `recency_experiment.md` with per-variant metrics, paired CIs vs baseline, and an
  honest verdict on whether recency-weighting / short windows beat full-history Elo.
- co-op.md updated; Claude reviews before P6.
