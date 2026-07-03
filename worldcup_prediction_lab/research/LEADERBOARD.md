# Daily Model-Research Leaderboard

Generated: `2026-07-03T11:18:41Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 377
- Registered variants: 26

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `dixon_coles_tuned` | 2 | 0.1086 | 0.5531 | 0.2723 | 1.000 | 1.000 | +0.0405 |
| 2 | `competitive_form` | 18 | 0.1136 | 0.7404 | 0.4070 | 0.667 | 0.923 | +0.0354 |
| 3 | `dixon_coles_poisson` | 2 | 0.1161 | 0.5855 | 0.2967 | 1.000 | 1.000 | +0.0329 |
| 4 | `weighted_recent_form` | 18 | 0.1193 | 0.7563 | 0.4191 | 0.667 | 0.923 | +0.0298 |
| 5 | `form_trend` | 18 | 0.1218 | 0.7651 | 0.4241 | 0.667 | 0.923 | +0.0273 |
| 6 | `ewma_goal_form` | 12 | 0.1224 | 0.7413 | 0.4110 | 0.667 | 0.889 | +0.0267 |
| 7 | `ensemble_top_k` | 12 | 0.1240 | 0.7463 | 0.4143 | 0.667 | 0.889 | +0.0251 |
| 8 | `accuracy_pick_tuned` | 5 | 0.1248 | 0.7197 | 0.3981 | 0.800 | 1.000 | +0.0243 |
| 9 | `opp_adj_recent_form` | 12 | 0.1249 | 0.7446 | 0.4141 | 0.667 | 0.889 | +0.0242 |
| 10 | `defensive_form` | 12 | 0.1263 | 0.7511 | 0.4184 | 0.667 | 0.889 | +0.0228 |
| 11 | `ml_elo_correction` | 3 | 0.1287 | 0.6113 | 0.3186 | 1.000 | 1.000 | +0.0204 |
| 12 | `elo_recalibrated` | 6 | 0.1296 | 0.7203 | 0.3972 | 0.833 | 1.000 | +0.0195 |
| 13 | `group_incentive` | 12 | 0.1314 | 0.7422 | 0.4117 | 0.833 | 0.889 | +0.0177 |
| 14 | `elo_calibrated` | 6 | 0.1318 | 0.7251 | 0.4015 | 0.833 | 1.000 | +0.0173 |
| 15 | `draw_guard` | 12 | 0.1339 | 0.7669 | 0.4310 | 0.667 | 0.889 | +0.0152 |
| 16 | `opp_adj_form` | 24 | 0.1385 | 0.8239 | 0.4700 | 0.583 | 0.824 | +0.0106 |
| 17 | `attack_defense_form` | 24 | 0.1388 | 0.8249 | 0.4706 | 0.583 | 0.824 | +0.0103 |
| 18 | `tournament_form` | 3 | 0.1411 | 0.6180 | 0.3260 | 1.000 | 1.000 | +0.0080 |
| 19 | `match_congestion` | 24 | 0.1439 | 0.8418 | 0.4809 | 0.583 | 0.824 | +0.0052 |
| 20 | `scoring_form` | 38 | 0.1443 | 0.7816 | 0.4424 | 0.658 | 0.833 | +0.0047 |
| 21 | `recent_form` | 38 | 0.1463 | 0.7869 | 0.4464 | 0.658 | 0.833 | +0.0028 |
| 22 | `rest_days` | 38 | 0.1490 | 0.7974 | 0.4524 | 0.658 | 0.833 | +0.0000 |
| 23 | `elo_baseline` (baseline) | 38 | 0.1491 | 0.7977 | 0.4526 | 0.658 | 0.833 | +0.0000 |
| 24 | `dc_elo_fusion` | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| 25 | `dc_squad_fusion` | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| 26 | `squad_value` | 0 | n/a | n/a | n/a | n/a | n/a | n/a |

## Variants

- `dixon_coles_tuned` — Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history.  
  feature: Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge.
- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `dixon_coles_poisson` — Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived).  
  feature: Team attack/defense ratings in log-goal-rate space, online Poisson-regression gradient updates, Dixon-Coles low-score tau correction, host-aware home edge.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `tournament_form` — Elo adjusted for over/under-performance vs expectation in this World Cup.  
  feature: Mean residual (actual result - Elo win-expectation) over each team's 2026 WC matches; hot teams get a small Elo bump, cold teams a small dock. Opponent-adjusted.
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
- `dc_elo_fusion` — Log opinion pool of dixon_coles_tuned (w=0.7) and elo_recalibrated — first fusion to beat its best constituent.  
  feature: Weighted geometric mean of the H/D/A probabilities from the two best, genuinely decorrelated model classes (goal-based Dixon-Coles + outcome-based recalibrated Elo); scoreline shape delegated to the Dixon-Coles component.
- `dc_squad_fusion` — dc_elo_fusion with the squad_value Elo leg — Dixon-Coles pooled with squad-value-aware Elo (current history champion).  
  feature: Swap dc_elo_fusion's plain recalibrated-Elo leg for squad_value so the pool inherits the Transfermarkt squad-value signal the goal-based Dixon-Coles leg cannot see.
- `squad_value` — Recalibrated Elo + Transfermarkt squad-value differential (first non-scoreline signal).  
  feature: Bounded Elo delta from the log ratio of the two sides' Transfermarkt squad values (top-15 citizen market values, monthly, strictly pre-match).

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
