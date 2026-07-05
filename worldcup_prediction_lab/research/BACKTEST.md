# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-05 11:36 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **80** (2026-06-11 → 2026-07-03)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 80 | 0.1487 | 0.8128 | 0.4898 | 0.713 | +0.0131 |
| `dixon_coles_poisson` | 80 | 0.1499 | 0.8403 | 0.4946 | 0.637 | +0.0119 |
| `dc_squad_fusion` | 80 | 0.1544 | 0.8480 | 0.5061 | 0.613 | +0.0074 |
| `dc_elo_fusion` | 80 | 0.1546 | 0.8494 | 0.5066 | 0.613 | +0.0072 |
| `dixon_coles_tuned` | 80 | 0.1551 | 0.8571 | 0.5078 | 0.613 | +0.0067 |
| `squad_value` | 80 | 0.1553 | 0.8446 | 0.5081 | 0.613 | +0.0065 |
| `ml_elo_correction` | 80 | 0.1558 | 0.8600 | 0.5125 | 0.613 | +0.0060 |
| `elo_recalibrated` | 80 | 0.1559 | 0.8469 | 0.5094 | 0.613 | +0.0059 |
| `elo_calibrated` | 80 | 0.1578 | 0.8556 | 0.5127 | 0.613 | +0.0040 |
| `opp_adj_form` | 80 | 0.1594 | 0.8921 | 0.5238 | 0.613 | +0.0024 |
| `ewma_goal_form` | 80 | 0.1596 | 0.8925 | 0.5241 | 0.613 | +0.0022 |
| `attack_defense_form` | 80 | 0.1600 | 0.8942 | 0.5252 | 0.613 | +0.0018 |
| `scoring_form` | 80 | 0.1600 | 0.8942 | 0.5252 | 0.613 | +0.0018 |
| `ensemble_top_k` | 80 | 0.1602 | 0.8943 | 0.5251 | 0.613 | +0.0016 |
| `competitive_form` | 80 | 0.1603 | 0.8947 | 0.5256 | 0.613 | +0.0015 |
| `defensive_form` | 80 | 0.1605 | 0.8961 | 0.5258 | 0.600 | +0.0013 |
| `opp_adj_recent_form` | 80 | 0.1608 | 0.8953 | 0.5262 | 0.613 | +0.0010 |
| `recent_form` | 80 | 0.1612 | 0.8969 | 0.5272 | 0.613 | +0.0006 |
| `rest_days` | 80 | 0.1613 | 0.8990 | 0.5273 | 0.613 | +0.0005 |
| `weighted_recent_form` | 80 | 0.1614 | 0.8969 | 0.5275 | 0.613 | +0.0004 |
| `draw_guard` | 80 | 0.1617 | 0.8779 | 0.5213 | 0.613 | +0.0001 |
| `match_congestion` | 80 | 0.1618 | 0.9001 | 0.5281 | 0.613 | +0.0000 |
| `elo_baseline` (baseline) | 80 | 0.1618 | 0.9006 | 0.5282 | 0.613 | +0.0000 |
| `form_trend` | 80 | 0.1621 | 0.9000 | 0.5286 | 0.613 | -0.0004 |
| `group_incentive` | 80 | 0.1626 | 0.9005 | 0.5281 | 0.650 | -0.0008 |
| `tournament_form` | 80 | 0.1634 | 0.9017 | 0.5294 | 0.613 | -0.0016 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
