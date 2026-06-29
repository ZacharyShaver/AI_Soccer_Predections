# Daily Model-Research Leaderboard

Generated: `2026-06-29T13:02:53Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 272
- Registered variants: 20

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `elo_recalibrated` | 1 | 0.0951 | 0.5233 | 0.2536 | 1.000 | 1.000 | +0.0549 |
| 2 | `competitive_form` | 13 | 0.1056 | 0.7355 | 0.4034 | 0.615 | 0.889 | +0.0445 |
| 3 | `form_trend` | 13 | 0.1107 | 0.7497 | 0.4118 | 0.615 | 0.889 | +0.0393 |
| 4 | `weighted_recent_form` | 13 | 0.1107 | 0.7505 | 0.4148 | 0.615 | 0.889 | +0.0393 |
| 5 | `ewma_goal_form` | 7 | 0.1108 | 0.7248 | 0.4011 | 0.571 | 0.800 | +0.0393 |
| 6 | `ensemble_top_k` | 7 | 0.1120 | 0.7273 | 0.4022 | 0.571 | 0.800 | +0.0380 |
| 7 | `elo_calibrated` | 1 | 0.1138 | 0.5830 | 0.2962 | 1.000 | 1.000 | +0.0363 |
| 8 | `defensive_form` | 7 | 0.1138 | 0.7328 | 0.4069 | 0.571 | 0.800 | +0.0363 |
| 9 | `opp_adj_recent_form` | 7 | 0.1146 | 0.7301 | 0.4063 | 0.571 | 0.800 | +0.0355 |
| 10 | `draw_guard` | 7 | 0.1228 | 0.7455 | 0.4157 | 0.571 | 0.800 | +0.0273 |
| 11 | `group_incentive` | 7 | 0.1233 | 0.7174 | 0.3961 | 0.857 | 0.800 | +0.0268 |
| 12 | `opp_adj_form` | 19 | 0.1398 | 0.8433 | 0.4847 | 0.526 | 0.769 | +0.0103 |
| 13 | `attack_defense_form` | 19 | 0.1401 | 0.8451 | 0.4858 | 0.526 | 0.769 | +0.0099 |
| 14 | `match_congestion` | 19 | 0.1443 | 0.8597 | 0.4938 | 0.526 | 0.769 | +0.0057 |
| 15 | `scoring_form` | 33 | 0.1460 | 0.7866 | 0.4469 | 0.636 | 0.808 | +0.0041 |
| 16 | `recent_form` | 33 | 0.1473 | 0.7902 | 0.4496 | 0.636 | 0.808 | +0.0027 |
| 17 | `elo_baseline` (baseline) | 33 | 0.1500 | 0.8008 | 0.4554 | 0.636 | 0.808 | +0.0000 |
| 18 | `rest_days` | 33 | 0.1500 | 0.8008 | 0.4554 | 0.636 | 0.808 | +0.0000 |
| 19 | `accuracy_pick_tuned` | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| 20 | `ml_elo_correction` | 0 | n/a | n/a | n/a | n/a | n/a | n/a |

## Variants

- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
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
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
