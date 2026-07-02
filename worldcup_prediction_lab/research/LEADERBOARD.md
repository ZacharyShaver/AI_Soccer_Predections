# Daily Model-Research Leaderboard

Generated: `2026-07-02T14:41:34Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 331
- Registered variants: 23

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `competitive_form` | 16 | 0.1164 | 0.7751 | 0.4309 | 0.625 | 0.909 | +0.0349 |
| 2 | `weighted_recent_form` | 16 | 0.1210 | 0.7879 | 0.4407 | 0.625 | 0.909 | +0.0304 |
| 3 | `form_trend` | 16 | 0.1241 | 0.7990 | 0.4469 | 0.625 | 0.909 | +0.0273 |
| 4 | `ewma_goal_form` | 10 | 0.1280 | 0.7954 | 0.4489 | 0.600 | 0.857 | +0.0233 |
| 5 | `ensemble_top_k` | 10 | 0.1295 | 0.8002 | 0.4518 | 0.600 | 0.857 | +0.0219 |
| 6 | `opp_adj_recent_form` | 10 | 0.1297 | 0.7952 | 0.4498 | 0.600 | 0.857 | +0.0216 |
| 7 | `defensive_form` | 10 | 0.1326 | 0.8069 | 0.4577 | 0.600 | 0.857 | +0.0187 |
| 8 | `group_incentive` | 10 | 0.1360 | 0.7874 | 0.4434 | 0.800 | 0.857 | +0.0154 |
| 9 | `draw_guard` | 10 | 0.1362 | 0.8017 | 0.4558 | 0.600 | 0.857 | +0.0151 |
| 10 | `elo_recalibrated` | 4 | 0.1383 | 0.7955 | 0.4501 | 0.750 | 1.000 | +0.0131 |
| 11 | `elo_calibrated` | 4 | 0.1416 | 0.8058 | 0.4573 | 0.750 | 1.000 | +0.0098 |
| 12 | `opp_adj_form` | 22 | 0.1427 | 0.8564 | 0.4929 | 0.545 | 0.800 | +0.0086 |
| 13 | `attack_defense_form` | 22 | 0.1430 | 0.8575 | 0.4936 | 0.545 | 0.800 | +0.0083 |
| 14 | `match_congestion` | 22 | 0.1471 | 0.8714 | 0.5015 | 0.545 | 0.800 | +0.0042 |
| 15 | `scoring_form` | 36 | 0.1472 | 0.7991 | 0.4549 | 0.639 | 0.821 | +0.0041 |
| 16 | `recent_form` | 36 | 0.1488 | 0.8033 | 0.4581 | 0.639 | 0.821 | +0.0025 |
| 17 | `rest_days` | 36 | 0.1513 | 0.8131 | 0.4635 | 0.639 | 0.821 | +0.0000 |
| 18 | `elo_baseline` (baseline) | 36 | 0.1513 | 0.8133 | 0.4636 | 0.639 | 0.821 | +0.0000 |
| 19 | `accuracy_pick_tuned` | 3 | 0.1522 | 0.8887 | 0.5166 | 0.667 | 1.000 | -0.0009 |
| 20 | `ml_elo_correction` | 1 | 0.1749 | 0.7569 | 0.4228 | 1.000 | 1.000 | -0.0236 |
| 21 | `tournament_form` | 1 | 0.1927 | 0.7783 | 0.4411 | 1.000 | 1.000 | -0.0414 |
| 22 | `dixon_coles_poisson` | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| 23 | `dixon_coles_tuned` | 0 | n/a | n/a | n/a | n/a | n/a | n/a |

## Variants

- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
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
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.
- `tournament_form` — Elo adjusted for over/under-performance vs expectation in this World Cup.  
  feature: Mean residual (actual result - Elo win-expectation) over each team's 2026 WC matches; hot teams get a small Elo bump, cold teams a small dock. Opponent-adjusted.
- `dixon_coles_poisson` — Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived).  
  feature: Team attack/defense ratings in log-goal-rate space, online Poisson-regression gradient updates, Dixon-Coles low-score tau correction, host-aware home edge.
- `dixon_coles_tuned` — Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history.  
  feature: Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
