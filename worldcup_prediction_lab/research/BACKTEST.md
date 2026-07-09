# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-09 11:26 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **94** (2026-06-11 → 2026-07-06)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 94 | 0.1507 | 0.8020 | 0.4790 | 0.723 | +0.0104 |
| `dixon_coles_poisson` | 94 | 0.1526 | 0.8295 | 0.4867 | 0.660 | +0.0085 |
| `squad_value` | 94 | 0.1560 | 0.8307 | 0.4954 | 0.638 | +0.0051 |
| `dc_squad_fusion` | 94 | 0.1562 | 0.8351 | 0.4949 | 0.638 | +0.0049 |
| `dc_elo_fusion` | 94 | 0.1565 | 0.8363 | 0.4954 | 0.638 | +0.0046 |
| `ml_elo_correction` | 94 | 0.1566 | 0.8429 | 0.4984 | 0.638 | +0.0045 |
| `elo_recalibrated` | 94 | 0.1566 | 0.8330 | 0.4967 | 0.638 | +0.0045 |
| `elo_calibrated` | 94 | 0.1573 | 0.8374 | 0.4974 | 0.638 | +0.0038 |
| `dixon_coles_tuned` | 94 | 0.1575 | 0.8442 | 0.4974 | 0.649 | +0.0036 |
| `opp_adj_form` | 94 | 0.1584 | 0.8632 | 0.5033 | 0.638 | +0.0027 |
| `ewma_goal_form` | 94 | 0.1587 | 0.8640 | 0.5038 | 0.638 | +0.0024 |
| `attack_defense_form` | 94 | 0.1589 | 0.8651 | 0.5045 | 0.638 | +0.0022 |
| `scoring_form` | 94 | 0.1589 | 0.8651 | 0.5045 | 0.638 | +0.0022 |
| `ensemble_top_k` | 94 | 0.1592 | 0.8657 | 0.5046 | 0.638 | +0.0019 |
| `competitive_form` | 94 | 0.1592 | 0.8658 | 0.5051 | 0.638 | +0.0019 |
| `opp_adj_recent_form` | 94 | 0.1593 | 0.8655 | 0.5049 | 0.638 | +0.0017 |
| `defensive_form` | 94 | 0.1597 | 0.8680 | 0.5057 | 0.628 | +0.0014 |
| `recent_form` | 94 | 0.1597 | 0.8669 | 0.5057 | 0.638 | +0.0013 |
| `weighted_recent_form` | 94 | 0.1599 | 0.8668 | 0.5058 | 0.638 | +0.0012 |
| `rest_days` | 94 | 0.1607 | 0.8717 | 0.5078 | 0.638 | +0.0004 |
| `elo_baseline` (baseline) | 94 | 0.1611 | 0.8730 | 0.5086 | 0.638 | +0.0000 |
| `form_trend` | 94 | 0.1613 | 0.8719 | 0.5083 | 0.638 | -0.0003 |
| `match_congestion` | 94 | 0.1614 | 0.8735 | 0.5090 | 0.638 | -0.0003 |
| `group_incentive` | 94 | 0.1618 | 0.8729 | 0.5085 | 0.670 | -0.0007 |
| `tournament_form` | 94 | 0.1619 | 0.8719 | 0.5081 | 0.638 | -0.0008 |
| `draw_guard` | 94 | 0.1623 | 0.8616 | 0.5079 | 0.638 | -0.0012 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
