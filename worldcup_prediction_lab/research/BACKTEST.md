# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-10 11:33 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **96** (2026-06-11 → 2026-07-07)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 96 | 0.1492 | 0.8012 | 0.4783 | 0.719 | +0.0105 |
| `dixon_coles_poisson` | 96 | 0.1514 | 0.8295 | 0.4864 | 0.656 | +0.0084 |
| `squad_value` | 96 | 0.1545 | 0.8290 | 0.4942 | 0.635 | +0.0053 |
| `dc_squad_fusion` | 96 | 0.1549 | 0.8348 | 0.4946 | 0.635 | +0.0048 |
| `elo_recalibrated` | 96 | 0.1551 | 0.8314 | 0.4956 | 0.635 | +0.0046 |
| `ml_elo_correction` | 96 | 0.1552 | 0.8418 | 0.4976 | 0.635 | +0.0046 |
| `dc_elo_fusion` | 96 | 0.1552 | 0.8361 | 0.4951 | 0.635 | +0.0046 |
| `elo_calibrated` | 96 | 0.1557 | 0.8355 | 0.4960 | 0.635 | +0.0041 |
| `dixon_coles_tuned` | 96 | 0.1563 | 0.8445 | 0.4975 | 0.646 | +0.0035 |
| `opp_adj_form` | 96 | 0.1570 | 0.8631 | 0.5031 | 0.635 | +0.0028 |
| `ewma_goal_form` | 96 | 0.1573 | 0.8638 | 0.5034 | 0.635 | +0.0025 |
| `attack_defense_form` | 96 | 0.1575 | 0.8650 | 0.5043 | 0.635 | +0.0022 |
| `scoring_form` | 96 | 0.1575 | 0.8650 | 0.5043 | 0.635 | +0.0022 |
| `ensemble_top_k` | 96 | 0.1578 | 0.8656 | 0.5043 | 0.635 | +0.0019 |
| `competitive_form` | 96 | 0.1578 | 0.8657 | 0.5048 | 0.635 | +0.0019 |
| `opp_adj_recent_form` | 96 | 0.1580 | 0.8655 | 0.5048 | 0.635 | +0.0018 |
| `recent_form` | 96 | 0.1584 | 0.8669 | 0.5056 | 0.635 | +0.0014 |
| `defensive_form` | 96 | 0.1584 | 0.8684 | 0.5058 | 0.625 | +0.0013 |
| `weighted_recent_form` | 96 | 0.1585 | 0.8667 | 0.5056 | 0.635 | +0.0013 |
| `rest_days` | 96 | 0.1593 | 0.8717 | 0.5076 | 0.635 | +0.0004 |
| `elo_baseline` (baseline) | 96 | 0.1597 | 0.8731 | 0.5085 | 0.635 | +0.0000 |
| `form_trend` | 96 | 0.1599 | 0.8716 | 0.5078 | 0.635 | -0.0002 |
| `match_congestion` | 96 | 0.1600 | 0.8735 | 0.5088 | 0.635 | -0.0003 |
| `group_incentive` | 96 | 0.1604 | 0.8730 | 0.5084 | 0.667 | -0.0006 |
| `tournament_form` | 96 | 0.1605 | 0.8721 | 0.5080 | 0.635 | -0.0008 |
| `draw_guard` | 96 | 0.1608 | 0.8602 | 0.5068 | 0.635 | -0.0011 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
