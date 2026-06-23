# Model-Research Log

Daily Claude-orchestrates-Codex bake-off. Each challenger must beat `elo_baseline`
(walk-forward RPS 0.1776). See `DAILY_PLAYBOOK.md` for the procedure and
`LEADERBOARD.md` for standings.

---

## Day 1 — 2026-06-22 (Monday)

**Resolved since yesterday:** none yet — this is the seed day. No variant predictions
have been scored.

**Variants in play (3 challengers + baseline), built by Codex in git worktrees
`exp/2026-06-22/<id>`:**
- `elo_baseline` — control: host-aware Elo, K=20.
- `rest_days` — Elo + rest/fatigue: Elo delta of 3 pts/day of rest difference (cap ±30),
  rest capped at 14 days. *Hypothesis:* fresher teams over-perform Elo.
- `recent_form` — Elo + last-5 results momentum: delta 60·(form_home − form_away),
  form = mean(win=1/draw=0.5/loss=0). *Hypothesis:* short-window momentum adds signal
  Elo's slow updates miss.
- `scoring_form` — Elo + last-5 goal-difference: delta 15·(gd_home − gd_away) (cap ±45).
  *Hypothesis:* recent scoring margin predicts beyond Elo's smoothed rating.

**Seeded predictions:** as_of `2026-06-21` (32 upcoming fixtures incl. today's 4 games)
and as_of `2026-06-22` (32 fixtures, 2026-06-23+), all 4 variants, in
`runs/experiments/`.

**Early observation:** during synchronized group play `rest_days` ≈ baseline (both teams
share a match cadence, so rest differences are tiny). It should matter more across the
knockout/rest-gap boundary. `recent_form` and `scoring_form` nudge probabilities a point
or two toward in-form sides (e.g. Norway vs Senegal: baseline 38.0/26.4/35.6 →
scoring_form 39.5/25.9/34.6).

**Next (Tue 2026-06-23, autonomous cron):** score the 2026-06-22 results that landed,
update the leaderboard, retire/keep, and build 3 new feature variants.
