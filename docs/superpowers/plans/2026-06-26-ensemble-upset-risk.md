# Ensemble Upset Risk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a top-model ensemble forecast variant and an upset-risk second-pass signal to the model-research dashboard.

**Architecture:** The ensemble is a normal auto-discovered lab variant so it participates in live forecasts, leaderboard scoring, and walk-forward backtests. The upset-risk model is a pure report-layer module that reads existing probabilities and match metadata, then annotates dashboard rows without rewriting immutable prediction ledgers.

**Tech Stack:** Python, pandas, existing `wc_predictor.lab` variant registry, existing dashboard HTML generator, pytest via `uv run --extra dev`.

---

### Task 1: Test ensemble model behavior

**Files:**
- Modify: `worldcup_prediction_lab/tests/lab/test_lab.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/lab/variants/ensemble_top_k.py`

- [ ] **Step 1: Write failing tests**

Add tests proving `ensemble_top_k` is registered and returns normalized probabilities bounded by the component forecasts.

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run --extra dev pytest tests/lab/test_lab.py::test_registry_discovers_ensemble_top_k tests/lab/test_lab.py::test_ensemble_top_k_averages_component_probabilities -q`

Expected: fail because `ensemble_top_k` is not registered yet.

- [ ] **Step 3: Implement variant**

Create `ensemble_top_k.py` with a small model wrapper that builds `ewma_goal_form`, `form_trend`, and `opp_adj_form`, fits each component, averages `predict_match`, and delegates `predict_scoreline` to the strongest current component (`ewma_goal_form`) to keep the ledger schema intact.

- [ ] **Step 4: Run tests and verify pass**

Run the same two tests. Expected: pass.

### Task 2: Test upset-risk second pass

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/lab/upset.py`
- Create: `worldcup_prediction_lab/tests/lab/test_upset.py`

- [ ] **Step 1: Write failing tests**

Add tests for favorite detection, underdog-avoids-defeat probability, bounded risk percentages, and stronger risk when the favorite is less confident.

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run --extra dev pytest tests/lab/test_upset.py -q`

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement pure functions**

Implement `UpsetRisk`, `assess_upset_risk`, and `format_upset_risk`. Use underdog win-or-draw as the soccer-friendly upset definition, with a conservative confidence penalty.

- [ ] **Step 4: Run tests and verify pass**

Run the same upset tests. Expected: pass.

### Task 3: Add upset signal to dashboard

**Files:**
- Modify: `worldcup_prediction_lab/src/wc_predictor/lab/dashboard.py`
- Test: `worldcup_prediction_lab/tests/lab/test_upset.py`

- [ ] **Step 1: Write/extend failing tests**

Add one dashboard-facing formatting test that verifies a high-risk favorite displays a percent and label.

- [ ] **Step 2: Implement dashboard annotations**

Add an `Upset risk` column to result cards and upcoming forecasts. Prefer `ensemble_top_k` probabilities when present, falling back to `elo_baseline`.

- [ ] **Step 3: Verify**

Run lab tests, then regenerate:

`uv run --extra dev python -m wc_predictor.lab.backtest`

`uv run --extra dev python -m wc_predictor.lab.dashboard`

Expected: `research/dashboard.html` includes `ensemble_top_k` and `Upset risk`.
