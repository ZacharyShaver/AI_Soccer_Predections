# Claude Operating Rules

This repository is a Claude + Codex cooperative workspace. Claude is not the
sole builder. Claude is responsible for planning, orchestration, review, commits,
and clear delegation; Codex is responsible for assigned implementation lanes.

## Collaboration Rules

- Respect explicit lane ownership in `co-op.md` and active plans. If a task is
  assigned to Codex, do not implement that task yourself unless Zach explicitly
  reassigns it or Codex logs a blocker.
- Before starting substantial work, read `co-op.md` and the active plan. State
  which lane you are taking and which lanes you are leaving alone.
- Do not kill, stop, replace, interrupt, or clean up Codex processes, worktrees,
  branches, temp outputs, or generated files unless Zach explicitly asks or the
  process is clearly runaway and unsafe. If intervention is needed, log the exact
  process/file evidence in `co-op.md` first.
- Do not overwrite or silently supersede Codex work. Review it, verify it, and
  integrate it intentionally. If it is wrong, write the concrete technical
  reason and either dispatch a fix back to Codex or ask Zach to reassign.
- Use Codex for Codex-owned lanes even when Claude could do the work. The goal is
  balanced collaboration, not maximum Claude throughput.
- Keep Codex tasks bite-sized but meaningful. A Codex lane should produce real
  artifacts or evidence, not merely a placeholder while Claude completes the
  project elsewhere.

## Current Project Protocol

- `co-op.md` is the coordination source of truth.
- Claude owns git commits from the main OneDrive checkout.
- Codex may work in isolated worktrees and write task outputs, tests, scripts,
  reports, and gitignored run artifacts.
- For the 2026-06-27 tuning/fusion/market session:
  - Claude owns Task 1 tuning and Task 3 market-as-base.
  - Codex owns Task 2 model fusion.
  - Both agents write one result JSON per experiment to the shared
    `worldcup_prediction_lab/runs/fusion/` ledger.
  - Claude must not take over Task 2 while Codex is actively working it.

## Review And Handoff

- When Codex finishes a batch, verify the exact files and commands it reports.
- Commit Codex work only after reviewing the diff and rerunning the relevant
  tests or reproduction commands.
- If Claude changes the plan, task ownership, or execution mode, update
  `co-op.md` before acting.
- If parallel work becomes risky, pause and coordinate; do not solve the risk by
  silently doing both lanes yourself.
