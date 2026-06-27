# Plan: Model Tuning + Fusion + Market-as-Base — paste-into-new-session brief

**Author:** Claude (handoff for a fresh session). **Date:** 2026-06-27.
**Mission:** Do real science today. See how close our statistical models can get to
**live betting** (the market). We don't expect to beat it, but we strive to, and we
measure honestly. Three parallel thrusts: (1) tune our top models, (2) fuse multiple
models, (3) train stat models that take a **market prediction as input**. Claude and
Codex both work in parallel via worktrees + a shared, conflict-free ledger, with a
**live dashboard** to watch results land.

You (the new session) are the boss who also does the work. Read this top to bottom,
do the "Kickoff checklist" first, then execute.

---

## 0. The bars to beat (measured this session — these are ground truth)

All numbers are RPS (Ranked Probability Score, lower is better), leak-free walk-forward.

| Sample | What it is | baseline Elo | **elo_recalibrated** | **de-vigged market** |
| --- | --- | ---: | ---: | ---: |
| 15.8k history (2010+) | online walk-forward, all intl matches | 0.1762 | **0.1745** | n/a |
| WC-60 backtest | `lab/backtest.py`, played WC-2026 matches | 0.1763 | **0.1719** | n/a |
| 964-match market join | martj42 ∩ Football-Data odds, 2014–2026 | 0.1574 | **0.1574** | **0.1496** |

- **The market bar is RPS 0.1496** on the 964-match join. Our best model there is **0.1574**.
  The gap is **+0.0078 (~5%), paired 95% CI [+0.0040, +0.0120]** — real and significant.
  **Today's target: shrink that gap. Stretch goal: reach 0.1496 on held-out data.**
- `elo_recalibrated` config (the current champion, in `lab/variants/elo_recalibrated.py`):
  `k_factor=30, home_advantage=75, draw_base_probability=0.33, draw_rating_scale=600,
  tournament_weights=ALL 1.0 (flat), default_tournament_weight=1.0`, host-aware.
- **Hard-won lessons (do not relearn):**
  - Pure Elo reparameterization **plateaus at ~+1.1% RPS** over 3 sweep rounds. Don't expect
    big wins from constants alone; combos don't compound past ~0.1743 on history.
  - **Lowering home_advantage overfits** the WC sample (HA=40 looked best on 60 matches,
    strictly worse on 15.8k). Validate every candidate on BOTH 15.8k history AND WC-60.
  - **You cannot distill the market into Elo's parameters** (`reports/backtests/market_distillation.md`):
    tuning Elo to mimic the market made it the WORST predictor on history (RPS 0.1805). The
    market's edge is per-match info Elo can't represent + a biased priced-match sample.
  - A **linear blend of Elo+market picks λ=1** (pure market) — they're not complementary.
    Task 3 must therefore try NON-linear / calibration approaches, not linear blends.

---

## 1. Infrastructure to build FIRST (≈45 min, do before experiments)

### 1a. Shared, conflict-free experiment ledger
Reuse the file-per-experiment pattern (same idea as `runs/experiments/`): every experiment
writes ONE json file, so two agents never write the same file.

- Location (shared, gitignored, reached by both worktrees via the existing `runs/` junction):
  `worldcup_prediction_lab/runs/fusion/<agent>__<exp_id>__<utc>.json`
- Schema (one object per file):
  ```json
  {
    "exp_id": "tune-k-sweep-001",
    "agent": "claude" | "codex",
    "task": "tune" | "fuse" | "market_base",
    "created_utc": "2026-06-27T18:00:00Z",
    "config": { "...": "the exact knobs / recipe" },
    "samples": {
      "hist_15k":   {"n": 15877, "rps": 0.1743, "log_loss": 0.881, "brier": 0.522},
      "wc60":       {"n": 60,    "rps": 0.1719, "log_loss": 0.892, "brier": 0.547},
      "market964":  {"n": 964,   "rps": 0.1560, "log_loss": 0.79,  "brier": 0.49}
    },
    "vs_market_paired": {"mean_diff": 0.0064, "ci95": [0.003, 0.010], "excludes_0": true},
    "notes": "what changed, what it means, overfit flag",
    "promote": false
  }
  ```
- Add `src/wc_predictor/lab/fusion_ledger.py` with `record(result: dict)` (writes a file with
  a deterministic name) and `load_all() -> list[dict]` (globs `runs/fusion/*.json`).
  **Tests:** round-trip write/read; unique filenames; tolerates partial/missing samples.

### 1b. Standard evaluation harness (shared by all 3 tasks)
A single module both agents import so every result is comparable. Put it in the package so
both worktrees have it: `src/wc_predictor/lab/eval_harness.py`.
- `score_on_history(model_or_predict_fn) -> dict` — port `hist_sweep2.evaluate` (online
  walk-forward over `martj42_matches` from 2010-01-01; returns rps/ll/brier/n).
- `score_on_wc60(build_model_fn) -> dict` — wrap `lab/backtest.run_backtest` for a single config.
- `score_on_market964(predict_fn) -> dict` — reuse `evaluation/market_blend` alignment
  (`align_matches_with_market` + `add_elo_predictions`), score predictions vs outcomes AND
  return the paired-vs-market CI (reuse `bootstrap_ci`).
- `predict_fn` contract: takes a match row / aligned frame, returns (p_home, p_draw, p_away).
- **Tests:** harness reproduces the known bars (recalibrated → 0.1745 / 0.1719 / 0.1574)
  within tolerance. This is the regression guard for the whole session.

### 1c. Live experimentation dashboard (NEW — separate from the research dashboard)
`src/wc_predictor/lab/fusion_dashboard.py` → writes `research/fusion_dashboard.html` and
publishes `docs/fusion.html` (Pages). It reads the shared ledger and renders:
- A header with the three bars (market 0.1496 / recalibrated 0.1574 on market964, etc.).
- A sortable table of every experiment: agent, task, config summary, RPS on each sample,
  **"distance to market" = rps_market964 − 0.1496** (the headline metric), and a
  significance flag vs the Elo bar.
- A "best so far per task" summary and a small bar showing gap-to-market closing over time.
- Color: green when it beats `elo_recalibrated` on a sample; gold when it closes >50% of the
  Elo→market gap; red when worse than baseline.
- Offline single-file HTML (inline CSS), same style as `lab/dashboard.py`. Regenerate cheaply.
- **A refresh loop** so the user can watch: a tiny script `scripts/watch_fusion.ps1` that
  rebuilds the dashboard every ~60s (or call `fusion_dashboard.build()` at the end of each
  experiment batch). Commit the HTML periodically so Pages updates.
- **Tests:** builds from a synthetic ledger; renders rows; computes distance-to-market.

### 1d. Worktrees (no-conflict parallelism)
Worktrees live OUTSIDE OneDrive at `C:\Users\ztsha\wc_worktrees\`. For each, junction the
gitignored `data/` and `runs/` from main so both agents share data + the ledger:
```
git worktree add C:\Users\ztsha\wc_worktrees\tuning  -b tuning
git worktree add C:\Users\ztsha\wc_worktrees\fusion  -b fusion
# in each worktree (PowerShell), junction shared dirs to main:
New-Item -ItemType Junction -Path "<wt>\data" -Target "<main>\data"
New-Item -ItemType Junction -Path "<wt>\runs" -Target "<main>\runs"
```
- **Claude** works in `tuning` (Tasks 1 + 3). **Codex** works in `fusion` (Task 2).
- **Conflict rule (critical):** each agent only ADDS new files (variant files, experiment
  scripts, result json). Never edit a shared file from a worktree. Claude owns ALL git
  commits via PowerShell from main (Codex's sandbox can't write `.git` under OneDrive — known
  constraint). Codex writes files in its worktree; Claude reviews and commits them.
- Coordinate via `co-op.md` at repo root: a live task queue + "who's doing what" index.

---

## 2. Work split

| Agent | Owns | Why |
| --- | --- | --- |
| **Claude** (you) | Task 1 (tuning passes) + Task 3 (market-as-base) | Need judgment on significance, overfitting, and stat-model design |
| **Codex** | Task 2 (model fusion) — many mechanical ensemble/stack recipes | High-throughput, well-specified, parallelizable |

Both append to the shared ledger; both runs are scored by the same harness. Claude reviews
Codex's result files + variant code before committing. Re-balance if one finishes early.

---

## 3. TASK 1 — Tune top models (≥5 passes). Owner: Claude.

Start from `elo_recalibrated`. Each pass = define grid → score on **all three samples** →
record to ledger → keep only changes that help on 15.8k AND WC-60 (or are market-relevant on
964) → promote a winner as a new `lab/variants/*.py` variant only if robust + significant.
Reuse `wc_worktrees/weight-sweep/{hist_sweep2,significance}.py` patterns.

- **Pass 1 — K × draw joint fine grid.** k_factor {26,28,30,32,34} × draw_base {0.30,0.33,0.36}
  × draw_scale {500,600,700}. Find the joint optimum (round-2 only did one-knob). Validate.
- **Pass 2 — Recency-weighted K (time decay).** Weight each historical update by
  exp(-age_days/τ) for τ ∈ {365, 730, 1460, ∞}. P5 showed HARD windows hurt; test SOFT decay.
  Implement as a TunableElo subclass that scales K by match age at update time.
- **Pass 3 — Margin-of-victory multiplier.** Re-test {log_damped(base), log_plain, sqrt, wfe,
  linear(c)} jointly with K (round-2 found sqrt marginally best alone). Add a `goal_cap`.
- **Pass 4 — Rating scale (the 400 divisor) × home_advantage.** Joint grid scale {340,360,400,
  440} × HA {65,75,85}. Remember HA<60 overfits — confirm on 15.8k, don't trust WC-60 alone.
- **Pass 5 — Tournament weights, learned.** Flat=1.0 won round-2; now try a small coordinate
  search per high-volume tournament (Friendly, WC-qual, Euro/Copa, Nations Leagues) around 1.0
  to see if a non-flat optimum generalizes. Guard against overfitting the WC sample.
- **Pass 6 — Confederation/initial-rating priors.** Seed `base_rating` per confederation from
  long-run strength instead of a flat 1500; measure whether priors speed calibration.
- **Pass 7 — Draw-mass functional form.** Replace the exp decay of draw mass with logistic /
  linear alternatives; joint with draw_base. The model is structurally draw-blind at db≤1/3 —
  see if a better draw curve helps RPS without forcing wrong argmax draws.
- **Pass 8 (stretch) — Bayesian rating shrinkage** toward the mean between matches (regression
  to mean) with strength γ; can reduce overconfidence (the market's main edge is being less
  extreme — but globally softening overfit in distillation, so target it narrowly).

**Promotion bar:** improves 15.8k RPS with paired 95% CI excluding 0 AND does not regress
WC-60. Record EVERY pass (wins and nulls) to the ledger so the dashboard shows the search.

---

## 4. TASK 2 — Fuse multiple models. Owner: Codex.

Inputs are the per-match probability vectors of our existing variants (collect from the
walk-forward predictions of each `lab/variants/*` model on each sample). Build fusion recipes,
score with the shared harness, log to ledger. Start from the existing `ensemble_top_k` variant.

- **Fusion 1 — Linear opinion pool.** Weighted average of top-k variant probs; weights =
  uniform, inverse-RPS, and softmax(-RPS/T). Sweep k ∈ {2,3,5,all}.
- **Fusion 2 — Logarithmic opinion pool** (normalized geometric mean) with the same weight
  schemes — often beats linear when models are complementary.
- **Fusion 3 — Stacking / meta-model.** Walk-forward multinomial logistic regression with the
  variant probs as features → final 3-way probs. Strong L2 regularization (small n). Must be
  leak-free: fit the meta-model only on matches strictly before each scored match.
- **Fusion 4 — Confidence-weighted routing.** Pick/upweight the model that is sharpest (lowest
  entropy) per match, or route by rating-gap regime (form models for close games, Elo for
  mismatches — round-1 showed form variants lead on the WC sample).
- **Fusion 5 — Bayesian model averaging** by historical predictive likelihood (each model's
  weight ∝ its exp(−cumulative log loss) up to that match).
- **Fusion 6 — Rank-and-trim ensembles:** drop the worst variants, average the rest; find the
  subset that maximizes 15.8k RPS without overfitting WC-60.

**Promotion bar:** beats the single best constituent on 15.8k with paired CI excluding 0.
Codex records each recipe to the ledger. Watch for the ensemble just reproducing the best
single model (common) — only a genuinely complementary set wins.

---

## 5. TASK 3 — Market-as-base stat model. Owner: Claude.

**Premise:** instead of predicting from ratings, take a **market prediction as input** and
learn a model that outputs a (hopefully better-calibrated) prediction. We already proved a
linear Elo+market blend just picks the market (λ=1), so explore **calibration and non-linear
corrections** on the 964-match market join (heavy overfit risk at n=964 — use walk-forward /
k-fold + strong regularization, and report honestly).

- **M3.1 — Market calibration (temperature / Platt / isotonic).** Sharpen or soften the
  de-vigged market: p ∝ market^t (sweep t around 0.85 — the round-2 hint that the market is
  slightly under-confident), then Platt and isotonic on the 3-way probs. Does calibrated
  market beat raw market out-of-fold?
- **M3.2 — Market + context residual.** Features: de-vigged market probs (+ logits), Elo
  rating gap, home/host flag, tournament. Target: actual outcome. Model: small regularized
  multinomial logit / gradient-boosted trees with monotonic-ish priors. Walk-forward. The
  question: does ANY context correct the market beyond noise?
- **M3.3 — Market-anchored Elo.** Back out an implied rating gap from each market line and
  blend it with Elo's gap before predicting — i.e., let the market move the ratings, not the
  hyperparameters (distillation moved hyperparameters and failed; this moves the per-match
  state instead).
- **M3.4 — Log-linear (geometric) market+Elo pool** swept finely (round-2 showed it loses to
  pure market on 174; re-test on the bigger 964 join — more data may change it).
- **Honesty protocol:** every M3 result reports out-of-fold RPS vs **pure market** with a
  paired CI. If nothing beats pure market (likely), that itself is the scientific result:
  "the market is efficient on priced matches; our value is coverage + the overlay." Write it up.

---

## 6. Measurement, promotion, and honesty

- **Primary metric:** RPS. Secondary: log loss, Brier. Always report `n`.
- **Three samples, always:** 15.8k history (generalization), WC-60 (live tournament), 964
  market join (the market comparison). A win must hold on ≥2 of 3 and not regress the third.
- **Significance:** paired bootstrap CI (reuse `evaluation.metrics.bootstrap_ci`, seed fixed).
  "Win" = CI excludes 0. The project's accepted bar.
- **Overfitting guard:** anything that helps WC-60 but hurts 15.8k is overfit — reject (this
  is the #1 trap this codebase has, twice). Prefer the larger sample.
- **Promotion:** a winner becomes a committed `lab/variants/*.py` variant (+ test) so the
  daily bake-off scores it out-of-sample. New files only; Claude commits.

---

## 7. Coordination protocol (Claude ⇄ Codex)

- `co-op.md` (repo root): live index — task queue, who owns what, last status, blockers.
- Codex invocation on Windows (known-good): `$prompt | codex exec … -` (prompt via stdin, `-`
  placeholder, keep `"` out of the prompt). Run Codex FOREGROUND so the orchestrating session
  stays alive (the Day-2 background-dispatch bug). Codex builds ONE bite-sized task at a time.
- Claude owns all git commits (PowerShell from main; verify via PowerShell, not the Bash tool
  which sees a sandboxed git view). Commit cadence: after each promoted variant or batch of
  ledger results + dashboard refresh, so the user can watch progress land on Pages.
- Env: `uv run --extra dev python -m pytest`; set `$env:PYTHONUTF8="1"`; DuckDB-only parquet
  (no pyarrow). Worktrees need `data/` + `runs/` junctions to main.

---

## 8. Kickoff checklist (do these in order)

1. Read this plan + `memory/worldcup-prediction-lab-state.md` (full project state).
2. Skim the proof artifacts: `reports/backtests/market_blend.md`,
   `reports/backtests/market_distillation.md`, `research/BACKTEST.md`, and the worktree scripts
   in `C:\Users\ztsha\wc_worktrees\weight-sweep\` (hist_sweep2/significance/market_blend/distill).
3. Build Infrastructure §1 (ledger, eval_harness, fusion_dashboard, worktrees) and confirm the
   harness reproduces the bars (0.1745 / 0.1719 / 0.1574). Commit it. **Do not start
   experiments until the harness is verified** — every later number depends on it.
4. Write `co-op.md`, spin up the `tuning` and `fusion` worktrees, junction data+runs.
5. Kick Codex on Task 2 Fusion 1–2 (foreground). In parallel, Claude runs Task 1 Pass 1 and
   Task 3 M3.1.
6. After each batch: append results to the ledger, rebuild `fusion_dashboard.html` + publish
   `docs/fusion.html`, commit, push so the user can watch.
7. Keep going through the passes/recipes; promote robust winners as variants; end the day with
   a written summary of: best tuned model, best fusion, whether anything approached the market
   bar, and the honest verdict on market-as-base.

**North star:** close the 0.1574 → 0.1496 gap to the market on held-out data, with every
claim backed by a paired CI on the large samples. If we can't beat the market (likely), prove
exactly how close we got and why the remaining gap exists. That's the science.
