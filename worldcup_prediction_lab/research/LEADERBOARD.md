# Daily Model-Research Leaderboard

Generated: `2026-07-04T20:12:25Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 429
- Registered variants: 26

| Rank | Variant | n | RPS | log loss | Brier | Overall acc | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `dc_elo_fusion` | 2 | 0.0623 | 0.6166 | 0.3557 | 0.500 | 1.000 | +0.0832 |
| 2 | `dc_squad_fusion` | 2 | 0.0627 | 0.6181 | 0.3573 | 0.500 | 1.000 | +0.0828 |
| 3 | `squad_value` | 2 | 0.0660 | 0.6590 | 0.3804 | 0.500 | 1.000 | +0.0795 |
| 4 | `dixon_coles_poisson` | 4 | 0.0857 | 0.5746 | 0.3038 | 1.000 | 1.000 | +0.0599 |
| 5 | `dixon_coles_tuned` | 4 | 0.0859 | 0.5843 | 0.3116 | 0.750 | 1.000 | +0.0597 |
| 6 | `ml_elo_correction` | 5 | 0.1048 | 0.6422 | 0.3507 | 0.800 | 1.000 | +0.0407 |
| 7 | `accuracy_pick_tuned` | 7 | 0.1092 | 0.7073 | 0.3987 | 0.714 | 1.000 | +0.0364 |
| 8 | `competitive_form` | 20 | 0.1098 | 0.7424 | 0.4101 | 0.650 | 0.929 | +0.0357 |
| 9 | `elo_recalibrated` | 8 | 0.1135 | 0.7038 | 0.3919 | 0.750 | 1.000 | +0.0321 |
| 10 | `tournament_form` | 5 | 0.1144 | 0.6712 | 0.3669 | 0.800 | 1.000 | +0.0312 |
| 11 | `weighted_recent_form` | 20 | 0.1149 | 0.7567 | 0.4210 | 0.650 | 0.929 | +0.0307 |
| 12 | `ewma_goal_form` | 14 | 0.1157 | 0.7439 | 0.4149 | 0.643 | 0.900 | +0.0299 |
| 13 | `elo_calibrated` | 8 | 0.1159 | 0.7123 | 0.3984 | 0.750 | 1.000 | +0.0297 |
| 14 | `ensemble_top_k` | 14 | 0.1170 | 0.7478 | 0.4173 | 0.643 | 0.900 | +0.0286 |
| 15 | `form_trend` | 20 | 0.1170 | 0.7636 | 0.4245 | 0.650 | 0.929 | +0.0286 |
| 16 | `opp_adj_recent_form` | 14 | 0.1178 | 0.7468 | 0.4174 | 0.643 | 0.900 | +0.0278 |
| 17 | `defensive_form` | 14 | 0.1195 | 0.7556 | 0.4232 | 0.643 | 0.900 | +0.0260 |
| 18 | `group_incentive` | 14 | 0.1239 | 0.7480 | 0.4172 | 0.786 | 0.900 | +0.0217 |
| 19 | `draw_guard` | 14 | 0.1251 | 0.7582 | 0.4267 | 0.643 | 0.900 | +0.0205 |
| 20 | `opp_adj_form` | 26 | 0.1337 | 0.8192 | 0.4676 | 0.577 | 0.833 | +0.0119 |
| 21 | `attack_defense_form` | 26 | 0.1339 | 0.8199 | 0.4681 | 0.577 | 0.833 | +0.0116 |
| 22 | `match_congestion` | 26 | 0.1389 | 0.8372 | 0.4785 | 0.577 | 0.833 | +0.0067 |
| 23 | `scoring_form` | 40 | 0.1409 | 0.7805 | 0.4422 | 0.650 | 0.839 | +0.0047 |
| 24 | `recent_form` | 40 | 0.1427 | 0.7854 | 0.4459 | 0.650 | 0.839 | +0.0028 |
| 25 | `rest_days` | 40 | 0.1456 | 0.7969 | 0.4524 | 0.650 | 0.839 | +0.0000 |
| 26 | `elo_baseline` (baseline) | 40 | 0.1456 | 0.7969 | 0.4524 | 0.650 | 0.839 | +0.0000 |

## Variants

- `dc_elo_fusion` — Log opinion pool of dixon_coles_tuned (w=0.7) and elo_recalibrated — first fusion to beat its best constituent.  
  feature: Weighted geometric mean of the H/D/A probabilities from the two best, genuinely decorrelated model classes (goal-based Dixon-Coles + outcome-based recalibrated Elo); scoreline shape delegated to the Dixon-Coles component.
- `dc_squad_fusion` — dc_elo_fusion with the squad_value Elo leg — Dixon-Coles pooled with squad-value-aware Elo (current history champion).  
  feature: Swap dc_elo_fusion's plain recalibrated-Elo leg for squad_value so the pool inherits the Transfermarkt squad-value signal the goal-based Dixon-Coles leg cannot see.
- `squad_value` — Recalibrated Elo + Transfermarkt squad-value differential (first non-scoreline signal).  
  feature: Bounded Elo delta from the log ratio of the two sides' Transfermarkt squad values (top-15 citizen market values, monthly, strictly pre-match).
- `dixon_coles_poisson` — Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived).  
  feature: Team attack/defense ratings in log-goal-rate space, online Poisson-regression gradient updates, Dixon-Coles low-score tau correction, host-aware home edge.
- `dixon_coles_tuned` — Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history.  
  feature: Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge.
- `ml_elo_correction` — Trained softmax correction layer blended with recalibrated Elo.  
  feature: Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, neutral/host context, and tournament class; blend learned probabilities with Elo.
- `accuracy_pick_tuned` — Accuracy-first pick layer on top of recalibrated Elo.  
  feature: Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, and already-safe favorite override toward the other side.
- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `elo_recalibrated` — Calibrated Elo plus flat tournament weights (sweep-validated, significant).  
  feature: flat tournament_weights=1.0 on top of K30 / draw_base 0.33 / draw_scale 600.
- `tournament_form` — Elo adjusted for over/under-performance vs expectation in this World Cup.  
  feature: Mean residual (actual result - Elo win-expectation) over each team's 2026 WC matches; hot teams get a small Elo bump, cold teams a small dock. Opponent-adjusted.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `elo_calibrated` — Host-aware Elo with faster K and recalibrated draw mass (no new feature).  
  feature: none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `group_incentive` — Host-aware Elo adjusted for group-stage qualification incentives.  
  feature: Use measurable pre-kickoff group-table state: final group match, draw utility, favorite safety, and underdog points pressure.
- `draw_guard` — Host-aware Elo with a small capped draw-probability guardrail.  
  feature: Move a modest amount of mass from home/away outcomes into draw probability to test whether the live ledger is under-pricing draws.
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

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.
