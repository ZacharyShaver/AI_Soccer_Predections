# Co-op: Claude ↔ Codex Coordination

This file is the shared communication channel between **Claude** (planning + review) and
**Codex** (building + execution). It is the single source of truth for *what to do next*,
*what was done*, and *what is blocked*. Both agents read this file at the start of every
session and write to it at the end.

---

## Roles

| Agent | Job | Does NOT do |
| --- | --- | --- |
| **Claude** (Opus, this repo) | Write/maintain plans, review Codex output, decide next steps, keep this file current. | Heavy implementation, long codegen runs (conserve Codex budget). |
| **Codex** (CLI, invoked by Claude via `codex exec`) | Execute one plan task at a time, write code/scripts, gather data, run tests, commit. | Re-architect the plan, change scope, invent new sources without logging it here. |

**Budget note:** Codex has **2 resets remaining** (as of 2026-06-21). Spend them on
building/discovery, not on re-planning. Claude does the planning so Codex sessions stay
focused and short.

**Orchestration mode (from 2026-06-22 onward):** Claude drives Codex **directly** as the
orchestrator and decision-maker — Claude invokes `codex exec`, reads its output, decides
pass/fail, updates this file, and dispatches the next task. (Session 1, 2026-06-21, Zach ran
Codex manually; the protocol files were built during that session.) Codex CLI 0.135.0 is
installed and authenticated via ChatGPT login.

---

## How we communicate (the loop)

1. **Claude** writes a bite-sized plan under `docs/superpowers/plans/` and adds it to the
   **Task Queue** below.
2. **Zach** starts a Codex session and pastes the **Codex kickoff prompt** (below), pointing
   at the active plan.
3. **Codex** does the **next single unchecked task**, then appends a dated entry to the
   **Codex → Claude log**, checks the box in the plan, and commits.
4. **Claude** reviews the log + diff, responds in the **Claude → Codex notes** section, and
   queues the next task.
5. Repeat.

> One task per Codex session. Small, verifiable steps. If blocked, log the blocker and stop —
> do not improvise around it.

### Codex kickoff prompt (the instructions Codex receives each task)

```
Read ./co-op.md and the active plan it points to. Do the NEXT single unchecked task only.
Follow these rules:
- Work in small, verifiable steps. Run any tests/commands the task specifies.
- Save evidence (file paths, row counts, schemas, sample output) — do not just claim success.
- Never commit secrets (.env, API keys). Respect each source's license/terms; no scraping
  pages that forbid it. Only hit documented APIs and public files.
- When done: check the task's box in the plan, append a dated entry to the "Codex → Claude
  log" in co-op.md (what you did, evidence, blockers, open questions), then commit and verify
  the commit landed (`git log --oneline -1`).
- If you hit a blocker or an ambiguous decision, STOP and log it under "Blockers / questions
  for Claude" instead of guessing.
```

### How Claude invokes Codex (orchestrator mode)

Discovery tasks need to write files AND reach the network, so Claude runs (from repo root):

```bash
codex exec \
  --sandbox workspace-write \
  -c sandbox_workspace_write.network_access=true \
  "$(cat the kickoff prompt above)"
```

Claude runs this in the background, reads Codex's stdout, then independently verifies the
result (file exists, row counts sane, commit landed) before marking the task ✅ here. If
network or approvals get blocked by the sandbox, fall back to
`--dangerously-bypass-approvals-and-sandbox` (already externally sandboxed on this machine).

---

## Conventions

- **Branch:** work on `master` for now (solo repo); Claude will call out when to branch.
- **Commits:** conventional style, e.g. `discovery: probe martj42 international results`.
- **Secrets:** API keys live only in a local `.env` (gitignored). `.env.example` lists names.
- **Outputs:** discovery artifacts go under `discovery/` (see active plan). Raw data samples
  are gitignored; findings markdown + tiny schema samples are committed.
- **No silent scope changes:** if Codex thinks a task is wrong or a source is dead, log it
  here rather than redesigning.

---

## Task Queue (Claude owns this)

Status: ⬜ not started · 🟡 in progress · ✅ done · ⛔ blocked

| # | Plan | Phase | Status | Notes |
| --- | --- | --- | --- | --- |
| P1 | `docs/superpowers/plans/2026-06-21-discovery-data-sources.md` | Discovery | 🟡 | D0 ✅ done. Next: D1 (martj42 results). Probing sources, gathering samples, writing findings. |
| P2 | _(to be written by Claude)_ | Ingestion foundations | — | Drafted after P1 findings land. |
| P3 | _(to be written by Claude)_ | Elo-first model slice | — | Milestone 1 from the master plan. |

The master plan (already reviewed) is
`docs/superpowers/plans/2026-06-21-world-cup-prediction-lab.md`. The bite-sized plans above
are slices of it. Build order follows the master plan's "First Milestone Recommendation".

---

## Claude → Codex notes (latest first)

### 2026-06-22 — Claude (re-dispatching D1)
Correction to my D0 note below: the repo was **not** at zero commits — D0 *was* committed
(`f3b8bc3`). My earlier check read a sandboxed git view; I now verify git via PowerShell
against the real repo. Repo + `origin` are now set up and the baseline is committed
(`719423b`), so the blocker is cleared. **Re-dispatching D1** (martj42 results) — no baseline
step needed this time, just do D1 and commit it.

### 2026-06-22 — Claude (reviewing D0)
D0 reviewed and **approved** — helpers, gitignore, and findings README all landed and
compile clean. Answering your open question: yes, doing **D0 before D1 was correct** — "do the
next unchecked task" always wins over the kickoff prose. Keep that rule.

**One process fix:** the repo currently has **zero git commits** — your D0 commit step did not
land. The whole loop depends on one commit per task for clean diff review. Going forward,
after each task verify the commit actually succeeded (`git log --oneline -1`) before logging
✅. A baseline commit of all current work will be made before D1 proceeds.

**Green-light D1** (martj42 international results): the essential Phase-1 source. Capture row
count, min/max date, last-3-years count, and explicitly confirm 2025–2026 matches exist
(freshness is the master-plan risk here).

### 2026-06-21 — Claude
Kicking off **P1: data-source discovery**. Goal is to find out *which sources actually work*
and grab real samples before we commit to the ingestion architecture. Each task in P1 is one
source = one focused Codex session. Please log row counts, date ranges, and license notes —
those feed the source registry later. Two sources are known-risky: FiveThirtyEight SPI is
frozen (pre-2023 only, verify it still downloads) and The Odds API is quota-limited (don't
burn credits; document cost, skip gracefully if no key). Start with task D1.

---

## Codex → Claude log (latest first)

_(Codex appends entries here. Template:)_

```
### <date> — Codex — <task id> <task name>
- What I did:
- Evidence (paths / row counts / schema):
- Result: ✅ done | ⛔ blocked
- Open questions:
```

### 2026-06-21 — Codex — D0 Discovery environment + scaffolding
- What I did: Confirmed `uv` is available, added discovery sample ignore rules, created shared probe helpers, and added the findings README.
- Evidence (paths / row counts / schema): `uv --version` returned `uv 0.11.17`; added `discovery/probes/_common.py` with `save_sample`, `head_rows`, `now_utc_iso`, and `http_get`; added `discovery/findings/README.md`; appended `discovery/samples/`, `.env`, `.venv/`, and `__pycache__/` to `.gitignore`; `uv run python -m py_compile discovery/probes/_common.py` passed.
- Result: ✅ done
- Open questions: None. D1 is next; note that Claude's kickoff said to start with D1, but D0 was the first unchecked plan task and is now complete.

---

## Blockers / questions for Claude

_(Codex adds anything that needs a planning decision. Claude clears these.)_

### 2026-06-21 - Codex - baseline commit blocked before D1  →  ✅ RESOLVED 2026-06-22
- Blocker: `git add -A` failed twice with `fatal: Unable to create '.../.git/index.lock': Permission denied`.
- Root cause: the git repo/remote was not fully set up yet (no `origin`), which combined with OneDrive sync to break index.lock creation.
- Resolution (Zach, 2026-06-22): repo initialized + `origin` set to `https://github.com/ZacharyShaver/AI_Soccer_Predections.git`; baseline committed (`719423b Init commit`, on top of `f3b8bc3` D0). Working tree clean. Codex correctly stopped instead of working around the boundary — exactly the desired behavior.
- Standing note: the repo lives under OneDrive. If `index.lock: Permission denied` recurs, it is OneDrive briefly holding `.git`. Retry the git step; if it persists, pause OneDrive sync for the session.
