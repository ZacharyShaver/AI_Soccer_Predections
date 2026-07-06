# Match-Analyst Timing (agent_late) + Self-History Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Lane split (co-op.md protocol, Zach-directed 2026-07-05):** Codex owns Tasks 1–4
> (Python + tests), strictly in order, ONE task per `codex exec` session, and **SKIPS all
> Commit steps** (no git — Claude reviews and commits). Claude owns Tasks 5–8 (kickoff
> data research, Windows ops scripts, agent prompt, review + integration).

**Goal:** Add a pre-kickoff "agent_late" second research pass (one-shot Windows scheduled tasks at kickoff−75min) and feed the live agent its own resolved track record, so morning-vs-late picks form a paired timing experiment and deviation sizing becomes self-informed.

**Architecture:** A manual `config/kickoff_times.csv` (mirroring the `knockout_overrides.csv` pattern) gives kickoff times the silver fixtures lack. The analyst CLI becomes mode-aware (`agent` vs `agent_late` — the ledger already dedupes on `(fixture_id, mode)`, so the late pass records its own row). A `your_record` block built from `resolve_forecasts` output rides along in the dump-packet payload. PowerShell one-shot tasks (registered by the 7am daily job) fire a narrow, time-boxed lineup-check Claude session per fixture.

**Tech Stack:** Python 3.12 (pandas, pytest via `uv run pytest` from `worldcup_prediction_lab/`), Windows PowerShell 5.1 + ScheduledTasks module, Claude CLI one-shot (`-p`) sessions.

## Global Constraints

- The analyst ledger (`runs/analyst/ledger.jsonl`) is append-only and immutable; new modes only ADD rows, never rewrite existing ones.
- Leak-free: `your_record` is built ONLY from resolved (completed-match) ledger rows; no match results ever reach a forecast for that same match.
- Codex does NOT run git (OneDrive `index.lock` failures); Claude commits after review. Codex logs evidence in co-op.md's "Codex → Claude log" and STOPS after one task.
- Allowed ledger modes after this plan: `deterministic`, `agent`, `agent_late`. Nothing else.
- Ops scripts must follow the hardened `daily_match_analyst.ps1` pattern: LLM steps time-boxed and non-blocking; deterministic steps never depend on LLM compliance; PowerShell 5.1 syntax (no `&&`, no ternary).
- All tests run from `worldcup_prediction_lab/`: `uv run pytest tests/lab/<file> -v`.
- Kickoff times in the CSV are machine-local (America/New_York — the scheduling machine's zone); the scheduler consumes them as local times.

---

### Task 1 (CODEX): Kickoff-times config loader

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/lab/kickoffs.py`
- Test: `worldcup_prediction_lab/tests/lab/test_kickoffs.py`

**Interfaces:**
- Consumes: `wc_predictor.config.settings.CONFIG_DIR` (existing; `config/` dir).
- Produces: `load_kickoffs(path: str | Path | None = None) -> dict[str, pd.Timestamp]` and `kickoffs_for_date(date: str, *, path: str | Path | None = None) -> list[tuple[str, pd.Timestamp]]` (sorted by time then fixture_id). Task 6's registration script calls `kickoffs_for_date` via `uv run python -c`.

- [x] **Step 1: Write the failing tests**

```python
# worldcup_prediction_lab/tests/lab/test_kickoffs.py
"""Tests for the manual kickoff-times config loader."""

from pathlib import Path

import pandas as pd
import pytest

from wc_predictor.lab.kickoffs import kickoffs_for_date, load_kickoffs


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "kickoff_times.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_kickoffs_parses_rows(tmp_path):
    p = _write(
        tmp_path,
        "fixture_id,kickoff_local,source,note\n"
        "fd67eda02d56,2026-07-06 15:00,fifa_schedule,Portugal v Spain\n"
        "8fcb454f2317,2026-07-06 18:00,fifa_schedule,USA v Belgium\n",
    )
    ks = load_kickoffs(p)
    assert ks["fd67eda02d56"] == pd.Timestamp("2026-07-06 15:00")
    assert len(ks) == 2


def test_load_kickoffs_missing_file_returns_empty(tmp_path):
    assert load_kickoffs(tmp_path / "nope.csv") == {}


def test_load_kickoffs_bad_time_raises_with_fixture_id(tmp_path):
    p = _write(
        tmp_path,
        "fixture_id,kickoff_local,source,note\n"
        "abc123,not-a-time,x,\n",
    )
    with pytest.raises(ValueError, match="abc123"):
        load_kickoffs(p)


def test_kickoffs_for_date_filters_and_sorts(tmp_path):
    p = _write(
        tmp_path,
        "fixture_id,kickoff_local,source,note\n"
        "late,2026-07-06 18:00,x,\n"
        "early,2026-07-06 15:00,x,\n"
        "other_day,2026-07-07 15:00,x,\n",
    )
    rows = kickoffs_for_date("2026-07-06", path=p)
    assert [fid for fid, _ in rows] == ["early", "late"]
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_kickoffs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wc_predictor.lab.kickoffs'`

- [x] **Step 3: Write the implementation**

```python
# worldcup_prediction_lab/src/wc_predictor/lab/kickoffs.py
"""Manual kickoff-time table for the pre-kickoff (T-75) lineup-check pass.

Silver fixtures carry only a match DATE — no time of day — so pre-kickoff
scheduling needs this manually maintained CSV (same convention as
``config/knockout_overrides.csv``; only a handful of tournament matches remain).
``kickoff_local`` is machine-local time (America/New_York on the scheduling
machine): the Windows one-shot tasks that consume it schedule in local time.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings

KICKOFFS_FILE = "kickoff_times.csv"


def load_kickoffs(path: str | Path | None = None) -> dict[str, pd.Timestamp]:
    """fixture_id -> naive local-time kickoff. Missing file -> {}; bad row -> ValueError."""

    p = Path(path) if path is not None else settings.CONFIG_DIR / KICKOFFS_FILE
    if not p.exists():
        return {}
    out: dict[str, pd.Timestamp] = {}
    with p.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fid = str(row["fixture_id"]).strip()
            ts = pd.to_datetime(row["kickoff_local"], errors="coerce")
            if pd.isna(ts):
                raise ValueError(
                    f"kickoff_times.csv: unparseable kickoff_local for fixture "
                    f"{fid!r}: {row['kickoff_local']!r}"
                )
            out[fid] = ts
    return out


def kickoffs_for_date(date: str, *, path: str | Path | None = None) -> list[tuple[str, pd.Timestamp]]:
    """Kickoffs on `date` (YYYY-MM-DD), sorted by time then fixture_id."""

    day = pd.Timestamp(date).date()
    rows = [(fid, ts) for fid, ts in load_kickoffs(path).items() if ts.date() == day]
    return sorted(rows, key=lambda item: (item[1], item[0]))
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_kickoffs.py -v`
Expected: 4 PASS

- [x] **Step 5: Commit — CLAUDE ONLY (Codex: skip, log evidence in co-op.md, STOP)**

```bash
git add worldcup_prediction_lab/src/wc_predictor/lab/kickoffs.py worldcup_prediction_lab/tests/lab/test_kickoffs.py
git commit -m "feat(analyst): kickoff-times config loader for T-75 lineup checks"
```

---

### Task 2 (CODEX): Mode-aware analyst CLI (`agent_late`)

**Files:**
- Modify: `worldcup_prediction_lab/src/wc_predictor/lab/analyst_cli.py` (functions `cmd_record`, `cmd_list_fixtures`, `main`)
- Test: `worldcup_prediction_lab/tests/lab/test_analyst_cli.py` (new file)

**Interfaces:**
- Consumes: `AnalystForecast` dataclass (`wc_predictor.lab.analyst`), `load_ledger` (`wc_predictor.lab.analyst_ledger`).
- Produces: `record --json <path> [--mode agent|agent_late]` (default `agent`); `list-fixtures --as-of D [--mode agent|agent_late]` (skip-set filters on that mode); pure helpers `_forecast_from_json(data: dict, *, mode: str = "agent") -> AnalystForecast` and `_researched_fixture_ids(ledger_rows: list[dict], mode: str) -> set[str]`. Task 6's scripts call `record --mode agent_late` and `list-fixtures --mode agent_late`.

- [x] **Step 1: Write the failing tests**

```python
# worldcup_prediction_lab/tests/lab/test_analyst_cli.py
"""Tests for the analyst CLI's pure helpers and mode handling."""

import json

import pytest

from wc_predictor.lab.analyst_cli import (
    _forecast_from_json,
    _researched_fixture_ids,
    main,
)


def _payload(**over):
    base = {
        "fixture_id": "fx1", "as_of": "2026-07-06", "match_date": "2026-07-06",
        "home_team_name": "Portugal", "away_team_name": "Spain",
        "p_home": 0.22, "p_draw": 0.26, "p_away": 0.52,
        "pick": "away", "pick_team": "Spain", "rationale": "r", "sources": [],
    }
    base.update(over)
    return base


def test_forecast_from_json_default_mode_agent():
    fc = _forecast_from_json(_payload())
    assert fc.mode == "agent"
    assert fc.pick == "away"
    assert abs(fc.p_home + fc.p_draw + fc.p_away - 1.0) < 1e-9


def test_forecast_from_json_agent_late_mode():
    fc = _forecast_from_json(_payload(), mode="agent_late")
    assert fc.mode == "agent_late"


def test_forecast_from_json_rejects_bad_probability_sum():
    with pytest.raises(SystemExit):
        _forecast_from_json(_payload(p_home=0.9, p_draw=0.9, p_away=0.9))


def test_record_rejects_unknown_mode(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps(_payload()), encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["record", "--json", str(p), "--mode", "banana"])


def test_researched_fixture_ids_filters_by_mode():
    rows = [
        {"fixture_id": "a", "mode": "agent"},
        {"fixture_id": "b", "mode": "agent_late"},
        {"fixture_id": "c", "mode": "deterministic"},
    ]
    assert _researched_fixture_ids(rows, "agent") == {"a"}
    assert _researched_fixture_ids(rows, "agent_late") == {"b"}
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_analyst_cli.py -v`
Expected: FAIL with `ImportError: cannot import name '_forecast_from_json'`

- [x] **Step 3: Implement**

In `analyst_cli.py`:

(a) Add the pure helpers (module level, near `_find_fixture`):

```python
_AGENT_MODES = ("agent", "agent_late")


def _researched_fixture_ids(ledger_rows: list[dict], mode: str) -> set[str]:
    """fixture_ids already carrying a ledger row of `mode`."""

    return {str(r["fixture_id"]) for r in ledger_rows if r.get("mode") == mode}


def _forecast_from_json(data: dict, *, mode: str = "agent") -> AnalystForecast:
    """Validate + normalize an agent-authored forecast payload into a ledger row."""

    p = (float(data["p_home"]), float(data["p_draw"]), float(data["p_away"]))
    total = sum(p)
    if not (0.99 <= total <= 1.01):
        raise SystemExit(f"probabilities must sum to 1.0 (got {total:.3f})")
    p = tuple(v / total for v in p)
    idx = max(range(3), key=lambda i: p[i])
    pick = ("home", "draw", "away")[idx]
    return AnalystForecast(
        fixture_id=str(data["fixture_id"]),
        as_of=str(data["as_of"]),
        match_date=str(data.get("match_date", "")),
        home_team_name=str(data.get("home_team_name", "")),
        away_team_name=str(data.get("away_team_name", "")),
        p_home=p[0], p_draw=p[1], p_away=p[2],
        pick=str(data.get("pick", pick)),
        pick_team=str(data.get("pick_team", "")),
        confidence=max(p),
        rationale=str(data.get("rationale", "")),
        sources=list(data.get("sources", [])),
        mode=mode,
    )
```

(b) Rewrite `cmd_record` to use the helper (drop its inline body):

```python
def cmd_record(args: argparse.Namespace) -> None:
    from wc_predictor.lab.analyst_ledger import record_forecast

    data = json.loads(Path(args.json).read_text(encoding="utf-8"))
    forecast = _forecast_from_json(data, mode=args.mode)
    elo = {forecast.fixture_id: tuple(data["elo_probs"])} if data.get("elo_probs") else None
    mkt = {forecast.fixture_id: tuple(data["market_probs"])} if data.get("market_probs") else None
    added = record_forecast([forecast], as_of=forecast.as_of, elo_probs=elo, market_probs=mkt)
    print(f"recorded {added} {forecast.mode} forecast(s) for fixture {forecast.fixture_id}")
```

(c) In `cmd_list_fixtures`, replace the `done` block's set comprehension:

```python
    done: set[str] = set()
    if not args.all:
        try:
            from wc_predictor.lab.analyst_ledger import load_ledger

            done = _researched_fixture_ids(load_ledger(), args.mode)
        except Exception:
            done = set()
```

(d) In `main`, register the flag on both subcommands (after their existing args):

```python
    lf.add_argument("--mode", choices=_AGENT_MODES, default="agent",
                    help="skip fixtures already researched in this mode")
    ...
    rc.add_argument("--mode", choices=_AGENT_MODES, default="agent",
                    help="ledger mode to record under")
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_analyst_cli.py -v`
Expected: 5 PASS

- [x] **Step 5: Regression check**

Run: `uv run pytest tests/lab/test_analyst.py tests/lab/test_analyst_ledger.py -v`
Expected: all PASS (no behavior change for default mode)

- [x] **Step 6: Commit — CLAUDE ONLY (Codex: skip, log evidence in co-op.md, STOP)**

```bash
git add worldcup_prediction_lab/src/wc_predictor/lab/analyst_cli.py worldcup_prediction_lab/tests/lab/test_analyst_cli.py
git commit -m "feat(analyst): agent_late ledger mode via --mode on record/list-fixtures"
```

---

### Task 3 (CODEX): `your_record` self-history block in the packet

**Files:**
- Modify: `worldcup_prediction_lab/src/wc_predictor/lab/analyst_ledger.py` (add `agent_record_summary` after `track_record`)
- Modify: `worldcup_prediction_lab/src/wc_predictor/lab/analyst_cli.py` (`cmd_dump_packet`)
- Test: `worldcup_prediction_lab/tests/lab/test_analyst_ledger.py` (extend)

**Interfaces:**
- Consumes: `resolve_forecasts` output rows (keys: `resolved`, `mode`, `p_*`, `market_probs`, `rps`, `market_rps`, `correct`, team names, `match_date`); `_mean`, `_OUTCOMES` (module-private, same file).
- Produces: `agent_record_summary(resolved: list[dict], *, mode: str = "agent", max_rows: int = 10) -> dict` with keys `mode, n_resolved, hits, mean_rps, vs_market, deviations, caution`; each deviation: `{fixture, match_date, size_pts, toward, outcome, pick_correct}`. The dump-packet payload gains a top-level `"your_record"` key. Task 7's agent prompt references these exact key names.

- [x] **Step 1: Write the failing tests**

Append to `worldcup_prediction_lab/tests/lab/test_analyst_ledger.py`:

```python
def _agent_ledger_row(fid, home, probs, mkt, pick):
    return {
        "fixture_id": fid, "mode": "agent", "match_date": "2026-07-02",
        "home_team_name": home, "away_team_name": "Opp",
        "p_home": probs[0], "p_draw": probs[1], "p_away": probs[2],
        "pick": pick, "pick_team": home, "market_probs": list(mkt),
    }


def test_agent_record_summary_classifies_deviations():
    from wc_predictor.lab.analyst_ledger import agent_record_summary, resolve_forecasts

    ledger = [
        # deviated 5pts toward home; home happened -> helped
        _agent_ledger_row("f1", "Alpha", (0.60, 0.25, 0.15), (0.55, 0.27, 0.18), "home"),
        # no deviation -> neutral
        _agent_ledger_row("f2", "Beta", (0.30, 0.30, 0.40), (0.30, 0.30, 0.40), "away"),
    ]
    resolved = resolve_forecasts(ledger, {"f1": (2, 0), "f2": (0, 1)})
    rec = agent_record_summary(resolved)

    assert rec["mode"] == "agent"
    assert rec["n_resolved"] == 2
    assert rec["hits"] == 2
    assert rec["vs_market"] < 0  # beat the market on this pair
    d1 = next(d for d in rec["deviations"] if d["fixture"].startswith("Alpha"))
    d2 = next(d for d in rec["deviations"] if d["fixture"].startswith("Beta"))
    assert d1["toward"] == "home" and d1["outcome"] == "helped"
    assert abs(d1["size_pts"] - 5.0) < 0.01
    assert d2["outcome"] == "neutral"


def test_agent_record_summary_empty_history_has_caution():
    from wc_predictor.lab.analyst_ledger import agent_record_summary

    rec = agent_record_summary([])
    assert rec["n_resolved"] == 0
    assert rec["deviations"] == []
    assert "anecdote" in rec["caution"]


def test_agent_record_summary_ignores_other_modes_and_unresolved():
    from wc_predictor.lab.analyst_ledger import agent_record_summary, resolve_forecasts

    ledger = [
        {**_agent_ledger_row("f1", "Alpha", (0.5, 0.3, 0.2), (0.5, 0.3, 0.2), "home"),
         "mode": "deterministic"},
        _agent_ledger_row("f2", "Beta", (0.5, 0.3, 0.2), (0.5, 0.3, 0.2), "home"),
    ]
    resolved = resolve_forecasts(ledger, {"f1": (1, 0)})  # f2 unresolved
    rec = agent_record_summary(resolved)
    assert rec["n_resolved"] == 0
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_analyst_ledger.py -v -k agent_record`
Expected: 3 FAIL with `ImportError: cannot import name 'agent_record_summary'`

- [x] **Step 3: Implement `agent_record_summary`**

Add to `analyst_ledger.py` after `track_record`:

```python
RECORD_CAUTION = (
    "Small sample: treat this record as anecdote, not license. It informs how you SIZE "
    "deviations; it never justifies deviating more than your rules allow."
)


def agent_record_summary(resolved: list[dict], *, mode: str = "agent", max_rows: int = 10) -> dict:
    """The agent's own resolved record, packaged for the context packet.

    Leak-free by construction (resolved rows only). Each past deviation from the
    frozen market anchor is classified helped/hurt/neutral by paired RPS so the
    live agent can see whether its news-based shifts have been earning their keep.
    """

    rows = [r for r in resolved if r["resolved"] and str(r.get("mode")) == mode]
    deviations: list[dict] = []
    for r in rows[-max_rows:]:
        mkt = r.get("market_probs")
        if not mkt or r.get("market_rps") is None:
            continue
        probs = (float(r["p_home"]), float(r["p_draw"]), float(r["p_away"]))
        # Total-variation distance from the anchor, in percentage points.
        size_pts = 50.0 * sum(abs(p - m) for p, m in zip(probs, mkt))
        toward = _OUTCOMES[max(range(3), key=lambda i: probs[i] - mkt[i])]
        edge = r["market_rps"] - r["rps"]  # positive = beat the market
        outcome = (
            "neutral" if size_pts < 0.25 or abs(edge) < 1e-4
            else "helped" if edge > 0 else "hurt"
        )
        deviations.append({
            "fixture": f"{r['home_team_name']} v {r['away_team_name']}",
            "match_date": r.get("match_date"),
            "size_pts": round(size_pts, 2),
            "toward": toward,
            "outcome": outcome,
            "pick_correct": bool(r["correct"]),
        })
    return {
        "mode": mode,
        "n_resolved": len(rows),
        "hits": sum(1 for r in rows if r["correct"]),
        "mean_rps": _mean([r["rps"] for r in rows]),
        "vs_market": _mean([
            r["rps"] - r["market_rps"] for r in rows if r.get("market_rps") is not None
        ]),  # negative = agent better than the frozen market anchor
        "deviations": deviations,
        "caution": RECORD_CAUTION,
    }
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_analyst_ledger.py -v`
Expected: all PASS (new 3 + existing)

- [x] **Step 5: Wire into `cmd_dump_packet`**

In `analyst_cli.py`'s `cmd_dump_packet`, immediately before `payload = {`:

```python
    your_record: dict = {}
    try:
        from wc_predictor.lab.analyst_ledger import (
            agent_record_summary, load_ledger, resolve_forecasts,
        )
        from wc_predictor.lab.leaderboard import load_results

        results_df = load_results()
        results = {
            str(r["match_id"]): (int(r["home_score"]), int(r["away_score"]))
            for _, r in results_df.iterrows()
        } if not results_df.empty else {}
        your_record = agent_record_summary(resolve_forecasts(load_ledger(), results))
    except Exception:
        your_record = {}  # packet must still ship if history/results are unavailable
```

and add to `payload` (after `"deterministic_baseline"`), plus extend the instructions string:

```python
        "your_record": your_record,
        "instructions": (
            "Anchor to the market probs. Deviate only on concrete, cited findings "
            "(confirmed lineups, injuries, suspensions, travel, weather, odds moves). "
            "your_record is your own resolved history: use it to SIZE deviations, "
            "never to justify exceeding them. Output p_home+p_draw+p_away=1.0, a "
            "single pick, a short rationale, and a sources list of URLs with dates. "
            "If you find nothing, return the baseline."
        ),
```

- [x] **Step 6: Verify the wiring end-to-end (no network needed beyond the model fit)**

Run: `uv run python -m wc_predictor.lab.analyst_cli dump-packet --fixture "Argentina,Egypt" --as-of 2026-07-05 --out ../.tmp_packet_check.json` then inspect: `uv run python -c "import json; d=json.load(open('../.tmp_packet_check.json')); print(sorted(d)); print(d['your_record']['n_resolved'], len(d['your_record']['deviations']))"`
Expected: keys include `your_record`; `n_resolved >= 5`; delete `.tmp_packet_check.json` afterwards.

- [x] **Step 7: Commit — CLAUDE ONLY (Codex: skip, log evidence in co-op.md, STOP)**

```bash
git add worldcup_prediction_lab/src/wc_predictor/lab/analyst_ledger.py worldcup_prediction_lab/src/wc_predictor/lab/analyst_cli.py worldcup_prediction_lab/tests/lab/test_analyst_ledger.py
git commit -m "feat(analyst): your_record self-history block in the context packet"
```

---

### Task 4 (CODEX): Paired agent vs agent_late comparison

**Files:**
- Modify: `worldcup_prediction_lab/src/wc_predictor/lab/analyst_ledger.py` (add `paired_mode_comparison` after `agent_record_summary`)
- Test: `worldcup_prediction_lab/tests/lab/test_analyst_ledger.py` (extend)

**Interfaces:**
- Consumes: `resolve_forecasts` output; `bootstrap_ci` from `wc_predictor.evaluation.metrics` (signature: `bootstrap_ci(diffs, n_boot=2000, seed=11)` returning a 4-tuple whose middle two values are the CI bounds).
- Produces: `paired_mode_comparison(resolved: list[dict], *, mode_a: str = "agent", mode_b: str = "agent_late") -> dict` with keys `mode_a, mode_b, n, mean_rps_a, mean_rps_b, mean_diff, ci95, fixtures`. `mean_diff = mean(rps_b - rps_a)`; negative = late pass better. `ci95` is `None` below n=10.

- [x] **Step 1: Write the failing tests**

Append to `worldcup_prediction_lab/tests/lab/test_analyst_ledger.py`:

```python
def test_paired_mode_comparison_joins_on_fixture():
    from wc_predictor.lab.analyst_ledger import paired_mode_comparison, resolve_forecasts

    ledger = [
        _agent_ledger_row("f1", "Alpha", (0.60, 0.25, 0.15), (0.55, 0.27, 0.18), "home"),
        {**_agent_ledger_row("f1", "Alpha", (0.70, 0.20, 0.10), (0.55, 0.27, 0.18), "home"),
         "mode": "agent_late"},
        # agent-only fixture: must be excluded from the pairing
        _agent_ledger_row("f2", "Beta", (0.30, 0.30, 0.40), (0.30, 0.30, 0.40), "away"),
    ]
    resolved = resolve_forecasts(ledger, {"f1": (2, 0), "f2": (0, 1)})
    cmp = paired_mode_comparison(resolved)

    assert cmp["n"] == 1
    assert cmp["fixtures"] == ["f1"]
    # late pass was sharper toward the actual winner -> lower RPS -> negative diff
    assert cmp["mean_diff"] < 0
    assert cmp["ci95"] is None  # n < 10


def test_paired_mode_comparison_empty_when_no_overlap():
    from wc_predictor.lab.analyst_ledger import paired_mode_comparison, resolve_forecasts

    ledger = [_agent_ledger_row("f1", "Alpha", (0.5, 0.3, 0.2), (0.5, 0.3, 0.2), "home")]
    resolved = resolve_forecasts(ledger, {"f1": (1, 0)})
    cmp = paired_mode_comparison(resolved)
    assert cmp["n"] == 0
    assert cmp["mean_diff"] is None
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_analyst_ledger.py -v -k paired_mode`
Expected: 2 FAIL with `ImportError: cannot import name 'paired_mode_comparison'`

- [x] **Step 3: Implement**

```python
def paired_mode_comparison(
    resolved: list[dict], *, mode_a: str = "agent", mode_b: str = "agent_late"
) -> dict:
    """Paired RPS comparison of two modes on fixtures where BOTH resolved.

    This is the timing experiment's readout: mode_a = morning research,
    mode_b = T-75 lineup check. mean_diff = mean(rps_b - rps_a); negative
    means the late pass was more accurate. ci95 stays None below n=10.
    """

    a = {str(r["fixture_id"]): r for r in resolved
         if r["resolved"] and str(r.get("mode")) == mode_a}
    b = {str(r["fixture_id"]): r for r in resolved
         if r["resolved"] and str(r.get("mode")) == mode_b}
    fids = sorted(set(a) & set(b))
    diffs = [b[f]["rps"] - a[f]["rps"] for f in fids]
    ci95 = None
    if len(diffs) >= 10:
        from wc_predictor.evaluation.metrics import bootstrap_ci

        _, lo, hi, _ = bootstrap_ci(diffs, n_boot=2000, seed=11)
        ci95 = [lo, hi]
    return {
        "mode_a": mode_a,
        "mode_b": mode_b,
        "n": len(fids),
        "mean_rps_a": _mean([a[f]["rps"] for f in fids]),
        "mean_rps_b": _mean([b[f]["rps"] for f in fids]),
        "mean_diff": _mean(diffs),
        "ci95": ci95,
        "fixtures": fids,
    }
```

- [x] **Step 4: Run the full analyst test set**

Run: `uv run pytest tests/lab/test_analyst_ledger.py tests/lab/test_analyst.py tests/lab/test_analyst_cli.py tests/lab/test_kickoffs.py -v`
Expected: all PASS

- [x] **Step 5: Commit — CLAUDE ONLY (Codex: skip, log evidence in co-op.md, STOP)**

```bash
git add worldcup_prediction_lab/src/wc_predictor/lab/analyst_ledger.py worldcup_prediction_lab/tests/lab/test_analyst_ledger.py
git commit -m "feat(analyst): paired agent vs agent_late timing comparison"
```

---

### Task 5 (CLAUDE): Kickoff-times data

**Files:**
- Create: `worldcup_prediction_lab/config/kickoff_times.csv`

**Interfaces:**
- Produces: rows `fixture_id,kickoff_local,source,note` for every remaining tournament fixture with a known kickoff (local = America/New_York). Consumed by Task 1's loader.

- [x] **Step 1:** List remaining fixtures + ids: `uv run python -m wc_predictor.lab.analyst_cli list-fixtures --as-of 2026-07-05 --days 21 --all`
- [x] **Step 2:** Web-research each fixture's confirmed kickoff (FIFA/ESPN schedule pages), convert to Eastern, and write the CSV with one `source` URL slug per row (pattern: `knockout_overrides.csv`). (5 rows: PT-ES 7/6 15:00, US-BE 7/6 20:00, AR-EG 7/7 12:00, SUI-COL 7/7 16:00, FR-MA 7/9 16:00 ET; today's two matches excluded — already underway/past.)
- [x] **Step 3:** Verify round-trip: `uv run python -c "from wc_predictor.lab.kickoffs import load_kickoffs; ks = load_kickoffs(); print(len(ks), sorted(ks.items())[:3])"` — every id present in the fixture list, no parse errors. (5 rows load; kickoffs_for_date('2026-07-06') returns both July-6 fixtures sorted.)
- [x] **Step 4:** Commit: `git add worldcup_prediction_lab/config/kickoff_times.csv && git commit -m "data: kickoff times for remaining fixtures (T-75 scheduling)"`

---

### Task 6 (CLAUDE): Windows one-shot lineup-check ops

**Files:**
- Create: `worldcup_prediction_lab/scripts/lineup_check.ps1`
- Create: `worldcup_prediction_lab/scripts/register_lineup_checks.ps1`
- Modify: `worldcup_prediction_lab/scripts/daily_match_analyst.ps1` (phase 1.5 between phase 1 and phase 2)

**Interfaces:**
- Consumes: `kickoffs_for_date` (Task 1) via `uv run python -c`; `record --mode agent_late` and `list-fixtures --mode agent_late` (Task 2).
- Produces: `lineup_check.ps1 -FixtureId <id> -Home <name> -Away <name> [-DryRun]` — time-boxed (10 min) one-shot Claude session that dump-packets fresh, researches ONLY confirmed XI + late team news + current lines, records an `agent_late` row; then a deterministic tail commits + pushes the ledger and deletes its own scheduled task `WC-LineupCheck-<id>`. `register_lineup_checks.ps1 [-Date YYYY-MM-DD]` — registers one one-shot task per fixture at kickoff−75min (skipping past times and fixtures already carrying an `agent_late` row), using `Register-ScheduledTask` with `-WakeToRun -StartWhenAvailable`.

- [ ] **Step 1:** Write `lineup_check.ps1` following `daily_match_analyst.ps1`'s hardened pattern (Start-Process + WaitForExit timeout + `$null = $proc.Handle`; `Invoke-NativeLogged`-style stderr handling; logs to `runs/analyst/logs/lineup_<fixture>_<stamp>.log`). `-DryRun` skips the Claude call, the git tail, and task deletion — it only logs what it would do.
- [ ] **Step 2:** Write `register_lineup_checks.ps1`: get today's kickoffs via `uv run python -c "from wc_predictor.lab.kickoffs import kickoffs_for_date; [print(f'{f}\t{t:%Y-%m-%d %H:%M}') for f, t in kickoffs_for_date('<date>')]"`, resolve team names via `list-fixtures --all`, skip fixtures already in the ledger with mode `agent_late`, register `WC-LineupCheck-<id>` at kickoff−75min.
- [ ] **Step 3:** Add phase 1.5 to `daily_match_analyst.ps1`: invoke `register_lineup_checks.ps1` wrapped in try/catch, logged, non-fatal (phase 2 must proceed regardless).
- [ ] **Step 4:** Dry-run test: register a disposable task 3 minutes out pointing at `lineup_check.ps1 -DryRun`, confirm it fires, logs, and (manually) delete it. Verify `Get-ScheduledTask WC-LineupCheck-*` lists then clears.
- [ ] **Step 5:** Commit: `git add worldcup_prediction_lab/scripts/ && git commit -m "ops: T-75 one-shot lineup-check tasks (register + runner + daily phase 1.5)"`

---

### Task 7 (CLAUDE): Agent prompt updates

**Files:**
- Modify: `.claude/agents/match-analyst.md`

**Interfaces:**
- Consumes: `your_record` payload keys from Task 3 (`n_resolved, hits, vs_market, deviations[].{size_pts,toward,outcome}, caution`); `--mode agent_late` from Task 2.

- [ ] **Step 1:** Add a "Your record" subsection under Hard rules: the packet's `your_record` is the agent's own resolved history; it informs deviation SIZING (typical winning deviation so far ≈ 1pt with a cited cause); it NEVER justifies exceeding the existing modesty rules; note the draw blind spot explicitly.
- [ ] **Step 2:** Add a "Late mode (agent_late)" section: when the dispatch prompt says lineup-check/T-75, scope research to confirmed XI + late team news + current lines ONLY (skip travel/weather/social — already covered by the morning pass), and record with `--mode agent_late`.
- [ ] **Step 3:** Commit: `git add .claude/agents/match-analyst.md && git commit -m "agents: your_record guidance + agent_late lineup-check mode"`

---

### Task 8 (CLAUDE): Review, integration, and co-op bookkeeping

- [ ] **Step 1:** After each Codex task: review the diff, rerun its test commands, then run the full suite `uv run pytest` — expect green (pre-existing known failures excepted) — and commit with the task's message.
- [ ] **Step 2:** End-to-end smoke: `dump-packet` for the next fixture shows `your_record` populated; `record --mode agent_late` on a scratch JSON writes a second row for a fixture that already has an `agent` row (verify with `list-fixtures --mode agent_late`), then remove the scratch row is NOT possible (append-only) — so use a **throwaway fixture id** (`smoke_test_fixture`) and leave it; it never resolves so it only ever counts as pending. Alternative: point `record` at a tmp ledger via a copied JSON and skip the real-ledger write; either way, do not hand-edit `ledger.jsonl`.
- [ ] **Step 3:** Update co-op.md (lane outcome entry + task queue) and the memory file; confirm the dashboard still builds (`uv run python -m wc_predictor.lab.run_experiments --help` sanity only — no full rebuild needed).
- [ ] **Step 4:** Final commit + push.

---

## Self-review notes

- **Spec coverage:** (A) T-75 pass = Tasks 1, 2, 5, 6, 7; (B) your_record = Tasks 3, 7; paired experiment readout = Task 4; review/integration = Task 8. No gaps found.
- **Type consistency:** `kickoffs_for_date` returns `list[tuple[str, pd.Timestamp]]` (Task 6 consumes via CLI print, not import); `_forecast_from_json` keyword `mode` matches `_AGENT_MODES`; `agent_record_summary` key names match Task 7's prompt text and the payload key `your_record`; `paired_mode_comparison` consumes the same `resolve_forecasts` rows Tasks 3's tests build.
- **Ledger immutability:** no task rewrites existing rows; `agent_late` is purely additive; smoke testing avoids hand-editing the ledger.
