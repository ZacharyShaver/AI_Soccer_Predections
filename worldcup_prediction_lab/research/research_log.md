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

---

## Day 3 — 2026-06-24 (Wednesday, UTC)

**Date note:** the wrapper's local clock read 2026-06-23 (Tue evening), but UTC had rolled to
2026-06-24, so `run_daily_update` keyed the ledger to `date=2026-06-24`. Per the playbook
(`as_of` = UTC date) this run uses **as_of `2026-06-24`** for branches, predictions, and this entry.

**Resolved since yesterday:** none new. Day 2 scored the four 2026-06-22 fixtures; the 2026-06-23
group games have not yet landed in martj42 (training cutoff still 2026-06-22), so the leaderboard
is unchanged (n=4 per variant). Standings carried over:
| variant | RPS | edge vs baseline |
| --- | ---: | ---: |
| `scoring_form` | 0.0968 | +0.0154 |
| `recent_form` | 0.1021 | +0.0101 |
| `elo_baseline` | 0.1122 | — |
| `rest_days` | 0.1122 | +0.0000 |

**Cleanup:** Tuesday's orphaned worktrees/branches (`exp/2026-06-23/{competitive_form,
opponent_adjusted_form,weighted_goal_form}`) were empty (the background-dispatch bug authored
nothing) — removed them and started today fresh with foreground Codex builds.

**Decisions:** the two recent-form challengers (last-5 goal-diff, last-5 results) are the only
signals beating the bar so far, both by leaning harder into correct favorites. `rest_days` ties
the baseline (group-play rest is uniform, as predicted) — **retiring** it as a new descendant
and rebuilding the fatigue idea as cumulative *match congestion*. **Carrying forward** the
winner (`scoring_form`) with an opponent-adjusted twist.

**Today's 3 challengers (built by Codex in `exp/2026-06-24/<id>` worktrees):**
- `opp_adj_form` — *carry-forward winner.* Opponent-adjusted last-5 goal difference: each game's
  GD is weighted by opponent strength `(opp_pre_match_elo − 1500)/100` before averaging, then the
  home−away difference becomes the Elo delta. *Hypothesis:* a +3 GD vs a weak side should count
  less than +1 vs a strong side — opponent-adjusting `scoring_form`'s winning signal sharpens it.
- `attack_defense_form` — *opponent-adjusted attack vs defense.* Track each team's last-5 goals
  scored and conceded; delta from expected goal supremacy `(home_attack − away_defense) −
  (away_attack − home_defense)`. *Hypothesis:* net GD hides matchup structure; a strong attack
  facing a leaky defense should be favored beyond what smoothed Elo captures.
- `match_congestion` — *fatigue, done right.* Count each team's matches in the trailing 15 days;
  more recent load = small negative Elo (fewer matches favors that side). *Hypothesis:* unlike
  `rest_days` (gap since last match, uniform in group play), cumulative congestion should bite as
  the group→knockout rest gap opens up.

Each must beat `elo_baseline` (the bar). Predictions immutable; no sub-200 recalibration.

---

## Day 4 — 2026-06-25 (Thursday, UTC)

**Resolved since yesterday:** the 2026-06-23 group fixtures landed in martj42 (training
cutoff now 2026-06-24), so all four Day-1 variants jumped from n=4 to **n=14**. The three
Day-3 variants (`opp_adj_form`, `attack_defense_form`, `match_congestion`) recorded their
first predictions on 06-24 for fixtures not yet resolved, so they remain **n=0**.

**Leaderboard (n=14 for Day-1 variants):**
| variant | n | RPS | edge vs baseline |
| --- | ---: | ---: | ---: |
| `recent_form` | 14 | 0.1537 | +0.0041 |
| `scoring_form` | 14 | 0.1539 | +0.0040 |
| `elo_baseline` | 14 | 0.1578 | — |
| `rest_days` | 14 | 0.1578 | +0.0000 |
| `attack_defense_form` | 0 | n/a | n/a |
| `match_congestion` | 0 | n/a | n/a |
| `opp_adj_form` | 0 | n/a | n/a |

**What changed:** with the larger sample the two form challengers stay ahead of the bar but
their edge **shrank** (scoring_form +0.0154 → +0.0040; recent_form +0.0101 → +0.0041) and the
order flipped — last-5 *results* (`recent_form`) now narrowly leads last-5 *goal difference*
(`scoring_form`). The Day-2 gap was a small-sample artifact (n=4), exactly as flagged. Both
form signals are real but modest. `rest_days` again **exactly ties** the baseline (n=14):
group-play rest is uniform — confirmed no-value, **retired** as a build target (the fatigue
idea already lives on as `match_congestion`, awaiting resolution).

**Decisions:** **carry forward** the new leader (`recent_form`, last-5 results) with a recency
weighting twist; **retire** `rest_days`; **invent** two new feature hypotheses from data we
have (the `tournament` column enables match-importance weighting; trajectory is untested).

**Today's 3 challengers (built by Codex in `exp/2026-06-25/<id>` worktrees):**
- `weighted_recent_form` — *carry-forward winner.* Recency-weighted last-5 results: within the
  5-match window, weight the most recent game highest (linear 5..1) before averaging, then
  home−away → Elo delta. *Hypothesis:* a win last week predicts more than a win five games ago;
  weighting recent_form's winning window by recency sharpens the signal.
- `competitive_form` — *qualifier-vs-friendly weighting (new).* Last-5 goal-difference form, but
  each match weighted by importance from the `tournament` field — World Cup / continental / Nations
  League / qualifiers full weight, friendlies down-weighted (~0.4). *Hypothesis:* friendlies use
  experimental lineups and are noisy; a competition-weighted form is a cleaner predictor than the
  flat recent/scoring form.
- `form_trend` — *directional momentum (new).* The slope of last-5 goal difference, not its level:
  (mean of the 2 most recent GDs) − (mean of the earlier 3), home−away → Elo delta. *Hypothesis:*
  trajectory predicts beyond level — a team peaking right now beats one with the same average form
  that is declining.

Each must beat `elo_baseline` (the bar). Predictions immutable; no sub-200 recalibration.
