# Daily Model-Research Leaderboard

Generated: `2026-06-28T14:09:49Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 254
- Registered variants: 18

| Rank | Variant | n | RPS | log loss | Brier | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `competitive_form` | 12 | 0.1063 | 0.7555 | 0.4180 | 0.875 | +0.0448 |
| 2 | `weighted_recent_form` | 12 | 0.1095 | 0.7647 | 0.4251 | 0.875 | +0.0415 |
| 3 | `form_trend` | 12 | 0.1110 | 0.7682 | 0.4251 | 0.875 | +0.0401 |
| 4 | `ewma_goal_form` | 6 | 0.1120 | 0.7598 | 0.4274 | 0.750 | +0.0391 |
| 5 | `defensive_form` | 6 | 0.1125 | 0.7601 | 0.4276 | 0.750 | +0.0386 |
| 6 | `ensemble_top_k` | 6 | 0.1133 | 0.7622 | 0.4284 | 0.750 | +0.0378 |
| 7 | `opp_adj_recent_form` | 6 | 0.1138 | 0.7580 | 0.4277 | 0.750 | +0.0373 |
| 8 | `draw_guard` | 6 | 0.1210 | 0.7637 | 0.4295 | 0.750 | +0.0300 |
| 9 | `group_incentive` | 6 | 0.1242 | 0.7439 | 0.4163 | 0.750 | +0.0269 |
| 10 | `opp_adj_form` | 18 | 0.1419 | 0.8617 | 0.4983 | 0.750 | +0.0092 |
| 11 | `attack_defense_form` | 18 | 0.1423 | 0.8639 | 0.4997 | 0.750 | +0.0087 |
| 12 | `match_congestion` | 18 | 0.1458 | 0.8764 | 0.5060 | 0.750 | +0.0053 |
| 13 | `scoring_form` | 32 | 0.1474 | 0.7954 | 0.4535 | 0.800 | +0.0037 |
| 14 | `recent_form` | 32 | 0.1483 | 0.7975 | 0.4551 | 0.800 | +0.0028 |
| 15 | `elo_baseline` (baseline) | 32 | 0.1510 | 0.8084 | 0.4611 | 0.800 | +0.0000 |
| 16 | `rest_days` | 32 | 0.1510 | 0.8084 | 0.4611 | 0.800 | +0.0000 |
| 17 | `elo_calibrated` | 0 | n/a | n/a | n/a | n/a | n/a |
| 18 | `elo_recalibrated` | 0 | n/a | n/a | n/a | n/a | n/a |

## Variants

- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
