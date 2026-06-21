# Plan P3: Elo-First Model Slice (Milestone 1 model)

> Bite-sized, Codex-executable slices of the master plan
> (`2026-06-21-world-cup-prediction-lab.md`), built on the **completed P2 data layer**
> (`worldcup_prediction_lab/reports/data_quality/INGESTION_REPORT.md`).
> One task per Codex session. Codex does NOT run git — Claude verifies and commits (see `co-op.md`).

## Scope and goal

Establish **plain calibrated Elo as the project's model bar**, proven by a **walk-forward
historical backtest** before any forecast is believed, then produce **live as-of-2026-06-21
forecasts** for the remaining World Cup fixtures.

Per the master plan's model ladder, Elo is expected to be the champion on sparse international data;
fancier rungs (Poisson attack/defense, Dixon-Coles, market, ML) are **falsification experiments for
later plans** and are OUT OF SCOPE here. P3 delivers: a deterministic prediction schema + immutable
ledger, evaluation metrics, a walk-forward backtest runner, a climatology baseline, the Elo model
(outcome + scoreline), the acceptance gate (Elo must beat climatology with statistical honesty), and
the first live forecast set.

**Framing decision (Zach, 2026-06-22): backtest first, then live.** Trust before forecasts.

## Inputs (pinned by INGESTION_REPORT.md)

- `data/silver/martj42_matches.parquet` — training labels + chronology. Columns: `match_id`, `date`,
  `home_team_id`, `away_team_id`, `home_team`, `away_team`, `home_score`, `away_score`, `tournament`,
  `city`, `country`, `neutral`, `source`, `occurrence_index`.
- `data/silver/martj42_teams.parquet` — team dimension: `canonical_team_id`, `canonical_name`,
  `source_team_name`, `source`, `auto_registered`.
- `data/silver/openfootball_worldcup_2026_fixtures.parquet` — forecasting target: `fixture_id`,
  `stage`, `group`, `home_team_id`, `away_team_id`, `home_slot`, `away_slot`, `match_date`, `venue`,
  `match_number`.
- These are gitignored; re-create locally by running the P2 ingestion if absent.

## Design constraints locked from prior phases (so Codex does not re-decide)

1. **Mid-tournament reality (I5).** WC is in progress as-of 2026-06-21. Every model run records
   `training_cutoff` and `as_of` in metadata. Backtest uses historical cutoffs; the live run uses
   `as_of=2026-06-21`, trains on completed matches through 2026-06-20, forecasts only remaining
   fixtures.
2. **Home advantage is NOT nominal home/away (I4).** WC matches are at neutral/host sites; martj42
   vs openfootball disagree on home/away order for 3 fixtures. Elo home-advantage must be driven by
   the `neutral` flag + host logic (USA/Canada/Mexico playing in their own country = host advantage),
   NOT by which column a team appears in for WC matches.
3. **Determinism (master plan).** Predictions serialize to canonical JSON (sorted keys, fixed
   separators), all probabilities rounded to 6 decimals, with a SHA-256 `prediction_hash`. Fixed RNG
   seeds. Re-running produces byte-identical hashes.
4. **Predictions are not labels.** Train only on actual results; never on predicted scores. The
   ledger is immutable.
5. **No tournament-only recalibration.** Calibration is fit on the full historical walk-forward set;
   in-tournament refresh only past a hard floor (>=200 scored matches in the window), else frozen.
6. **Acceptance gate.** Elo must beat `baseline_climatology` on walk-forward RPS, log loss, and
   Brier. Report confidence intervals / match counts alongside every gate metric — a 1–2% edge over
   ~100 matches is inside the noise and is NOT promotion evidence. Elo then becomes the bar future
   rungs must beat.

## Outputs

- `src/wc_predictor/models/base.py` (schemas) + `src/wc_predictor/evaluation/ledger.py` (+ tests).
- `src/wc_predictor/evaluation/metrics.py` + `backtest.py` (+ tests).
- `src/wc_predictor/models/baseline.py` (climatology) + `models/elo.py` (+ tests).
- `reports/backtests/` walk-forward report; `reports/model_cards/` for climatology + Elo.
- `runs/predictions/date=2026-06-21/predictions.jsonl` — live forecast ledger for remaining fixtures.

---

## Task M0: Prediction schema + immutable ledger

**Files:** `src/wc_predictor/models/base.py`, `src/wc_predictor/evaluation/ledger.py`,
`tests/evaluation/test_ledger.py`.

- [ ] **Step 1: Tests first — immutability + determinism**

Assert writing the same `prediction_id` twice fails UNLESS byte-identical. Assert canonical-JSON
serialization (sorted keys, fixed separators, probabilities rounded to 6 decimals) yields a stable
SHA-256 `prediction_hash` across re-serialization.

- [ ] **Step 2: Schemas**

Define `MatchPrediction` (incl `prediction_hash`, `model_id`, `model_version`, `generated_at_utc`,
`training_cutoff`, `as_of`, `home/draw/away` probs), `ScorelineDistribution` (per master plan:
`max_goals`, `home_expected_goals`, `away_expected_goals`, `probabilities`, `tail_probability`),
`ModelMetadata`, `FeatureSnapshotMetadata`. Probabilities sum to 1 within tolerance.

- [ ] **Step 3: Ledger writer + result-scoring join**

Write JSONL partitioned `runs/predictions/date=YYYY-MM-DD/predictions.jsonl`; never overwrite. A
separate join attaches actual results to stored predictions without mutating prediction rows.

- [ ] **Step 4: Run tests; Claude commits.**

---

## Task M1: Evaluation metrics

**Files:** `src/wc_predictor/evaluation/metrics.py`, `tests/evaluation/test_metrics.py`.

- [ ] **Step 1: Tests first — known vectors**

Use fixed probability vectors + outcomes with hand-computed expected values for `brier_score`,
`home_draw_away_log_loss`, `ranked_probability_score`, `exact_score_hit`, probability-sum checks.

- [ ] **Step 2: Implement metrics**

`scoreline_log_loss`, `home_draw_away_log_loss`, `brier_score`, `ranked_probability_score`,
`exact_score_hit`, `top_k_score_hit`, `expected_goals_mae`, `calibration_bins`. Include a helper for
bootstrap confidence intervals + n (for the acceptance gate's statistical-honesty requirement).

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task M2: Walk-forward backtest runner

**Files:** `src/wc_predictor/evaluation/backtest.py`, `tests/evaluation/test_backtest.py`.

- [ ] **Step 1: Leakage test first**

Synthetic matches: assert the training window strictly ends before the prediction window starts; a
match on date `D` never sees data dated `>= D`.

- [ ] **Step 2: Implement runner**

`run_backtest(train_start, first_prediction_date, final_prediction_date, prediction_window_days,
model_id) -> BacktestReport`. Walk-forward: train through T → predict next window → lock predictions
to the ledger → score after results → advance T. Records `training_cutoff`/`as_of` per window.

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task M3: Climatology baseline

**Files:** `src/wc_predictor/models/baseline.py`, `tests/models/test_baseline.py`.

- [ ] **Step 1: Tests first**

Probabilities sum to 1; scoreline matrix non-negative; fit uses only training rows.

- [ ] **Step 2: Implement `baseline_climatology`**

Fit global home/neutral goal rates + draw rate from training data; generate home/draw/away probs and
a scoreline matrix from global goal rates. This is the metric floor (the thing Elo must beat).

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task M4: Elo model (ratings + outcome probabilities)

**Files:** `src/wc_predictor/models/elo.py`, `tests/models/test_elo.py`.

- [ ] **Step 1: Tests first — update rules + home logic**

Assert: winner gains / loser loses Elo; draw changes are smaller; **home advantage applies via
`neutral`/host logic, not nominal home/away** (a neutral-site match gives no home bump; a host team
in its own country does). Goal-difference scales the update. Deterministic given input order.

- [ ] **Step 2: Implement Elo**

Maintain team Elo through chronological match order (sequential online update is leakage-safe).
Configurable K, tournament-importance weight, home/host advantage, goal-difference multiplier.
Convert pre-match rating diff (+ home/host adjustment) → expected score → home/draw/away
probabilities (draw handled explicitly). Export pre-match rating features per match.

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task M5: Elo → scoreline distribution

**Files:** extend `src/wc_predictor/models/elo.py` (or `models/poisson.py`),
`tests/models/test_elo_scoreline.py`.

- [ ] **Step 1: Tests first**

Expected goals positive; scoreline matrix sums to 1 incl tail mass; home/draw/away derived from the
matrix matches the M4 outcome probabilities within tolerance.

- [ ] **Step 2: Implement scoreline mapping**

Map Elo rating difference + home/host adjustment → home/away expected goals → bivariate-Poisson-style
`ScorelineDistribution` (top exact score, top-5, draw=diagonal, over/under, BTTS). This makes Elo
emit the full `ScorelineDistribution` schema from M0.

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task M6: Walk-forward backtest + acceptance gate

**Files:** `reports/backtests/elo_vs_climatology.md`,
`reports/model_cards/baseline_climatology.md`, `reports/model_cards/elo_poisson_v1.md`,
optional `src/wc_predictor/evaluation/compare.py`, `tests/...`.

- [ ] **Step 1: Run the walk-forward backtest**

Run both `baseline_climatology` and Elo over a multi-year walk-forward window of the silver `matches`
history (train_start early enough for warmup; predictions across many years to get a real sample).
Use a **pre-tournament cutoff** (exclude 2026 WC matches from training where the window demands it).
Lock predictions to the ledger; score with M1 metrics.

- [ ] **Step 2: Apply the acceptance gate (statistical honesty)**

Report RPS, log loss, Brier for both models WITH bootstrap CIs and match counts. State plainly
whether Elo beats climatology beyond noise. Write `elo_vs_climatology.md` and a model card per model
(metrics, config, training window, caveats). If Elo does NOT clearly beat climatology, record it as a
finding and STOP for Claude — do not hand-tune to force a pass.

- [ ] **Step 3: Determinism check**

Re-run a small backtest slice; assert identical `prediction_hash`es. Claude commits.

---

## Task M7: Live as-of-2026-06-21 forecast for remaining fixtures

**Files:** `src/wc_predictor/forecast_live.py` (or a CLI entry), `reports/backtests/` or
`reports/` live forecast summary, `runs/predictions/date=2026-06-21/predictions.jsonl`.

- [ ] **Step 1: Build the as-of forecast**

`as_of=2026-06-21`, `training_cutoff=2026-06-20` (train Elo on completed matches through 06-20,
including the 36 already-played WC group games). Forecast ONLY remaining `openfootball` fixtures
(match_date > as_of, or unresolved knockout slots left pending). Resolve fixture team ids → Elo
ratings; apply neutral/host logic (all WC matches neutral except host nations at home).

- [ ] **Step 2: Write predictions to the ledger**

One immutable `MatchPrediction` + `ScorelineDistribution` per remaining fixture, with
`prediction_hash`, model metadata, `training_cutoff`/`as_of`. Partitioned JSONL under
`runs/predictions/date=2026-06-21/`.

- [ ] **Step 3: Human-readable forecast report**

Summarize: per-remaining-match home/draw/away + top scoreline; note these are Elo-only (the proven
bar), not market-calibrated. Restate the statistical-honesty caveat. Claude commits.

---

## Definition of done for P3

- Deterministic prediction schema + immutable ledger (hash stable, double-write guarded); tests pass.
- Metrics + walk-forward backtest runner with a leakage test; tests pass.
- Climatology baseline + Elo model (outcome + scoreline), neutral/host home logic; tests pass.
- Walk-forward backtest report + model cards: **Elo vs climatology with CIs + match counts**, honest
  verdict on whether Elo beats the floor.
- Live `as_of=2026-06-21` forecasts for remaining WC fixtures written to the immutable ledger, with a
  readable report.
- No secrets; data/runs payloads gitignored (reports + code + model cards committed).
- co-op.md log updated; Claude reviews before any Phase-2 rung (Poisson/market/ML) is planned.
