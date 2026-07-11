# Daily Model-Research Leaderboard

Generated: `2026-07-11T13:03:01Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 637
- Registered variants: 26

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `competitive_form` | 28 | 0.1345 | 0.7782 | 0.4367 | 0.643 | 0.857 | +0.0194 |
| 2 | `weighted_recent_form` | 28 | 0.1376 | 0.7872 | 0.4436 | 0.643 | 0.857 | +0.0163 |
| 3 | `form_trend` | 28 | 0.1405 | 0.7964 | 0.4484 | 0.643 | 0.857 | +0.0134 |
| 4 | `opp_adj_recent_form` | 22 | 0.1454 | 0.7888 | 0.4473 | 0.636 | 0.824 | +0.0085 |
| 5 | `ewma_goal_form` | 22 | 0.1455 | 0.7904 | 0.4479 | 0.636 | 0.824 | +0.0084 |
| 6 | `ensemble_top_k` | 22 | 0.1461 | 0.7925 | 0.4489 | 0.636 | 0.824 | +0.0078 |
| 7 | `defensive_form` | 22 | 0.1478 | 0.7985 | 0.4536 | 0.636 | 0.824 | +0.0061 |
| 8 | `opp_adj_form` | 34 | 0.1480 | 0.8295 | 0.4752 | 0.588 | 0.800 | +0.0059 |
| 9 | `attack_defense_form` | 34 | 0.1482 | 0.8301 | 0.4756 | 0.588 | 0.800 | +0.0057 |
| 10 | `scoring_form` | 48 | 0.1498 | 0.7943 | 0.4519 | 0.646 | 0.816 | +0.0041 |
| 11 | `group_incentive` | 22 | 0.1499 | 0.7921 | 0.4489 | 0.727 | 0.824 | +0.0040 |
| 12 | `recent_form` | 48 | 0.1513 | 0.7983 | 0.4549 | 0.646 | 0.816 | +0.0026 |
| 13 | `elo_calibrated` | 16 | 0.1515 | 0.7906 | 0.4503 | 0.688 | 0.846 | +0.0024 |
| 14 | `draw_guard` | 22 | 0.1525 | 0.8129 | 0.4635 | 0.636 | 0.824 | +0.0014 |
| 15 | `match_congestion` | 34 | 0.1532 | 0.8473 | 0.4863 | 0.588 | 0.800 | +0.0007 |
| 16 | `elo_baseline` (baseline) | 48 | 0.1539 | 0.8090 | 0.4611 | 0.646 | 0.816 | +0.0000 |
| 17 | `rest_days` | 48 | 0.1541 | 0.8093 | 0.4613 | 0.646 | 0.816 | -0.0002 |
| 18 | `elo_recalibrated` | 16 | 0.1545 | 0.7991 | 0.4559 | 0.688 | 0.846 | -0.0006 |
| 19 | `accuracy_pick_tuned` | 15 | 0.1602 | 0.8183 | 0.4692 | 0.667 | 0.833 | -0.0063 |
| 20 | `ml_elo_correction` | 13 | 0.1621 | 0.7960 | 0.4536 | 0.692 | 0.818 | -0.0082 |
| 21 | `squad_value` | 10 | 0.1676 | 0.8408 | 0.4876 | 0.600 | 0.750 | -0.0137 |
| 22 | `tournament_form` | 13 | 0.1680 | 0.8024 | 0.4587 | 0.692 | 0.818 | -0.0141 |
| 23 | `dixon_coles_tuned` | 12 | 0.1761 | 0.8306 | 0.4813 | 0.750 | 0.900 | -0.0222 |
| 24 | `dc_squad_fusion` | 10 | 0.1814 | 0.8667 | 0.5090 | 0.600 | 0.750 | -0.0275 |
| 25 | `dc_elo_fusion` | 10 | 0.1820 | 0.8686 | 0.5102 | 0.600 | 0.750 | -0.0281 |
| 26 | `dixon_coles_poisson` | 12 | 0.1836 | 0.8486 | 0.4947 | 0.750 | 0.800 | -0.0297 |

## Variants

- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.
- `squad_value` — Recalibrated Elo + Transfermarkt squad-value differential (first non-scoreline signal).  
  feature: Bounded Elo delta from the log ratio of the two sides' Transfermarkt squad values (top-15 citizen market values, monthly, strictly pre-match).
- `tournament_form` — Elo adjusted for over/under-performance vs expectation in this World Cup.  
  feature: Mean residual (actual result - Elo win-expectation) over each team's 2026 WC matches; hot teams get a small Elo bump, cold teams a small dock. Opponent-adjusted.
- `dixon_coles_tuned` — Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history.  
  feature: Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge.
- `dc_squad_fusion` — dc_elo_fusion with the squad_value Elo leg — Dixon-Coles pooled with squad-value-aware Elo (current history champion).  
  feature: Swap dc_elo_fusion's plain recalibrated-Elo leg for squad_value so the pool inherits the Transfermarkt squad-value signal the goal-based Dixon-Coles leg cannot see.
- `dc_elo_fusion` — Log opinion pool of dixon_coles_tuned (w=0.7) and elo_recalibrated — first fusion to beat its best constituent.  
  feature: Weighted geometric mean of the H/D/A probabilities from the two best, genuinely decorrelated model classes (goal-based Dixon-Coles + outcome-based recalibrated Elo); scoreline shape delegated to the Dixon-Coles component.
- `dixon_coles_poisson` — Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived).  
  feature: Team attack/defense ratings in log-goal-rate space, online Poisson-regression gradient updates, Dixon-Coles low-score tau correction, host-aware home edge.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
