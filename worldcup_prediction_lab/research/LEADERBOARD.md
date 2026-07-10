# Daily Model-Research Leaderboard

Generated: `2026-07-10T11:15:20Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 585
- Registered variants: 26

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `competitive_form` | 26 | 0.1369 | 0.7985 | 0.4516 | 0.615 | 0.842 | +0.0188 |
| 2 | `weighted_recent_form` | 26 | 0.1400 | 0.8074 | 0.4585 | 0.615 | 0.842 | +0.0157 |
| 3 | `form_trend` | 26 | 0.1420 | 0.8141 | 0.4612 | 0.615 | 0.842 | +0.0137 |
| 4 | `ewma_goal_form` | 20 | 0.1487 | 0.8151 | 0.4663 | 0.600 | 0.800 | +0.0070 |
| 5 | `ensemble_top_k` | 20 | 0.1495 | 0.8177 | 0.4675 | 0.600 | 0.800 | +0.0062 |
| 6 | `opp_adj_recent_form` | 20 | 0.1495 | 0.8158 | 0.4674 | 0.600 | 0.800 | +0.0062 |
| 7 | `opp_adj_form` | 32 | 0.1508 | 0.8492 | 0.4897 | 0.562 | 0.783 | +0.0049 |
| 8 | `attack_defense_form` | 32 | 0.1510 | 0.8498 | 0.4901 | 0.562 | 0.783 | +0.0047 |
| 9 | `scoring_form` | 46 | 0.1519 | 0.8064 | 0.4609 | 0.630 | 0.806 | +0.0038 |
| 10 | `defensive_form` | 20 | 0.1524 | 0.8275 | 0.4750 | 0.600 | 0.800 | +0.0033 |
| 11 | `recent_form` | 46 | 0.1533 | 0.8104 | 0.4639 | 0.630 | 0.806 | +0.0024 |
| 12 | `group_incentive` | 20 | 0.1537 | 0.8171 | 0.4675 | 0.700 | 0.800 | +0.0020 |
| 13 | `draw_guard` | 20 | 0.1550 | 0.8322 | 0.4777 | 0.600 | 0.800 | +0.0007 |
| 14 | `elo_baseline` (baseline) | 46 | 0.1557 | 0.8206 | 0.4697 | 0.630 | 0.806 | +0.0000 |
| 15 | `match_congestion` | 32 | 0.1558 | 0.8664 | 0.5003 | 0.562 | 0.783 | -0.0001 |
| 16 | `rest_days` | 46 | 0.1559 | 0.8209 | 0.4699 | 0.630 | 0.806 | -0.0002 |
| 17 | `elo_calibrated` | 14 | 0.1576 | 0.8227 | 0.4740 | 0.643 | 0.818 | -0.0019 |
| 18 | `elo_recalibrated` | 14 | 0.1596 | 0.8280 | 0.4771 | 0.643 | 0.818 | -0.0040 |
| 19 | `dixon_coles_poisson` | 10 | 0.1708 | 0.8244 | 0.4778 | 0.700 | 0.750 | -0.0151 |
| 20 | `accuracy_pick_tuned` | 13 | 0.1713 | 0.8683 | 0.5058 | 0.615 | 0.800 | -0.0157 |
| 21 | `ml_elo_correction` | 11 | 0.1715 | 0.8386 | 0.4853 | 0.636 | 0.778 | -0.0158 |
| 22 | `dixon_coles_tuned` | 10 | 0.1729 | 0.8354 | 0.4854 | 0.700 | 0.875 | -0.0172 |
| 23 | `tournament_form` | 11 | 0.1781 | 0.8499 | 0.4944 | 0.636 | 0.778 | -0.0225 |
| 24 | `squad_value` | 8 | 0.1807 | 0.9041 | 0.5345 | 0.500 | 0.667 | -0.0250 |
| 25 | `dc_squad_fusion` | 8 | 0.1854 | 0.9002 | 0.5349 | 0.500 | 0.667 | -0.0297 |
| 26 | `dc_elo_fusion` | 8 | 0.1859 | 0.9017 | 0.5358 | 0.500 | 0.667 | -0.0302 |

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
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `dixon_coles_poisson` — Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived).  
  feature: Team attack/defense ratings in log-goal-rate space, online Poisson-regression gradient updates, Dixon-Coles low-score tau correction, host-aware home edge.
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.
- `dixon_coles_tuned` — Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history.  
  feature: Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge.
- `tournament_form` — Elo adjusted for over/under-performance vs expectation in this World Cup.  
  feature: Mean residual (actual result - Elo win-expectation) over each team's 2026 WC matches; hot teams get a small Elo bump, cold teams a small dock. Opponent-adjusted.
- `squad_value` — Recalibrated Elo + Transfermarkt squad-value differential (first non-scoreline signal).  
  feature: Bounded Elo delta from the log ratio of the two sides' Transfermarkt squad values (top-15 citizen market values, monthly, strictly pre-match).
- `dc_squad_fusion` — dc_elo_fusion with the squad_value Elo leg — Dixon-Coles pooled with squad-value-aware Elo (current history champion).  
  feature: Swap dc_elo_fusion's plain recalibrated-Elo leg for squad_value so the pool inherits the Transfermarkt squad-value signal the goal-based Dixon-Coles leg cannot see.
- `dc_elo_fusion` — Log opinion pool of dixon_coles_tuned (w=0.7) and elo_recalibrated — first fusion to beat its best constituent.  
  feature: Weighted geometric mean of the H/D/A probabilities from the two best, genuinely decorrelated model classes (goal-based Dixon-Coles + outcome-based recalibrated Elo); scoreline shape delegated to the Dixon-Coles component.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
