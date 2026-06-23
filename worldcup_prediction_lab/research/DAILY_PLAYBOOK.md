# Daily Model-Research Playbook

> You are **Claude Code orchestrating Codex**. Each Mon–Thu you run a one-day model
> bake-off: score yesterday's candidate models against newly-resolved results, then
> invent and build **3 new feature-model variants** (one per git worktree, built by
> Codex) and record their predictions. Every challenger must beat **`elo_baseline`**.

Working dir: `worldcup_prediction_lab/`. Run Python as `uv run --extra dev python ...`.
Commit via PowerShell (Codex never runs git). `as_of` = today's UTC date.

## Step 1 — Refresh data (pull yesterday's results)
```
uv run --extra dev python -m wc_predictor.run_daily_update
```
This ingests new martj42 results, retrains, refreshes odds + the main ledger.

## Step 2 — Score yesterday's variants
```
uv run --extra dev python -m wc_predictor.lab.leaderboard
```
Reads every `runs/experiments/date=*/<variant>.jsonl`, scores the most-informed
pre-kickoff prediction per match against results, writes `research/LEADERBOARD.md`.
Open it. Note which challengers beat `elo_baseline` (positive `Edge`) and which lost.

## Step 3 — Reflect and choose today's 3 variants
Append a dated entry to `research/research_log.md`:
- what resolved since yesterday, current standings, what you learned;
- today's 3 variant ideas. **Carry forward** a clear winner, **retire** a clear loser,
  and **invent** new feature hypotheses from data we actually have:
  rest/fatigue, match congestion, form windows (last-N results/goals), opponent-adjusted
  attack/defense, home-continent/travel proxy from venue, qualifier-vs-friendly weighting.
- Keep challengers honest: each is a falsification rung that must beat the baseline.

## Step 4 — Build the 3 variants with Codex, each in its own worktree
For each new `<id>` (snake_case):
```
git worktree add C:\Users\ztsha\wc_worktrees\<id> -b exp/<as_of>/<id> master
```
Dispatch Codex with cwd = that worktree to author **one file**
`src/wc_predictor/lab/variants/<id>.py` following the variant contract:
- `VARIANT_ID`, `DESCRIPTION`, `FEATURE_IDEA`, `build_model(*, generated_at_utc)`;
- subclass `EloModel`; override `fit` (precompute feature data) and
  `_home_advantage_elo` (add the feature as an Elo delta, positive favors home);
- set a `model_version`. Codex must NOT run git (no venv in the worktree — author only).

Then commit the file on its branch (from the worktree):
```
git -C C:\Users\ztsha\wc_worktrees\<id> add src/wc_predictor/lab/variants/<id>.py
git -C C:\Users\ztsha\wc_worktrees\<id> commit -F <msg-file>
```

## Step 5 — Merge, validate, generate today's predictions
```
git merge --no-ff exp/<as_of>/<id>          # repeat per variant (auto-discovery → no conflicts)
uv run --extra dev python -m pytest -q       # full suite must stay green
uv run --extra dev python -m wc_predictor.lab.run_experiments --as-of <as_of>
```
`run_experiments` writes each registered variant's predictions for upcoming fixtures
and refreshes the leaderboard. Sanity-check the new variants produce sane probabilities.

## Step 6 — Commit and clean up
- Commit on master: new variant code, `research/LEADERBOARD.md`, `research/research_log.md`.
- Remove the day's worktrees: `git worktree remove C:\Users\ztsha\wc_worktrees\<id>` (per id),
  and optionally delete merged `exp/<as_of>/<id>` branches.
- Update `co-op.md` with the day's log entry.

## Definition of done (per day)
3 new variants built + merged, full suite green, today's predictions recorded for all
variants, leaderboard + research log + co-op updated, worktrees cleaned. Do not retrain
or recalibrate on tournament-only data below the 200-match floor; predictions are immutable.
```
