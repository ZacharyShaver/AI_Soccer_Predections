# Daily Model-Research Leaderboard

Generated: `2026-07-11T11:05:39Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 611
- Registered variants: 26

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `competitive_form` | 27 | 0.1359 | 0.7886 | 0.4444 | 0.630 | 0.850 | +0.0192 |
| 2 | `weighted_recent_form` | 27 | 0.1391 | 0.7980 | 0.4516 | 0.630 | 0.850 | +0.0159 |
| 3 | `form_trend` | 27 | 0.1419 | 0.8069 | 0.4560 | 0.630 | 0.850 | +0.0131 |
| 4 | `ewma_goal_form` | 21 | 0.1474 | 0.8031 | 0.4574 | 0.619 | 0.812 | +0.0077 |
| 5 | `opp_adj_recent_form` | 21 | 0.1478 | 0.8031 | 0.4579 | 0.619 | 0.812 | +0.0072 |
| 6 | `ensemble_top_k` | 21 | 0.1482 | 0.8059 | 0.4589 | 0.619 | 0.812 | +0.0068 |
| 7 | `opp_adj_form` | 33 | 0.1496 | 0.8396 | 0.4826 | 0.576 | 0.792 | +0.0055 |
| 8 | `attack_defense_form` | 33 | 0.1497 | 0.8402 | 0.4831 | 0.576 | 0.792 | +0.0053 |
| 9 | `defensive_form` | 21 | 0.1507 | 0.8147 | 0.4655 | 0.619 | 0.812 | +0.0043 |
| 10 | `scoring_form` | 47 | 0.1510 | 0.8006 | 0.4566 | 0.638 | 0.811 | +0.0041 |
| 11 | `group_incentive` | 21 | 0.1523 | 0.8058 | 0.4591 | 0.714 | 0.812 | +0.0027 |
| 12 | `recent_form` | 47 | 0.1525 | 0.8049 | 0.4598 | 0.638 | 0.811 | +0.0026 |
| 13 | `draw_guard` | 21 | 0.1543 | 0.8240 | 0.4716 | 0.619 | 0.812 | +0.0008 |
| 14 | `match_congestion` | 33 | 0.1549 | 0.8578 | 0.4939 | 0.576 | 0.792 | +0.0002 |
| 15 | `elo_baseline` (baseline) | 47 | 0.1550 | 0.8155 | 0.4659 | 0.638 | 0.811 | +0.0000 |
| 16 | `rest_days` | 47 | 0.1552 | 0.8158 | 0.4661 | 0.638 | 0.811 | -0.0002 |
| 17 | `elo_calibrated` | 15 | 0.1559 | 0.8103 | 0.4648 | 0.667 | 0.833 | -0.0008 |
| 18 | `elo_recalibrated` | 15 | 0.1582 | 0.8165 | 0.4687 | 0.667 | 0.833 | -0.0031 |
| 19 | `accuracy_pick_tuned` | 14 | 0.1666 | 0.8456 | 0.4890 | 0.643 | 0.818 | -0.0115 |
| 20 | `ml_elo_correction` | 12 | 0.1679 | 0.8202 | 0.4715 | 0.667 | 0.800 | -0.0129 |
| 21 | `tournament_form` | 12 | 0.1735 | 0.8267 | 0.4770 | 0.667 | 0.800 | -0.0184 |
| 22 | `dixon_coles_tuned` | 11 | 0.1748 | 0.8351 | 0.4848 | 0.727 | 0.889 | -0.0198 |
| 23 | `squad_value` | 9 | 0.1755 | 0.8755 | 0.5132 | 0.556 | 0.714 | -0.0205 |
| 24 | `dixon_coles_poisson` | 11 | 0.1786 | 0.8421 | 0.4901 | 0.727 | 0.778 | -0.0236 |
| 25 | `dc_squad_fusion` | 9 | 0.1843 | 0.8860 | 0.5238 | 0.556 | 0.714 | -0.0292 |
| 26 | `dc_elo_fusion` | 9 | 0.1848 | 0.8877 | 0.5249 | 0.556 | 0.714 | -0.0298 |

## Variants

- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.
- `tournament_form` — Elo adjusted for over/under-performance vs expectation in this World Cup.  
  feature: Mean residual (actual result - Elo win-expectation) over each team's 2026 WC matches; hot teams get a small Elo bump, cold teams a small dock. Opponent-adjusted.
- `dixon_coles_tuned` — Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history.  
  feature: Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge.
- `squad_value` — Recalibrated Elo + Transfermarkt squad-value differential (first non-scoreline signal).  
  feature: Bounded Elo delta from the log ratio of the two sides' Transfermarkt squad values (top-15 citizen market values, monthly, strictly pre-match).
- `dixon_coles_poisson` — Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived).  
  feature: Team attack/defense ratings in log-goal-rate space, online Poisson-regression gradient updates, Dixon-Coles low-score tau correction, host-aware home edge.
- `dc_squad_fusion` — dc_elo_fusion with the squad_value Elo leg — Dixon-Coles pooled with squad-value-aware Elo (current history champion).  
  feature: Swap dc_elo_fusion's plain recalibrated-Elo leg for squad_value so the pool inherits the Transfermarkt squad-value signal the goal-based Dixon-Coles leg cannot see.
- `dc_elo_fusion` — Log opinion pool of dixon_coles_tuned (w=0.7) and elo_recalibrated — first fusion to beat its best constituent.  
  feature: Weighted geometric mean of the H/D/A probabilities from the two best, genuinely decorrelated model classes (goal-based Dixon-Coles + outcome-based recalibrated Elo); scoreline shape delegated to the Dixon-Coles component.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
