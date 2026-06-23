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

---

## Day 2 — 2026-06-23 (Tuesday)

**Resolved:** all 4 of the 2026-06-22 fixtures. The model went **4/4 on outcome**:
- France 3–0 Iraq (HOME; we had 79% home)
- Argentina 2–0 Austria (HOME; 73%)
- Jordan 1–2 Algeria (AWAY; 56% away)
- Norway 3–2 Senegal (HOME; 38/26/36 — our coin-flip landed)

**Leaderboard (n=4 each):**
| variant | RPS | edge vs baseline |
| --- | ---: | ---: |
| `scoring_form` | 0.0968 | +0.0154 |
| `recent_form` | 0.1021 | +0.0101 |
| `elo_baseline` | 0.1122 | — |
| `rest_days` | 0.1122 | +0.0000 |

Both form challengers beat the baseline by leaning harder into the (correct) favorites
(e.g. scoring_form gave Algeria 63% vs baseline 56%). `rest_days` exactly tied the baseline —
rest is equal in synchronized group play, as predicted Day 1; expect it to matter only across
the group→knockout rest gap. **Caveat: n=4 — far too small to separate models; treat as a
direction, not a verdict.**

**Infra fixes committed by the autonomous run:** results refresh through 2026-06-22
(`a08f1e9`) and the fixture↔result crosswalk (`992a7bf`) — variant predictions key on
openfootball `fixture_id` but results land under martj42 `match_id`; the crosswalk matches on
(team-pair, date) and re-orients the score, which is what makes scoring work at all.

**Bug found:** the headless `claude -p` run dispatched the 3 new Tuesday variants to Codex in
the *background*, then went idle and exited, orphaning the builds — so **no new variants were
added today** (still 4). Fix applied to `CRON_PROMPT.md`: run Codex builds in the FOREGROUND
(blocking), never `run_in_background`, so the headless session stays alive until each file is
authored. Should self-correct on the Wed 2026-06-24 run.
