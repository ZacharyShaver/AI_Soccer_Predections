# Research Lab Model Compare Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second Research Lab tab that compares every dashboard model side by side.

**Architecture:** Keep the static HTML generator as the single source of truth. The Research Lab bucket becomes a small CSS-tab interface: the existing accuracy/leaderboard/backtest/results stack remains the Performance tab, and a new Compare models tab renders a sortable table from `VariantStanding` records.

**Tech Stack:** Python static dashboard generator, inline HTML/CSS/JS, pytest.

---

### Task 1: Add Research Lab compare tab

**Files:**
- Modify: `worldcup_prediction_lab/src/wc_predictor/lab/dashboard.py`
- Test: `worldcup_prediction_lab/tests/lab/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Add `test_research_lab_renders_model_compare_tab` that builds a stubbed dashboard with two `VariantStanding` records and asserts:

```python
assert 'id="research-tab-performance"' in html
assert 'id="research-tab-compare"' in html
assert 'for="research-tab-compare">Compare models</label>' in html
assert '<tbody id="model-compare-body">' in html
assert "model_a" in html
assert "model_b" in html
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
uv run --extra dev pytest tests/lab/test_dashboard.py::test_research_lab_renders_model_compare_tab
```

Expected: fail because the Research Lab tab controls and compare table do not exist yet.

- [ ] **Step 3: Implement the minimal generator changes**

In `dashboard.py`, add a helper that renders sortable comparison rows from `standings`, pass the generated HTML into `_TEMPLATE`, and wrap the Research Lab content in CSS tabs:

```html
<input class="lab-tab-input" id="research-tab-performance" checked>
<label for="research-tab-performance">Performance</label>
<input class="lab-tab-input" id="research-tab-compare">
<label for="research-tab-compare">Compare models</label>
```

The Compare models panel contains a sortable table with variant, n, RPS, log loss, Brier, overall accuracy, decisive accuracy, and edge vs baseline.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv run --extra dev pytest tests/lab/test_dashboard.py tests/lab/test_upset.py
```

Expected: all tests pass.

- [ ] **Step 5: Rebuild generated dashboard outputs**

Run:

```powershell
uv run --extra dev python -m wc_predictor.lab.dashboard
```

Expected: writes `worldcup_prediction_lab/research/dashboard.html` and publishes `docs/index.html`.

- [ ] **Step 6: Inspect generated HTML**

Check that both generated files contain `research-tab-compare`, `Compare models`, and `model-compare-body`.
