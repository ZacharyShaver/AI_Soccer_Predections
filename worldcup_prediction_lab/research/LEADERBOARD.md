# Daily Model-Research Leaderboard

Generated: `2026-07-09T11:09:20Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 533
- Registered variants: 26

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `competitive_form` | 24 | 0.1406 | 0.7935 | 0.4483 | 0.625 | 0.833 | +0.0178 |
| 2 | `weighted_recent_form` | 24 | 0.1439 | 0.8030 | 0.4556 | 0.625 | 0.833 | +0.0145 |
| 3 | `form_trend` | 24 | 0.1461 | 0.8103 | 0.4590 | 0.625 | 0.833 | +0.0123 |
| 4 | `scoring_form` | 44 | 0.1546 | 0.8040 | 0.4594 | 0.636 | 0.800 | +0.0038 |
| 5 | `opp_adj_form` | 30 | 0.1547 | 0.8484 | 0.4895 | 0.567 | 0.773 | +0.0037 |
| 6 | `attack_defense_form` | 30 | 0.1549 | 0.8491 | 0.4899 | 0.567 | 0.773 | +0.0035 |
| 7 | `ewma_goal_form` | 18 | 0.1551 | 0.8108 | 0.4639 | 0.611 | 0.786 | +0.0033 |
| 8 | `opp_adj_recent_form` | 18 | 0.1557 | 0.8101 | 0.4639 | 0.611 | 0.786 | +0.0027 |
| 9 | `ensemble_top_k` | 18 | 0.1559 | 0.8132 | 0.4651 | 0.611 | 0.786 | +0.0025 |
| 10 | `recent_form` | 44 | 0.1560 | 0.8078 | 0.4623 | 0.636 | 0.800 | +0.0024 |
| 11 | `elo_baseline` (baseline) | 44 | 0.1584 | 0.8180 | 0.4682 | 0.636 | 0.800 | +0.0000 |
| 12 | `defensive_form` | 18 | 0.1584 | 0.8211 | 0.4711 | 0.611 | 0.786 | -0.0000 |
| 13 | `rest_days` | 44 | 0.1586 | 0.8185 | 0.4686 | 0.636 | 0.800 | -0.0002 |
| 14 | `match_congestion` | 30 | 0.1598 | 0.8660 | 0.5004 | 0.567 | 0.773 | -0.0014 |
| 15 | `group_incentive` | 18 | 0.1601 | 0.8103 | 0.4636 | 0.722 | 0.786 | -0.0017 |
| 16 | `draw_guard` | 18 | 0.1621 | 0.8363 | 0.4801 | 0.611 | 0.786 | -0.0037 |
| 17 | `elo_calibrated` | 12 | 0.1704 | 0.8354 | 0.4813 | 0.667 | 0.800 | -0.0120 |
| 18 | `elo_recalibrated` | 12 | 0.1721 | 0.8399 | 0.4828 | 0.667 | 0.800 | -0.0137 |
| 19 | `accuracy_pick_tuned` | 11 | 0.1880 | 0.8873 | 0.5165 | 0.636 | 0.778 | -0.0296 |
| 20 | `dixon_coles_poisson` | 8 | 0.1898 | 0.8240 | 0.4794 | 0.750 | 0.714 | -0.0314 |
| 21 | `ml_elo_correction` | 9 | 0.1903 | 0.8504 | 0.4919 | 0.667 | 0.750 | -0.0319 |
| 22 | `dixon_coles_tuned` | 8 | 0.1909 | 0.8300 | 0.4817 | 0.750 | 0.857 | -0.0325 |
| 23 | `tournament_form` | 9 | 0.1963 | 0.8437 | 0.4927 | 0.667 | 0.750 | -0.0379 |
| 24 | `squad_value` | 6 | 0.2131 | 0.9556 | 0.5665 | 0.500 | 0.600 | -0.0548 |
| 25 | `dc_squad_fusion` | 6 | 0.2158 | 0.9266 | 0.5533 | 0.500 | 0.600 | -0.0574 |
| 26 | `dc_elo_fusion` | 6 | 0.2162 | 0.9278 | 0.5539 | 0.500 | 0.600 | -0.0578 |

## Variants

- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
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
