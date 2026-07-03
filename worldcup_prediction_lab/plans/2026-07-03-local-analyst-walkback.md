# Local-Model Match-Analyst Walk-Back Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure how well local LLMs (8–14B via LM Studio) turn prebaked, leak-free news + stats context into H/D/A match forecasts, placed on the lab's accuracy ladder (climatology → Elo ~0.169 → market ~0.150 RPS).

**Architecture:** A new `wc_predictor.lab.walkback` package with six focused modules: a post-cutoff match universe drawn from the existing `build_market964_frame()` (964 aligned matches with leak-free Elo probs, de-vigged market probs, and results); a GDELT-based "news well" builder that freezes pre-match articles per fixture into JSON files; a leakage linter; an LM Studio client + deterministic single-shot forecast harness (three ablation conditions, market NEVER shown); a parametric-recall screen; and an evaluation module producing the ladder table, paired bootstrap CIs, and calibration analysis. All model runs are resumable JSONL appends — the frozen wells are the durable dataset, models are interchangeable evaluees.

**Tech Stack:** Python 3.11 via `uv`, pandas, requests (GDELT DOC 2.0 API + article bodies), trafilatura (body extraction), LM Studio OpenAI-compatible local server (`http://localhost:1234/v1`), pytest. Reuses `wc_predictor.evaluation.metrics.ranked_probability_score` / `bootstrap_ci` and `wc_predictor.lab.eval_harness.build_market964_frame`.

## Execution status (2026-07-03)

- Tasks 1 and 2 are DONE and committed by Claude (`ee36ab5`, `5101a98`).
- **Codex lane: Tasks 2b → 3 → 4 → 5 → 6, strictly in that order, one task per session.**
  Codex: SKIP every "Commit" step inside the tasks — do not run git at all; Claude reviews
  and commits after each task. Check the boxes of the steps you completed, log evidence in
  co-op.md's "Codex → Claude log", then STOP.
- Claude lane: Tasks 7, 8, 9 plus review/commit of every Codex task.

## Global Constraints

- **Leak-free, twice over:** (1) every news doc must be dated strictly before the match date; (2) the eval universe is restricted to matches on/after the model's knowledge cutoff — default `--cutoff 2025-01-01` (443 of the 964 market-joined matches; `2024-07-01` gives 520, `2025-07-01` gives 287).
- **Market probs are NEVER shown to the LLM in any condition.** They exist only in the evaluation ladder.
- **Determinism:** temperature 0.0 on every LLM call; harness is single-shot prompt→JSON, no agentic tool use.
- **Frozen wells are append-only:** `runs/newswells/{match_id}.json`, never edited after lint; re-running builders must not clobber existing wells.
- **Resumable runs:** the batch runner skips (match_id, model, condition) keys already present in the output JSONL.
- **Do not touch** `runs/analyst/ledger.jsonl` (the live agent's forward ledger) or any Codex worktrees.
- All commands run from `worldcup_prediction_lab/` with `uv run`; tests live flat in `tests/lab/` per repo convention (`test_walkback_*.py`).
- Hardware budget: RTX 5070 12GB → models ≤14B at Q4/Q5; the runner must survive LM Studio restarts (per-call try/except, keep going).

---

### Task 1: Match universe builder

**Files:**
- Create: `src/wc_predictor/lab/walkback/__init__.py`
- Create: `src/wc_predictor/lab/walkback/universe.py`
- Test: `tests/lab/test_walkback_universe.py`

**Interfaces:**
- Consumes: `wc_predictor.lab.eval_harness.build_market964_frame() -> pd.DataFrame` (columns include `match_id`, `date`, `home_team`, `away_team`, `home_score`, `away_score`, `tournament`, `city`, `elo_prob_home/draw/away`, `elo_home_rating`, `elo_away_rating`, `elo_home_advantage`, `market_prob_home/draw/away`).
- Produces: `load_universe(cutoff: str = CUTOFF_DEFAULT, frame: pd.DataFrame | None = None) -> pd.DataFrame` — filtered to `date >= cutoff`, sorted by date, with an added `outcome` column (`"home" | "draw" | "away"`). Also `CUTOFF_DEFAULT = "2025-01-01"`. Later tasks iterate this frame's rows and key everything on `match_id`.

- [x] **Step 1: Write the failing test**

```python
# tests/lab/test_walkback_universe.py
import pandas as pd

from wc_predictor.lab.walkback.universe import CUTOFF_DEFAULT, load_universe


def _fake_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "date": pd.to_datetime(["2024-06-01", "2025-03-10", "2025-11-02"]),
            "home_team": ["Spain", "Brazil", "Egypt"],
            "away_team": ["Austria", "Norway", "Ghana"],
            "home_score": [3, 1, 0],
            "away_score": [0, 1, 2],
            "tournament": ["Friendly"] * 3,
            "city": ["Sevilla", "Rio", "Cairo"],
            "elo_prob_home": [0.6, 0.5, 0.3],
            "elo_prob_draw": [0.25, 0.3, 0.3],
            "elo_prob_away": [0.15, 0.2, 0.4],
            "elo_home_rating": [2000.0, 2100.0, 1700.0],
            "elo_away_rating": [1800.0, 1950.0, 1750.0],
            "elo_home_advantage": [50.0, 50.0, 50.0],
            "market_prob_home": [0.65, 0.5, 0.28],
            "market_prob_draw": [0.22, 0.28, 0.32],
            "market_prob_away": [0.13, 0.22, 0.40],
        }
    )


def test_filters_to_cutoff_and_adds_outcome():
    uni = load_universe(cutoff="2025-01-01", frame=_fake_frame())
    assert list(uni["match_id"]) == ["m2", "m3"]
    assert list(uni["outcome"]) == ["draw", "away"]


def test_default_cutoff_is_2025():
    assert CUTOFF_DEFAULT == "2025-01-01"
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lab/test_walkback_universe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wc_predictor.lab.walkback'`

- [x] **Step 3: Write minimal implementation**

```python
# src/wc_predictor/lab/walkback/__init__.py
"""Local-model match-analyst walk-back experiment (plan 2026-07-03)."""
```

```python
# src/wc_predictor/lab/walkback/universe.py
"""Post-cutoff eval universe drawn from the market964 aligned frame.

The cutoff exists because local models know historical results parametrically;
only matches after the model's training cutoff are a fair test.
"""

from __future__ import annotations

import pandas as pd

CUTOFF_DEFAULT = "2025-01-01"


def _outcome(row: pd.Series) -> str:
    if row["home_score"] > row["away_score"]:
        return "home"
    if row["home_score"] < row["away_score"]:
        return "away"
    return "draw"


def load_universe(cutoff: str = CUTOFF_DEFAULT, frame: pd.DataFrame | None = None) -> pd.DataFrame:
    if frame is None:
        from wc_predictor.lab.eval_harness import build_market964_frame

        frame = build_market964_frame()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out[out["date"] >= pd.Timestamp(cutoff)].sort_values("date").reset_index(drop=True)
    out["outcome"] = out.apply(_outcome, axis=1)
    return out
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lab/test_walkback_universe.py -v`
Expected: 2 PASS

- [x] **Step 5: Sanity-check against real data (no assert, just eyeball)**

Run: `uv run python -c "from wc_predictor.lab.walkback.universe import load_universe; u = load_universe(); print(len(u), u['date'].min(), u['date'].max())"`
Expected: `443 2025-01-... 2026-06-17...` (rows on/after 2025-01-01)

- [x] **Step 6: Commit**

```bash
git add src/wc_predictor/lab/walkback/ tests/lab/test_walkback_universe.py
git commit -m "walkback: post-cutoff match universe from market964 frame"
```

---

### Task 2: GDELT news-well builder

**Files:**
- Create: `src/wc_predictor/lab/walkback/wells.py`
- Test: `tests/lab/test_walkback_wells.py`

**Interfaces:**
- Consumes: universe rows (`match_id`, `home_team`, `away_team`, `date`).
- Produces:
  - `fetch_articles(home: str, away: str, match_date: str, *, days_before: int = 7, max_records: int = 30, session=None) -> list[dict]` — each dict: `{"url", "title", "seendate" (YYYY-MM-DD), "source"}`.
  - `fetch_body(url: str, *, session=None) -> str | None` — trafilatura-extracted text, None on failure.
  - `build_well(row, *, session=None, fetch_bodies: int = 3) -> dict` — well schema below.
  - `well_path(root: Path, match_id: str) -> Path`, `save_well(well: dict, root: Path) -> Path` (refuses overwrite), `load_well(match_id: str, root: Path) -> dict | None`.
  - Well schema (later tasks rely on these exact keys):
    ```json
    {"match_id": "...", "home_team": "...", "away_team": "...",
     "match_date": "YYYY-MM-DD", "built_at": "YYYY-MM-DDTHH:MM:SS",
     "docs": [{"url": "...", "title": "...", "seendate": "YYYY-MM-DD",
               "source": "...", "body": "text or null"}]}
    ```

- [x] **Step 1: Add the trafilatura dependency**

Run: `uv add trafilatura`
Expected: resolves and adds to `pyproject.toml`.

- [x] **Step 2: Write the failing tests**

```python
# tests/lab/test_walkback_wells.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from wc_predictor.lab.walkback.wells import (
    build_well,
    fetch_articles,
    load_well,
    save_well,
    well_path,
)


def _gdelt_response():
    return {
        "articles": [
            {
                "url": "https://ex.com/preview",
                "title": "Brazil vs Norway preview",
                "seendate": "20250308T120000Z",
                "domain": "ex.com",
            },
            {
                "url": "https://ex.com/preview",  # duplicate URL -> deduped
                "title": "Brazil vs Norway preview",
                "seendate": "20250308T120000Z",
                "domain": "ex.com",
            },
        ]
    }


def _session_returning(payload):
    session = MagicMock()
    resp = MagicMock()
    resp.json.return_value = payload
    resp.status_code = 200
    session.get.return_value = resp
    return session


def test_fetch_articles_windows_query_and_dedupes():
    session = _session_returning(_gdelt_response())
    docs = fetch_articles("Brazil", "Norway", "2025-03-10", days_before=7, session=session)
    assert len(docs) == 1
    assert docs[0]["seendate"] == "2025-03-08"
    params = session.get.call_args.kwargs["params"]
    assert '"Brazil"' in params["query"] and '"Norway"' in params["query"]
    assert params["startdatetime"] == "20250303000000"
    assert params["enddatetime"] == "20250309235959"  # strictly before match day


def test_build_well_shape():
    session = _session_returning(_gdelt_response())
    row = pd.Series(
        {"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
         "date": pd.Timestamp("2025-03-10")}
    )
    well = build_well(row, session=session, fetch_bodies=0)
    assert well["match_id"] == "m2"
    assert well["match_date"] == "2025-03-10"
    assert well["docs"][0]["title"] == "Brazil vs Norway preview"
    assert well["docs"][0]["body"] is None


def test_save_well_refuses_overwrite(tmp_path: Path):
    well = {"match_id": "m2", "home_team": "a", "away_team": "b",
            "match_date": "2025-03-10", "built_at": "x", "docs": []}
    save_well(well, tmp_path)
    assert load_well("m2", tmp_path)["match_id"] == "m2"
    with pytest.raises(FileExistsError):
        save_well(well, tmp_path)
    assert load_well("missing", tmp_path) is None
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_walkback_wells.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` on `wells`

- [x] **Step 4: Write the implementation**

```python
# src/wc_predictor/lab/walkback/wells.py
"""Frozen pre-match news wells, built from the GDELT DOC 2.0 API.

A well is one JSON file per match holding only documents published strictly
before the match date. Wells are the durable dataset of this experiment:
built once, linted once, then reused to evaluate any model.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _to_date(seendate: str) -> str:
    # GDELT format: 20250308T120000Z
    return f"{seendate[0:4]}-{seendate[4:6]}-{seendate[6:8]}"


def fetch_articles(home: str, away: str, match_date: str, *, days_before: int = 7,
                   max_records: int = 30, session=None) -> list[dict]:
    session = session or requests.Session()
    end = pd.Timestamp(match_date) - timedelta(days=1)
    start = pd.Timestamp(match_date) - timedelta(days=days_before)
    params = {
        "query": f'"{home}" "{away}" sourcelang:english',
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "startdatetime": start.strftime("%Y%m%d") + "000000",
        "enddatetime": end.strftime("%Y%m%d") + "235959",
    }
    resp = session.get(GDELT_DOC_API, params=params, timeout=30)
    articles = resp.json().get("articles", []) or []
    seen: set[str] = set()
    docs: list[dict] = []
    for a in articles:
        url = a.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        docs.append(
            {"url": url, "title": a.get("title", ""),
             "seendate": _to_date(a.get("seendate", "00000000")),
             "source": a.get("domain", "")}
        )
    return docs


def fetch_body(url: str, *, session=None) -> str | None:
    try:
        import trafilatura

        session = session or requests.Session()
        resp = session.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        return trafilatura.extract(resp.text) or None
    except Exception:
        return None


def build_well(row: pd.Series, *, session=None, fetch_bodies: int = 3) -> dict:
    match_date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    docs = fetch_articles(str(row["home_team"]), str(row["away_team"]), match_date, session=session)
    for i, doc in enumerate(docs):
        doc["body"] = fetch_body(doc["url"], session=session) if i < fetch_bodies else None
    return {
        "match_id": str(row["match_id"]),
        "home_team": str(row["home_team"]),
        "away_team": str(row["away_team"]),
        "match_date": match_date,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "docs": docs,
    }


def well_path(root: Path, match_id: str) -> Path:
    return Path(root) / f"{match_id}.json"


def save_well(well: dict, root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = well_path(root, well["match_id"])
    if path.exists():
        raise FileExistsError(f"well already frozen: {path}")
    path.write_text(json.dumps(well, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_well(match_id: str, root: Path) -> dict | None:
    path = well_path(Path(root), match_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_walkback_wells.py -v`
Expected: 3 PASS

- [x] **Step 6: One real smoke fetch (rate-limit friendly, 1 request)**

Run: `uv run python -c "from wc_predictor.lab.walkback.wells import fetch_articles; d = fetch_articles('Argentina', 'Brazil', '2025-03-25'); print(len(d)); print(d[0] if d else 'EMPTY')"`
Expected: a handful of docs with `seendate` in `2025-03-18..24`. (This match — WC qualifier — really happened; if GDELT returns 0 docs, note it in the commit message: coverage is a tracked risk, not a test failure.)

- [x] **Step 7: Commit**

```bash
git add src/wc_predictor/lab/walkback/wells.py tests/lab/test_walkback_wells.py pyproject.toml uv.lock
git commit -m "walkback: GDELT news-well builder with frozen per-match JSON wells"
```

---

### Task 2b: Wells hardening — GDELT query form + non-JSON resilience (added 2026-07-03 from field evidence; Codex lane)

**Field evidence (Claude API probes, 2026-07-03):**
- `query='"Argentina" "Brazil" sourcelang:english'` (two short quoted phrases) and `query='Argentina Brazil soccer'` (bare terms) → GDELT returns a plain-text "Please limit requests to one every 5 seconds" notice instead of JSON, consistently, even when requests are spaced out. This is GDELT rejecting too-generic query forms, disguised as throttling.
- `query='"Argentina vs Brazil"'` (one quoted phrase) with the same date window → real JSON articles, including a genuine March 2025 preview. Genuine rate limiting (1 req/5s) also exists on top.
- Consequence observed in Task 2's smoke step: `fetch_articles` produced nothing on the text response because `resp.json()` has no error handling.

**Files:**
- Modify: `src/wc_predictor/lab/walkback/wells.py`
- Test: `tests/lab/test_walkback_wells.py` (update the query-construction assertion; add non-JSON retry tests)

**Requirements (do NOT run git; log evidence in co-op.md and stop when done):**

- [x] **R1 — query form:** `fetch_articles` builds `params["query"] = f'"{home} vs {away}" sourcelang:english'` (single quoted phrase). Update `test_fetch_articles_windows_query_and_dedupes` to assert `'"Brazil vs Norway"' in params["query"]` instead of the two separate quoted names.
- [x] **R2 — non-JSON resilience:** wrap the `resp.json()` call in try/except (`ValueError` covers `json.JSONDecodeError`). On failure: `time.sleep(GDELT_RETRY_WAIT)` (module constant `GDELT_RETRY_WAIT = 5.0`), re-issue the same GET once; if the retry also fails to parse, print one warning line containing the first 80 chars of `resp.text` and return `[]`. New tests (monkeypatch `wells.time.sleep` to avoid real waiting): (a) first response non-JSON, second response valid articles → docs returned and `session.get` called exactly twice; (b) both responses non-JSON → returns `[]`, no exception.
- [x] **R3 — pacing:** add module constant `GDELT_MIN_INTERVAL = 5.0` and a module-level `_last_call` timestamp guard at the top of `fetch_articles`: if the previous call was less than `GDELT_MIN_INTERVAL` seconds ago, sleep the remainder before issuing the request. Existing single-call mock tests must not slow down (first call never sleeps); the retry tests monkeypatch sleep anyway.
- [x] **R4 — run the well tests:** `uv run pytest tests/lab/test_walkback_wells.py -v` → all pass, output pristine.
- [x] **R5 — one real smoke with evidence:** `uv run python -c "from wc_predictor.lab.walkback.wells import fetch_articles; d = fetch_articles('Argentina', 'Brazil', '2025-03-25'); print(len(d)); print(d[0] if d else 'EMPTY')"` → must print a count > 0 and a first doc with a `seendate` in `2025-03-18..24`. Paste the actual output into your co-op.md log entry. *(Verified by Claude 2026-07-03 after throttle cool-down: printed `1` + thewhistler.ng doc, seendate 2025-03-19 — in window. Codex's R5 failures were transient IP throttling from the session's probe burst.)*

---

### Task 3: Leakage linter

**Files:**
- Create: `src/wc_predictor/lab/walkback/linter.py`
- Test: `tests/lab/test_walkback_linter.py`

**Interfaces:**
- Consumes: well dicts from Task 2 (`well["docs"]` with `title`, `seendate`, `body`).
- Produces:
  - `lint_doc(doc: dict, *, home: str, away: str, match_date: str) -> list[str]` — list of violation strings, empty = clean.
  - `clean_well(well: dict) -> dict` — returns a copy with only clean docs plus `well["lint"] = {"kept": int, "dropped": [{"url", "violations"}]}`.
  - `well_ok(well: dict, *, min_docs: int = 3) -> bool` — coverage gate used by the runner.

- [x] **Step 1: Write the failing tests**

```python
# tests/lab/test_walkback_linter.py
from wc_predictor.lab.walkback.linter import clean_well, lint_doc, well_ok


def _doc(**over):
    base = {"url": "https://ex.com/a", "title": "Brazil vs Norway preview",
            "seendate": "2025-03-08", "source": "ex.com", "body": None}
    base.update(over)
    return base


KW = dict(home="Brazil", away="Norway", match_date="2025-03-10")


def test_clean_doc_passes():
    assert lint_doc(_doc(), **KW) == []


def test_doc_on_or_after_match_day_rejected():
    assert "date" in ";".join(lint_doc(_doc(seendate="2025-03-10"), **KW))
    assert "date" in ";".join(lint_doc(_doc(seendate="2025-03-11"), **KW))


def test_scoreline_with_both_teams_rejected():
    body = "Brazil beat Norway 2-1 at the Maracana on Tuesday."
    assert any("score" in v for v in lint_doc(_doc(body=body), **KW))


def test_past_tense_result_language_rejected():
    body = "Norway defeated Brazil in a stunning upset."
    assert any("result-language" in v for v in lint_doc(_doc(body=body), **KW))


def test_scoreline_without_team_context_is_fine():
    body = "Haaland has 2-1 odds to score first according to bookmakers."
    # both team names absent around the score pattern -> allowed
    assert lint_doc(_doc(title="Odds roundup", body=body), **KW) == []


def test_clean_well_and_gate():
    well = {"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
            "match_date": "2025-03-10", "built_at": "x",
            "docs": [_doc(), _doc(url="u2", seendate="2025-03-11"),
                     _doc(url="u3"), _doc(url="u4")]}
    cleaned = clean_well(well)
    assert cleaned["lint"]["kept"] == 3
    assert cleaned["lint"]["dropped"][0]["url"] == "u2"
    assert well_ok(cleaned) is True
    assert well_ok(cleaned, min_docs=4) is False
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_walkback_linter.py -v`
Expected: FAIL with `ModuleNotFoundError` on `linter`

- [x] **Step 3: Write the implementation**

```python
# src/wc_predictor/lab/walkback/linter.py
"""Leakage linter for news wells.

Belt and braces on top of the GDELT date window: a doc is rejected if it is
dated on/after match day, or if its text pairs both team names with a
scoreline or past-tense result language. False positives are acceptable —
dropping a clean preview costs a little coverage; keeping a leaky doc
invalidates the match.
"""

from __future__ import annotations

import re

SCORE_RE = re.compile(r"\b\d{1,2}\s?[-–:]\s?\d{1,2}\b")
RESULT_WORDS_RE = re.compile(
    r"\b(beat|defeated|won|lost to|thrashed|edged|drew with|held)\b", re.IGNORECASE
)


def _text(doc: dict) -> str:
    return f"{doc.get('title') or ''}\n{doc.get('body') or ''}"


def lint_doc(doc: dict, *, home: str, away: str, match_date: str) -> list[str]:
    violations: list[str] = []
    if str(doc.get("seendate", "9999")) >= str(match_date):
        violations.append(f"date: {doc.get('seendate')} not before {match_date}")
    text = _text(doc)
    both_teams = re.search(re.escape(home), text, re.I) and re.search(re.escape(away), text, re.I)
    if both_teams and SCORE_RE.search(text):
        violations.append("score: scoreline pattern with both team names present")
    if both_teams and RESULT_WORDS_RE.search(text):
        violations.append("result-language: past-tense result verb with both team names")
    return violations


def clean_well(well: dict) -> dict:
    kept, dropped = [], []
    for doc in well.get("docs", []):
        v = lint_doc(doc, home=well["home_team"], away=well["away_team"],
                     match_date=well["match_date"])
        if v:
            dropped.append({"url": doc.get("url", ""), "violations": v})
        else:
            kept.append(doc)
    out = dict(well)
    out["docs"] = kept
    out["lint"] = {"kept": len(kept), "dropped": dropped}
    return out


def well_ok(well: dict, *, min_docs: int = 3) -> bool:
    return len(well.get("docs", [])) >= min_docs
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_walkback_linter.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/wc_predictor/lab/walkback/linter.py tests/lab/test_walkback_linter.py
git commit -m "walkback: leakage linter (date window + score/result-language rules)"
```

**Note for the implementer:** the result-language rule WILL reject some clean previews ("Brazil beat Norway in their last meeting in 2019"). That is the intended trade-off (see module docstring). Do not "improve" the linter to be more permissive without adding a regression test proving the leaky case still fails.

---

### Task 4: LM Studio client with strict-JSON chat

**Files:**
- Create: `src/wc_predictor/lab/walkback/llm.py`
- Test: `tests/lab/test_walkback_llm.py`

**Interfaces:**
- Consumes: nothing internal — wraps the LM Studio OpenAI-compatible endpoint.
- Produces: `LMClient(base_url: str = "http://localhost:1234/v1", model: str = "", temperature: float = 0.0, timeout: int = 180)` with method `chat_json(self, system: str, user: str, *, max_retries: int = 2, session=None) -> dict` — sends a chat completion, extracts the first JSON object from the reply (handles ```json fences), retries with an explicit "reply with only valid JSON" nudge, raises `ValueError` after exhausting retries. Tasks 5–7 depend on this exact signature.

- [ ] **Step 1: Write the failing tests**

```python
# tests/lab/test_walkback_llm.py
from unittest.mock import MagicMock

import pytest

from wc_predictor.lab.walkback.llm import LMClient


def _session_replying(*contents):
    session = MagicMock()
    responses = []
    for content in contents:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        responses.append(resp)
    session.post.side_effect = responses
    return session


def test_parses_plain_json():
    session = _session_replying('{"p_home": 0.5, "p_draw": 0.3, "p_away": 0.2}')
    out = LMClient(model="test").chat_json("sys", "user", session=session)
    assert out["p_home"] == 0.5


def test_parses_fenced_json_with_prose():
    content = 'Sure! Here is my forecast:\n```json\n{"pick": "home"}\n```\nGood luck!'
    session = _session_replying(content)
    assert LMClient(model="test").chat_json("s", "u", session=session)["pick"] == "home"


def test_retries_then_raises():
    session = _session_replying("not json", "still not json", "nope")
    with pytest.raises(ValueError):
        LMClient(model="test").chat_json("s", "u", max_retries=2, session=session)
    assert session.post.call_count == 3


def test_request_is_deterministic():
    session = _session_replying('{"a": 1}')
    LMClient(model="qwen2.5-14b-instruct").chat_json("s", "u", session=session)
    body = session.post.call_args.kwargs["json"]
    assert body["temperature"] == 0.0
    assert body["model"] == "qwen2.5-14b-instruct"
    assert body["messages"][0] == {"role": "system", "content": "s"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_walkback_llm.py -v`
Expected: FAIL with `ModuleNotFoundError` on `llm`

- [ ] **Step 3: Write the implementation**

```python
# src/wc_predictor/lab/walkback/llm.py
"""Minimal LM Studio (OpenAI-compatible) chat client returning strict JSON.

No agentic tool use by design: 8-14B local models are unreliable tool callers,
and a single deterministic completion keeps the experiment reproducible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(content: str) -> dict | None:
    match = _JSON_RE.search(content)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


@dataclass
class LMClient:
    base_url: str = "http://localhost:1234/v1"
    model: str = ""
    temperature: float = 0.0
    timeout: int = 180

    def chat_json(self, system: str, user: str, *, max_retries: int = 2, session=None) -> dict:
        session = session or requests.Session()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(max_retries + 1):
            resp = session.post(
                f"{self.base_url}/chat/completions",
                json={"model": self.model, "messages": messages,
                      "temperature": self.temperature},
                timeout=self.timeout,
            )
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            if parsed is not None:
                return parsed
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user",
                             "content": "Reply with ONLY a valid JSON object. No prose."})
        raise ValueError(f"no valid JSON after {max_retries + 1} attempts")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_walkback_llm.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/wc_predictor/lab/walkback/llm.py tests/lab/test_walkback_llm.py
git commit -m "walkback: deterministic LM Studio chat client with strict-JSON parsing"
```

---

### Task 5: Parametric-recall contamination screen

**Files:**
- Create: `src/wc_predictor/lab/walkback/recall.py`
- Test: `tests/lab/test_walkback_recall.py`

**Interfaces:**
- Consumes: universe rows (Task 1) and `LMClient.chat_json` (Task 4).
- Produces: `recall_check(row, client: LMClient) -> dict` returning `{"match_id", "contaminated": bool, "recalled": {...raw model json...}}`. Contamination rule: **contaminated only if the model states the exact final score correctly** (correct-outcome-only is NOT contamination — excluding correctly-guessed outcomes would preferentially remove favorite-wins and bias the sample toward upsets; exact-score-by-chance is ~10%, an acceptable false-flag rate).

- [ ] **Step 1: Write the failing tests**

```python
# tests/lab/test_walkback_recall.py
from unittest.mock import MagicMock

import pandas as pd

from wc_predictor.lab.walkback.recall import recall_check


def _row(hs=2, aws=1):
    return pd.Series({"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
                      "date": pd.Timestamp("2025-03-10"),
                      "home_score": hs, "away_score": aws})


def _client_recalling(payload):
    client = MagicMock()
    client.chat_json.return_value = payload
    return client


def test_exact_score_recall_is_contaminated():
    client = _client_recalling({"known": True, "home_goals": 2, "away_goals": 1})
    assert recall_check(_row(), client)["contaminated"] is True


def test_correct_outcome_wrong_score_is_not_contaminated():
    client = _client_recalling({"known": True, "home_goals": 3, "away_goals": 0})
    assert recall_check(_row(), client)["contaminated"] is False


def test_unknown_is_not_contaminated():
    client = _client_recalling({"known": False, "home_goals": None, "away_goals": None})
    assert recall_check(_row(), client)["contaminated"] is False


def test_prompt_does_not_leak_the_result():
    client = _client_recalling({"known": False, "home_goals": None, "away_goals": None})
    recall_check(_row(), client)
    user_prompt = client.chat_json.call_args[0][1]
    assert "2" not in user_prompt.replace("2025", "")  # scores absent (date year allowed)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_walkback_recall.py -v`
Expected: FAIL with `ModuleNotFoundError` on `recall`

- [ ] **Step 3: Write the implementation**

```python
# src/wc_predictor/lab/walkback/recall.py
"""Parametric-memory contamination screen.

A local model may know a match result from training data. Before evaluating a
model on a match we ask it point-blank for the final score. Only an exact
correct score counts as contamination: excluding correct-outcome guesses would
strip favorite-wins from the sample and bias the eval toward upsets.
"""

from __future__ import annotations

import pandas as pd

from wc_predictor.lab.walkback.llm import LMClient

_SYSTEM = (
    "You are a sports results database. If you know the actual final result of the "
    "requested match from your training data, report it. If you do not know it, say so. "
    'Reply ONLY with JSON: {"known": true/false, "home_goals": int or null, '
    '"away_goals": int or null}. Never guess.'
)


def recall_check(row: pd.Series, client: LMClient) -> dict:
    date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    user = (
        f"What was the final score of {row['home_team']} vs {row['away_team']} "
        f"(men's international football) played on {date}?"
    )
    recalled = client.chat_json(_SYSTEM, user)
    contaminated = (
        bool(recalled.get("known"))
        and recalled.get("home_goals") == int(row["home_score"])
        and recalled.get("away_goals") == int(row["away_score"])
    )
    return {"match_id": str(row["match_id"]), "contaminated": contaminated, "recalled": recalled}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_walkback_recall.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/wc_predictor/lab/walkback/recall.py tests/lab/test_walkback_recall.py
git commit -m "walkback: parametric-recall contamination screen (exact-score rule)"
```

---

### Task 6: Forecast harness (three ablation conditions)

**Files:**
- Create: `src/wc_predictor/lab/walkback/harness.py`
- Test: `tests/lab/test_walkback_harness.py`

**Interfaces:**
- Consumes: universe rows (Task 1), clean wells (Task 3), `LMClient.chat_json` (Task 4).
- Produces:
  - `CONDITIONS = ("stats", "news", "both")`
  - `build_prompt(row, well: dict | None, condition: str) -> tuple[str, str]` — (system, user). **`market_prob_*` must never appear in any prompt.**
  - `forecast_one(row, well: dict | None, condition: str, client: LMClient) -> dict` — `{"match_id", "condition", "model", "p_home", "p_draw", "p_away", "pick"}` with probs clamped to ≥0.001 and renormalized to sum 1.0; `pick` = argmax outcome.

- [ ] **Step 1: Write the failing tests**

```python
# tests/lab/test_walkback_harness.py
from unittest.mock import MagicMock

import pandas as pd
import pytest

from wc_predictor.lab.walkback.harness import CONDITIONS, build_prompt, forecast_one


def _row():
    return pd.Series({
        "match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
        "date": pd.Timestamp("2025-03-10"), "city": "Rio", "tournament": "Friendly",
        "elo_prob_home": 0.5, "elo_prob_draw": 0.3, "elo_prob_away": 0.2,
        "elo_home_rating": 2100.0, "elo_away_rating": 1950.0, "elo_home_advantage": 50.0,
        "market_prob_home": 0.55, "market_prob_draw": 0.27, "market_prob_away": 0.18,
        "home_score": 1, "away_score": 1, "outcome": "draw",
    })


def _well():
    return {"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
            "match_date": "2025-03-10", "built_at": "x",
            "docs": [{"url": "u", "title": "Haaland doubtful with knock",
                      "seendate": "2025-03-08", "source": "ex.com", "body": "Short body."}]}


def test_market_never_in_any_prompt():
    for condition in CONDITIONS:
        system, user = build_prompt(_row(), _well(), condition)
        blob = system + user
        assert "0.55" not in blob and "market" not in blob.lower()


def test_stats_condition_has_elo_no_news():
    _, user = build_prompt(_row(), _well(), "stats")
    assert "2100" in user and "Haaland" not in user


def test_news_condition_has_news_no_elo():
    _, user = build_prompt(_row(), _well(), "news")
    assert "Haaland" in user and "2100" not in user


def test_both_condition_has_both():
    _, user = build_prompt(_row(), _well(), "both")
    assert "Haaland" in user and "2100" in user


def test_news_condition_requires_well():
    with pytest.raises(ValueError):
        build_prompt(_row(), None, "news")


def test_forecast_one_normalizes_and_picks():
    client = MagicMock()
    client.model = "test-model"
    client.chat_json.return_value = {"p_home": 0.9, "p_draw": 0.3, "p_away": 0.0}
    out = forecast_one(_row(), _well(), "both", client)
    total = out["p_home"] + out["p_draw"] + out["p_away"]
    assert abs(total - 1.0) < 1e-9
    assert out["p_away"] > 0.0  # clamped, not zero
    assert out["pick"] == "home"
    assert out["condition"] == "both" and out["model"] == "test-model"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_walkback_harness.py -v`
Expected: FAIL with `ModuleNotFoundError` on `harness`

- [ ] **Step 3: Write the implementation**

```python
# src/wc_predictor/lab/walkback/harness.py
"""Single-shot forecast harness for the walk-back ablations.

Three conditions, market NEVER shown (that is the whole experiment — with the
market in the prompt the task degenerates to copying a number):
  stats — Elo ratings/probs + venue/tournament, no news
  news  — linted news docs only, no model numbers
  both  — stats + news
"""

from __future__ import annotations

import pandas as pd

from wc_predictor.lab.walkback.llm import LMClient

CONDITIONS = ("stats", "news", "both")

_SYSTEM = (
    "You are a professional football (soccer) match forecaster. Estimate honest "
    "probabilities for the home win / draw / away win of the upcoming match using ONLY "
    "the information provided. Do not use any knowledge of what actually happened. "
    'Reply ONLY with JSON: {"p_home": float, "p_draw": float, "p_away": float, '
    '"reasoning": "one sentence"}. Probabilities must sum to 1.'
)


def _stats_block(row: pd.Series) -> str:
    return (
        f"Elo ratings: {row['home_team']} {row['elo_home_rating']:.0f}, "
        f"{row['away_team']} {row['elo_away_rating']:.0f} "
        f"(home advantage {row['elo_home_advantage']:.0f} Elo).\n"
        f"Elo model probabilities: home {row['elo_prob_home']:.3f}, "
        f"draw {row['elo_prob_draw']:.3f}, away {row['elo_prob_away']:.3f}."
    )


def _news_block(well: dict) -> str:
    lines = []
    for doc in well["docs"][:10]:
        lines.append(f"- [{doc['seendate']}] ({doc['source']}) {doc['title']}")
        if doc.get("body"):
            lines.append(f"  {doc['body'][:1500]}")
    return "Pre-match news (published before match day):\n" + "\n".join(lines)


def build_prompt(row: pd.Series, well: dict | None, condition: str) -> tuple[str, str]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if condition in ("news", "both") and not well:
        raise ValueError(f"condition {condition!r} requires a news well")
    date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    parts = [
        f"Match: {row['home_team']} (home) vs {row['away_team']} (away)",
        f"Date: {date} | Venue: {row.get('city', '')} | Competition: {row.get('tournament', '')}",
    ]
    if condition in ("stats", "both"):
        parts.append(_stats_block(row))
    if condition in ("news", "both"):
        parts.append(_news_block(well))
    parts.append("Forecast this match now.")
    return _SYSTEM, "\n\n".join(parts)


def _normalize(p: tuple[float, float, float]) -> tuple[float, float, float]:
    clamped = [max(0.001, float(x)) for x in p]
    total = sum(clamped)
    return tuple(x / total for x in clamped)


def forecast_one(row: pd.Series, well: dict | None, condition: str, client: LMClient) -> dict:
    system, user = build_prompt(row, well, condition)
    raw = client.chat_json(system, user)
    p_home, p_draw, p_away = _normalize(
        (raw.get("p_home", 1 / 3), raw.get("p_draw", 1 / 3), raw.get("p_away", 1 / 3))
    )
    pick = ("home", "draw", "away")[max(range(3), key=[p_home, p_draw, p_away].__getitem__)]
    return {"match_id": str(row["match_id"]), "condition": condition, "model": client.model,
            "p_home": p_home, "p_draw": p_draw, "p_away": p_away, "pick": pick}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_walkback_harness.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/wc_predictor/lab/walkback/harness.py tests/lab/test_walkback_harness.py
git commit -m "walkback: single-shot forecast harness, 3 ablations, market never shown"
```

---

### Task 7: Batch runner CLI (resumable)

**Files:**
- Create: `src/wc_predictor/lab/walkback/cli.py`
- Create: `src/wc_predictor/lab/walkback/__main__.py`
- Test: `tests/lab/test_walkback_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `python -m wc_predictor.lab.walkback <subcommand>`:
  - `build-wells --cutoff 2025-01-01 --root runs/newswells [--limit N] [--sleep 5.0]` — builds + lints + saves missing wells (skips existing files, honors append-only).
  - `recall --model <id> --cutoff <d> --out runs/analyst_walkback/recall_<model>.jsonl`
  - `run --model <id> --condition stats|news|both --cutoff <d> --wells-root runs/newswells --out runs/analyst_walkback/preds.jsonl` — resumable: skips (match_id, model, condition) already in the output; skips matches whose well fails `well_ok` for news/both; per-match try/except (log and continue).
  - Core function (unit-testable, CLI is a thin wrapper): `run_batch(universe, wells_root, client, condition, out_path) -> dict` returning `{"done": int, "skipped_existing": int, "skipped_no_well": int, "errors": int}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/lab/test_walkback_cli.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from wc_predictor.lab.walkback.cli import run_batch
from wc_predictor.lab.walkback.wells import save_well


def _universe():
    return pd.DataFrame({
        "match_id": ["m1", "m2"],
        "home_team": ["Brazil", "Spain"], "away_team": ["Norway", "Austria"],
        "date": pd.to_datetime(["2025-03-10", "2025-03-11"]),
        "city": ["Rio", "Sevilla"], "tournament": ["Friendly"] * 2,
        "elo_prob_home": [0.5, 0.6], "elo_prob_draw": [0.3, 0.25], "elo_prob_away": [0.2, 0.15],
        "elo_home_rating": [2100.0, 2000.0], "elo_away_rating": [1950.0, 1800.0],
        "elo_home_advantage": [50.0, 50.0],
        "home_score": [1, 3], "away_score": [1, 0], "outcome": ["draw", "home"],
    })


def _mk_well(match_id, home, away, root, n_docs=3):
    docs = [{"url": f"u{i}", "title": f"{home} team news {i}", "seendate": "2025-03-08",
             "source": "ex.com", "body": None} for i in range(n_docs)]
    save_well({"match_id": match_id, "home_team": home, "away_team": away,
               "match_date": "2025-03-10", "built_at": "x", "docs": docs}, root)


def test_run_batch_resumes_and_gates(tmp_path: Path):
    wells_root = tmp_path / "wells"
    _mk_well("m1", "Brazil", "Norway", wells_root, n_docs=3)
    _mk_well("m2", "Spain", "Austria", wells_root, n_docs=1)  # below min_docs gate
    out = tmp_path / "preds.jsonl"
    # pre-existing prediction for m1 -> must be skipped
    out.write_text(json.dumps({"match_id": "m1", "condition": "news",
                               "model": "test-model"}) + "\n", encoding="utf-8")

    client = MagicMock()
    client.model = "test-model"
    client.chat_json.return_value = {"p_home": 0.4, "p_draw": 0.3, "p_away": 0.3}

    stats = run_batch(_universe(), wells_root, client, "news", out)
    assert stats == {"done": 0, "skipped_existing": 1, "skipped_no_well": 1, "errors": 0}

    stats2 = run_batch(_universe(), wells_root, client, "stats", out)
    assert stats2["done"] == 2  # stats condition needs no well
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3


def test_run_batch_survives_client_errors(tmp_path: Path):
    out = tmp_path / "preds.jsonl"
    client = MagicMock()
    client.model = "test-model"
    client.chat_json.side_effect = ValueError("no valid JSON")
    stats = run_batch(_universe(), tmp_path / "none", client, "stats", out)
    assert stats["errors"] == 2 and stats["done"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lab/test_walkback_cli.py -v`
Expected: FAIL with `ModuleNotFoundError` on `cli`

- [ ] **Step 3: Write the implementation**

```python
# src/wc_predictor/lab/walkback/cli.py
"""CLI for the walk-back experiment: build wells, screen recall, run models."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from wc_predictor.lab.walkback.harness import CONDITIONS, forecast_one
from wc_predictor.lab.walkback.linter import clean_well, well_ok
from wc_predictor.lab.walkback.llm import LMClient
from wc_predictor.lab.walkback.recall import recall_check
from wc_predictor.lab.walkback.universe import CUTOFF_DEFAULT, load_universe
from wc_predictor.lab.walkback.wells import build_well, load_well, save_well, well_path


def _existing_keys(out_path: Path) -> set[tuple[str, str, str]]:
    if not Path(out_path).exists():
        return set()
    keys = set()
    for line in Path(out_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        keys.add((str(r["match_id"]), str(r["model"]), str(r["condition"])))
    return keys


def run_batch(universe: pd.DataFrame, wells_root: Path, client: LMClient,
              condition: str, out_path: Path) -> dict:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_keys(out_path)
    stats = {"done": 0, "skipped_existing": 0, "skipped_no_well": 0, "errors": 0}
    with out_path.open("a", encoding="utf-8") as fh:
        for _, row in universe.iterrows():
            key = (str(row["match_id"]), client.model, condition)
            if key in existing:
                stats["skipped_existing"] += 1
                continue
            well = None
            if condition in ("news", "both"):
                well = load_well(str(row["match_id"]), wells_root)
                if well is None or not well_ok(well):
                    stats["skipped_no_well"] += 1
                    continue
            try:
                pred = forecast_one(row, well, condition, client)
            except Exception as exc:
                print(f"  ERROR {row['match_id']}: {exc}")
                stats["errors"] += 1
                continue
            fh.write(json.dumps(pred) + "\n")
            fh.flush()
            stats["done"] += 1
    return stats


def cmd_build_wells(args: argparse.Namespace) -> None:
    universe = load_universe(cutoff=args.cutoff)
    if args.limit:
        universe = universe.head(args.limit)
    root = Path(args.root)
    built = skipped = 0
    for _, row in universe.iterrows():
        if well_path(root, str(row["match_id"])).exists():
            skipped += 1
            continue
        well = clean_well(build_well(row))
        save_well(well, root)
        built += 1
        print(f"{row['match_id']}: kept {well['lint']['kept']} docs "
              f"({row['home_team']} v {row['away_team']})")
        time.sleep(args.sleep)
    print(f"built {built}, skipped existing {skipped}")


def cmd_recall(args: argparse.Namespace) -> None:
    universe = load_universe(cutoff=args.cutoff)
    client = LMClient(model=args.model)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_bad = 0
    with out.open("w", encoding="utf-8") as fh:
        for _, row in universe.iterrows():
            try:
                res = recall_check(row, client)
            except Exception as exc:
                res = {"match_id": str(row["match_id"]), "contaminated": False,
                       "recalled": {"error": str(exc)}}
            n_bad += res["contaminated"]
            fh.write(json.dumps(res) + "\n")
    rate = n_bad / max(1, len(universe))
    print(f"contaminated: {n_bad}/{len(universe)} ({rate:.1%})")
    if rate > 0.15:
        print("WARNING: >15% contamination — move --cutoff later for this model.")


def cmd_run(args: argparse.Namespace) -> None:
    universe = load_universe(cutoff=args.cutoff)
    recall_path = Path(args.out).parent / f"recall_{args.model}.jsonl"
    if recall_path.exists():
        bad = {json.loads(l)["match_id"]
               for l in recall_path.read_text(encoding="utf-8").splitlines()
               if l.strip() and json.loads(l)["contaminated"]}
        universe = universe[~universe["match_id"].astype(str).isin(bad)]
        print(f"excluded {len(bad)} contaminated matches (recall screen)")
    client = LMClient(model=args.model)
    stats = run_batch(universe, Path(args.wells_root), client, args.condition, Path(args.out))
    print(stats)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m wc_predictor.lab.walkback")
    sub = parser.add_subparsers(required=True)

    bw = sub.add_parser("build-wells", help="freeze GDELT wells for the universe")
    bw.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    bw.add_argument("--root", default="runs/newswells")
    bw.add_argument("--limit", type=int, default=0)
    bw.add_argument("--sleep", type=float, default=5.0)  # GDELT hard-limits to 1 req/5s
    bw.set_defaults(func=cmd_build_wells)

    rc = sub.add_parser("recall", help="parametric-recall contamination screen")
    rc.add_argument("--model", required=True)
    rc.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    rc.add_argument("--out", required=True)
    rc.set_defaults(func=cmd_recall)

    rn = sub.add_parser("run", help="run one model x condition over the universe")
    rn.add_argument("--model", required=True)
    rn.add_argument("--condition", choices=list(CONDITIONS), required=True)
    rn.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    rn.add_argument("--wells-root", default="runs/newswells")
    rn.add_argument("--out", default="runs/analyst_walkback/preds.jsonl")
    rn.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    args.func(args)
```

```python
# src/wc_predictor/lab/walkback/__main__.py
from wc_predictor.lab.walkback.cli import main

main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_walkback_cli.py -v`
Expected: 2 PASS

- [ ] **Step 5: Run the full walkback test suite**

Run: `uv run pytest tests/lab/test_walkback_*.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/wc_predictor/lab/walkback/cli.py src/wc_predictor/lab/walkback/__main__.py tests/lab/test_walkback_cli.py
git commit -m "walkback: resumable batch runner CLI (build-wells / recall / run)"
```

---

### Task 8: Evaluation — ladder, paired CIs, calibration, report

**Files:**
- Create: `src/wc_predictor/lab/walkback/evaluate.py`
- Modify: `src/wc_predictor/lab/walkback/cli.py` (add `evaluate` subcommand)
- Test: `tests/lab/test_walkback_evaluate.py`

**Interfaces:**
- Consumes: prediction JSONL rows from Task 7; universe frame from Task 1; `ranked_probability_score(probs: Sequence[float], outcome: str) -> float` and `bootstrap_ci(values, n_boot=1000, alpha=0.05, seed=0) -> (point, low, high, n)` from `wc_predictor.evaluation.metrics`.
- Produces:
  - `evaluate(universe: pd.DataFrame, preds: list[dict]) -> dict` — for each (model, condition) lane: `n`, `rps`, `vs_elo` and `vs_market` paired bootstrap `(point, lo, hi)` **computed on that lane's matches only**, plus ladder rows for `climatology`, `elo`, `market` on the same matched subset, plus calibration: `{"temp", "rps_raw", "rps_temp", "clump_top10"}` (temp fitted on even-indexed matches by date, applied to odd-indexed — leak-free split; clump_top10 = the 10 most frequent rounded (p_h,p_d,p_a) triples, exposing probability clumping).
  - `write_report(results: dict, path: Path) -> None` — markdown to `reports/backtests/local_analyst_walkback.md`.
  - Climatology = outcome frequencies of market964 rows **before** the cutoff (leak-free constant baseline): `climatology_probs(frame, cutoff) -> tuple[float, float, float]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/lab/test_walkback_evaluate.py
import pandas as pd

from wc_predictor.lab.walkback.evaluate import climatology_probs, evaluate, fit_temperature


def _universe(n=40):
    # alternating outcomes, elo/market mildly informative
    rows = []
    for i in range(n):
        outcome = ("home", "draw", "away")[i % 3]
        rows.append({
            "match_id": f"m{i}", "date": pd.Timestamp("2025-02-01") + pd.Timedelta(days=i),
            "home_team": "H", "away_team": "A", "home_score": 0, "away_score": 0,
            "outcome": outcome,
            "elo_prob_home": 0.45, "elo_prob_draw": 0.30, "elo_prob_away": 0.25,
            "market_prob_home": 0.46, "market_prob_draw": 0.29, "market_prob_away": 0.25,
        })
    return pd.DataFrame(rows)


def _preds(universe, p=(0.4, 0.3, 0.3)):
    return [{"match_id": str(r["match_id"]), "model": "test-model", "condition": "both",
             "p_home": p[0], "p_draw": p[1], "p_away": p[2], "pick": "home"}
            for _, r in universe.iterrows()]


def test_evaluate_produces_lane_and_ladder():
    uni = _universe()
    res = evaluate(uni, _preds(uni))
    lane = res["lanes"]["test-model/both"]
    assert lane["n"] == 40
    assert 0.0 < lane["rps"] < 1.0
    assert set(lane["vs_elo"]) == {"point", "lo", "hi"}
    assert set(res["ladder"]) >= {"climatology", "elo", "market", "test-model/both"}


def test_perfect_predictions_beat_elo():
    uni = _universe()
    preds = []
    for _, r in uni.iterrows():
        p = {"home": (0.98, 0.01, 0.01), "draw": (0.01, 0.98, 0.01),
             "away": (0.01, 0.01, 0.98)}[r["outcome"]]
        preds.append({"match_id": str(r["match_id"]), "model": "oracle", "condition": "both",
                      "p_home": p[0], "p_draw": p[1], "p_away": p[2], "pick": r["outcome"]})
    res = evaluate(uni, preds)
    assert res["lanes"]["oracle/both"]["vs_elo"]["hi"] < 0  # CI excludes 0, oracle better


def test_climatology_uses_only_pre_cutoff_rows():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2025-06-01"]),
        "outcome": ["home", "home", "away"],
    })
    probs = climatology_probs(frame, cutoff="2025-01-01")
    assert probs[0] == 1.0  # only the two pre-cutoff home wins count


def test_fit_temperature_flattens_overconfidence():
    # overconfident probs on a coin-flip-ish sample -> fitted T > 1 (softens)
    probs = [(0.8, 0.1, 0.1)] * 30
    outcomes = (["home"] * 12) + (["draw"] * 9) + (["away"] * 9)
    temp = fit_temperature(probs, outcomes)
    assert temp > 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/lab/test_walkback_evaluate.py -v`
Expected: FAIL with `ModuleNotFoundError` on `evaluate`

- [ ] **Step 3: Write the implementation**

```python
# src/wc_predictor/lab/walkback/evaluate.py
"""Evaluation: accuracy ladder, paired bootstrap CIs, calibration analysis.

Every lane (model x condition) is compared PAIRED against elo and market on
exactly the matches that lane predicted — same protocol as the fusion ledger.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score

from wc_predictor.lab.walkback.universe import CUTOFF_DEFAULT


def climatology_probs(frame: pd.DataFrame, cutoff: str = CUTOFF_DEFAULT) -> tuple[float, float, float]:
    pre = frame[pd.to_datetime(frame["date"]) < pd.Timestamp(cutoff)]
    counts = pre["outcome"].value_counts()
    total = max(1, int(counts.sum()))
    return tuple(float(counts.get(k, 0)) / total for k in ("home", "draw", "away"))


def _rps_series(probs_list, outcomes) -> list[float]:
    return [ranked_probability_score(p, o) for p, o in zip(probs_list, outcomes)]


def _paired(diffs: list[float]) -> dict:
    point, lo, hi, _ = bootstrap_ci(diffs, n_boot=2000, alpha=0.05, seed=0)
    return {"point": point, "lo": lo, "hi": hi}


def _apply_temp(p: tuple[float, float, float], temp: float) -> tuple[float, float, float]:
    powered = [max(1e-9, x) ** (1.0 / temp) for x in p]
    total = sum(powered)
    return tuple(x / total for x in powered)


def fit_temperature(probs_list, outcomes, grid=None) -> float:
    grid = grid or [round(0.5 + 0.05 * i, 2) for i in range(51)]  # 0.5 .. 3.0
    best_t, best_rps = 1.0, float("inf")
    for t in grid:
        rps = sum(_rps_series([_apply_temp(p, t) for p in probs_list], outcomes))
        if rps < best_rps:
            best_t, best_rps = t, rps
    return best_t


def _calibration(probs_list, outcomes) -> dict:
    fit_p = probs_list[0::2]
    fit_o = outcomes[0::2]
    hold_p = probs_list[1::2]
    hold_o = outcomes[1::2]
    temp = fit_temperature(fit_p, fit_o) if len(fit_p) >= 10 else 1.0
    rps_raw = sum(_rps_series(hold_p, hold_o)) / max(1, len(hold_p))
    rps_temp = sum(
        _rps_series([_apply_temp(p, temp) for p in hold_p], hold_o)
    ) / max(1, len(hold_p))
    clump = Counter(tuple(round(x, 2) for x in p) for p in probs_list)
    return {"temp": temp, "rps_raw": rps_raw, "rps_temp": rps_temp,
            "clump_top10": clump.most_common(10)}


def evaluate(universe: pd.DataFrame, preds: list[dict]) -> dict:
    uni = universe.copy()
    uni["match_id"] = uni["match_id"].astype(str)
    uni = uni.set_index("match_id", drop=False)
    clim = climatology_probs(universe)

    lanes: dict[str, dict] = {}
    ladder: dict[str, dict] = {}
    by_lane: dict[str, list[dict]] = {}
    for p in preds:
        by_lane.setdefault(f"{p['model']}/{p['condition']}", []).append(p)

    for lane_key, rows in sorted(by_lane.items()):
        rows = [r for r in rows if str(r["match_id"]) in uni.index]
        rows.sort(key=lambda r: str(uni.loc[str(r["match_id"]), "date"]))
        outcomes = [str(uni.loc[str(r["match_id"]), "outcome"]) for r in rows]
        model_p = [(r["p_home"], r["p_draw"], r["p_away"]) for r in rows]
        elo_p = [tuple(uni.loc[str(r["match_id"]), ["elo_prob_home", "elo_prob_draw", "elo_prob_away"]])
                 for r in rows]
        mkt_p = [tuple(uni.loc[str(r["match_id"]), ["market_prob_home", "market_prob_draw", "market_prob_away"]])
                 for r in rows]
        model_rps = _rps_series(model_p, outcomes)
        elo_rps = _rps_series(elo_p, outcomes)
        mkt_rps = _rps_series(mkt_p, outcomes)
        clim_rps = _rps_series([clim] * len(rows), outcomes)
        n = len(rows)
        lanes[lane_key] = {
            "n": n,
            "rps": sum(model_rps) / max(1, n),
            "vs_elo": _paired([m - e for m, e in zip(model_rps, elo_rps)]),
            "vs_market": _paired([m - k for m, k in zip(model_rps, mkt_rps)]),
            "calibration": _calibration(model_p, outcomes),
        }
        ladder[lane_key] = {"n": n, "rps": lanes[lane_key]["rps"]}
        ladder.setdefault("climatology", {"n": n, "rps": sum(clim_rps) / max(1, n)})
        ladder.setdefault("elo", {"n": n, "rps": sum(elo_rps) / max(1, n)})
        ladder.setdefault("market", {"n": n, "rps": sum(mkt_rps) / max(1, n)})

    return {"lanes": lanes, "ladder": ladder}


def write_report(results: dict, path: Path) -> None:
    lines = ["# Local-model match-analyst walk-back", ""]
    lines += ["## Accuracy ladder (lower RPS = better)", "",
              "| Lane | n | RPS |", "| --- | ---: | ---: |"]
    for name, row in sorted(results["ladder"].items(), key=lambda kv: kv[1]["rps"]):
        lines.append(f"| {name} | {row['n']} | {row['rps']:.5f} |")
    lines += ["", "## Paired comparisons (RPS diff, negative = lane better)", ""]
    for lane_key, lane in results["lanes"].items():
        ve, vm = lane["vs_elo"], lane["vs_market"]
        cal = lane["calibration"]
        lines += [
            f"### {lane_key} (n={lane['n']})",
            f"- vs elo: {ve['point']:+.5f} CI [{ve['lo']:+.5f}, {ve['hi']:+.5f}]",
            f"- vs market: {vm['point']:+.5f} CI [{vm['lo']:+.5f}, {vm['hi']:+.5f}]",
            f"- calibration: temp {cal['temp']:.2f}, holdout RPS raw {cal['rps_raw']:.5f} "
            f"-> temp-scaled {cal['rps_temp']:.5f}",
            f"- clumping (top triples): {cal['clump_top10'][:3]}",
            "",
        ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Add the `evaluate` subcommand to the CLI**

In `src/wc_predictor/lab/walkback/cli.py`, add this command function after `cmd_run`:

```python
def cmd_evaluate(args: argparse.Namespace) -> None:
    from wc_predictor.lab.walkback.evaluate import evaluate, write_report

    universe = load_universe(cutoff=args.cutoff)
    preds = [json.loads(l) for l in Path(args.preds).read_text(encoding="utf-8").splitlines()
             if l.strip()]
    results = evaluate(universe, preds)
    write_report(results, Path(args.report))
    print(json.dumps(results["ladder"], indent=1))
```

and register it inside `main()` before `parser.parse_args`:

```python
    ev = sub.add_parser("evaluate", help="ladder + paired CIs + calibration report")
    ev.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    ev.add_argument("--preds", default="runs/analyst_walkback/preds.jsonl")
    ev.add_argument("--report", default="reports/backtests/local_analyst_walkback.md")
    ev.set_defaults(func=cmd_evaluate)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/lab/test_walkback_evaluate.py tests/lab/test_walkback_cli.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/wc_predictor/lab/walkback/evaluate.py src/wc_predictor/lab/walkback/cli.py tests/lab/test_walkback_evaluate.py
git commit -m "walkback: evaluation ladder, paired bootstrap CIs, calibration + report"
```

---

### Task 9: End-to-end smoke + ops runbook

This task has no new production code — it validates the whole pipeline on a tiny slice with the real GDELT API and a real LM Studio model, then documents the full overnight run. **A human (Zach) must have LM Studio running with a model loaded before the smoke steps.**

**Files:**
- Create: `worldcup_prediction_lab/plans/2026-07-03-local-analyst-walkback-runbook.md` (the completed checklist below, with observed numbers filled in)
- Modify: `co-op.md` (log the lane + results)

- [ ] **Step 1: Full test suite green**

Run: `uv run pytest tests/lab/ -v`
Expected: all lab tests PASS (walkback + pre-existing).

- [ ] **Step 2: Build 10 real wells**

Run: `uv run python -m wc_predictor.lab.walkback build-wells --limit 10`
Expected: 10 files in `runs/newswells/`, each printing `kept N docs`. Record the coverage: how many of the 10 have ≥3 clean docs. If fewer than 5, STOP and flag in co-op.md — GDELT coverage is below viability and the well query needs iteration (this is the plan's known highest-risk assumption).

- [ ] **Step 3: Verify LM Studio is up**

Run: `curl -s http://localhost:1234/v1/models`
Expected: JSON listing the loaded model id. Note the exact id — it is the `--model` argument everywhere. If this fails, ask Zach to start LM Studio's local server with an 8–14B instruct model (knowledge cutoff must predate `--cutoff 2025-01-01`; e.g. a Llama-3.1-8B or Qwen2.5-14B instruct quant that fits 12GB).

- [ ] **Step 4: Recall screen on the smoke slice**

Run: `uv run python -m wc_predictor.lab.walkback recall --model <MODEL_ID> --out runs/analyst_walkback/recall_<MODEL_ID>.jsonl`
Expected: prints `contaminated: X/443 (...)`. Record the rate. If >15%, rerun Tasks with `--cutoff 2025-07-01` (n=287) and note it.
(Runtime note: 443 short calls; at ~5s/call ≈ 40 min. Acceptable to run only once per model.)

- [ ] **Step 5: Smoke-run all three conditions on 10 matches**

The runner has no `--limit`; for the smoke, temporarily test with a sliced universe via Python:

Run:
```bash
uv run python -c "
from pathlib import Path
from wc_predictor.lab.walkback.universe import load_universe
from wc_predictor.lab.walkback.cli import run_batch
from wc_predictor.lab.walkback.llm import LMClient
client = LMClient(model='<MODEL_ID>')
uni = load_universe().head(10)
for cond in ('stats', 'news', 'both'):
    print(cond, run_batch(uni, Path('runs/newswells'), client, cond, Path('runs/analyst_walkback/smoke.jsonl')))
"
```
Expected: `done` > 0 for every condition; news/both may skip matches without wells. Spot-read 3 rows of `runs/analyst_walkback/smoke.jsonl` — probabilities sane (not all 1/3, sum to 1).

- [ ] **Step 6: Evaluate the smoke output (mechanics only, numbers meaningless at n=10)**

Run: `uv run python -m wc_predictor.lab.walkback evaluate --preds runs/analyst_walkback/smoke.jsonl --report runs/analyst_walkback/smoke_report.md`
Expected: ladder JSON prints; report file exists. Delete `smoke.jsonl`/`smoke_report.md` afterwards so the real run starts clean.

- [ ] **Step 7: Write the runbook and log the lane**

Create `worldcup_prediction_lab/plans/2026-07-03-local-analyst-walkback-runbook.md` containing the observed smoke numbers (well coverage, contamination rate, seconds/forecast) and the exact overnight sequence:

```bash
# 1. freeze all wells (GDELT-rate-limited, ~1-2h wall clock, run once ever)
uv run python -m wc_predictor.lab.walkback build-wells
# 2. per model: recall screen, then all three conditions (resumable, rerun on crash)
uv run python -m wc_predictor.lab.walkback recall --model <MODEL_ID> --out runs/analyst_walkback/recall_<MODEL_ID>.jsonl
uv run python -m wc_predictor.lab.walkback run --model <MODEL_ID> --condition stats
uv run python -m wc_predictor.lab.walkback run --model <MODEL_ID> --condition news
uv run python -m wc_predictor.lab.walkback run --model <MODEL_ID> --condition both
# 3. evaluate everything recorded so far
uv run python -m wc_predictor.lab.walkback evaluate
```

Add a co-op.md entry (date, lane owner, smoke results, link to runbook). Per repo protocol, update co-op.md **before** starting the overnight run.

- [ ] **Step 8: Commit**

```bash
# run from worldcup_prediction_lab/ (the working directory for all commands in this plan)
git add plans/2026-07-03-local-analyst-walkback-runbook.md ../co-op.md
git commit -m "walkback: e2e smoke validated + overnight runbook"
```

---

## Deliberately out of scope (YAGNI — do not build these in this pass)

- **Wayback Machine enrichment** of wells: only if GDELT coverage proves insufficient at Task 9 Step 2.
- **Claude-API ceiling run** on the same wells: one-command follow-up once the local results exist (`LMClient(base_url=..., model=...)` pointed at any OpenAI-compatible proxy) — decide after seeing local numbers.
- **Live-agent well replay** (the six 2026 WC agent picks): needs a different well source (those fixtures predate nothing — GDELT works — but market964 doesn't contain them); worth a small follow-up task, not this plan.
- **Betting/edge analysis** on LLM deviations: statistically hopeless at this n (see evaluation doc); explicitly not a goal.

## Success criteria (what "done" means scientifically)

1. Frozen, linted wells for ≥60% of the 443-match universe.
2. For at least one local model, all three conditions run end-to-end with ≥250 usable forecasts each.
3. The report answers, with paired CIs: (a) where each lane sits on the climatology→Elo→market ladder; (b) whether `both` beats `stats` (the marginal value of news — the headline question); (c) the fitted temperature and whether temp-scaling closes a meaningful share of the gap.
4. A null result ("news adds nothing; LLM ≈ Elo at best") is a valid, reportable outcome — it empirically grounds the live agent's market-anchor rule.
