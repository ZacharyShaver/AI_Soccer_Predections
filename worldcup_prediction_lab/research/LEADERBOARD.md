# Daily Model-Research Leaderboard

Generated: `2026-07-07T11:11:39Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 481
- Registered variants: 26

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `competitive_form` | 22 | 0.1375 | 0.7997 | 0.4526 | 0.591 | 0.812 | +0.0197 |
| 2 | `weighted_recent_form` | 22 | 0.1414 | 0.8109 | 0.4612 | 0.591 | 0.812 | +0.0158 |
| 3 | `form_trend` | 22 | 0.1449 | 0.8219 | 0.4672 | 0.591 | 0.812 | +0.0124 |
| 4 | `ewma_goal_form` | 16 | 0.1535 | 0.8239 | 0.4736 | 0.562 | 0.750 | +0.0038 |
| 5 | `opp_adj_recent_form` | 16 | 0.1537 | 0.8220 | 0.4728 | 0.562 | 0.750 | +0.0035 |
| 6 | `opp_adj_form` | 28 | 0.1538 | 0.8587 | 0.4969 | 0.536 | 0.750 | +0.0035 |
| 7 | `scoring_form` | 42 | 0.1539 | 0.8087 | 0.4630 | 0.619 | 0.788 | +0.0033 |
| 8 | `attack_defense_form` | 28 | 0.1540 | 0.8594 | 0.4974 | 0.536 | 0.750 | +0.0033 |
| 9 | `ensemble_top_k` | 16 | 0.1547 | 0.8277 | 0.4758 | 0.562 | 0.750 | +0.0026 |
| 10 | `recent_form` | 42 | 0.1552 | 0.8122 | 0.4656 | 0.619 | 0.788 | +0.0020 |
| 11 | `defensive_form` | 16 | 0.1566 | 0.8337 | 0.4804 | 0.562 | 0.750 | +0.0006 |
| 12 | `elo_baseline` (baseline) | 42 | 0.1573 | 0.8213 | 0.4706 | 0.619 | 0.788 | +0.0000 |
| 13 | `group_incentive` | 16 | 0.1573 | 0.8182 | 0.4693 | 0.688 | 0.750 | -0.0000 |
| 14 | `rest_days` | 42 | 0.1575 | 0.8219 | 0.4710 | 0.619 | 0.788 | -0.0002 |
| 15 | `match_congestion` | 28 | 0.1578 | 0.8732 | 0.5055 | 0.536 | 0.750 | -0.0005 |
| 16 | `draw_guard` | 16 | 0.1579 | 0.8373 | 0.4806 | 0.562 | 0.750 | -0.0007 |
| 17 | `elo_calibrated` | 10 | 0.1669 | 0.8402 | 0.4849 | 0.600 | 0.750 | -0.0096 |
| 18 | `elo_recalibrated` | 10 | 0.1701 | 0.8493 | 0.4893 | 0.600 | 0.750 | -0.0129 |
| 19 | `accuracy_pick_tuned` | 9 | 0.1844 | 0.8990 | 0.5245 | 0.556 | 0.714 | -0.0271 |
| 20 | `dixon_coles_poisson` | 6 | 0.1887 | 0.8346 | 0.4893 | 0.667 | 0.600 | -0.0314 |
| 21 | `dixon_coles_tuned` | 6 | 0.1897 | 0.8442 | 0.4930 | 0.667 | 0.800 | -0.0324 |
| 22 | `ml_elo_correction` | 7 | 0.1910 | 0.8659 | 0.5033 | 0.571 | 0.667 | -0.0337 |
| 23 | `tournament_form` | 7 | 0.1966 | 0.8595 | 0.5057 | 0.571 | 0.667 | -0.0393 |
| 24 | `squad_value` | 4 | 0.2288 | 1.0370 | 0.6247 | 0.250 | 0.333 | -0.0715 |
| 25 | `dc_squad_fusion` | 4 | 0.2290 | 0.9973 | 0.6077 | 0.250 | 0.333 | -0.0717 |
| 26 | `dc_elo_fusion` | 4 | 0.2296 | 0.9990 | 0.6085 | 0.250 | 0.333 | -0.0723 |

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
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `dixon_coles_poisson` — Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived).  
  feature: Team attack/defense ratings in log-goal-rate space, online Poisson-regression gradient updates, Dixon-Coles low-score tau correction, host-aware home edge.
- `dixon_coles_tuned` — Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history.  
  feature: Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.
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
