# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-11 11:24 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **97** (2026-06-11 → 2026-07-09)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 97 | 0.1487 | 0.7987 | 0.4762 | 0.722 | +0.0106 |
| `dixon_coles_poisson` | 97 | 0.1524 | 0.8314 | 0.4877 | 0.660 | +0.0069 |
| `squad_value` | 97 | 0.1543 | 0.8271 | 0.4927 | 0.639 | +0.0051 |
| `ml_elo_correction` | 97 | 0.1549 | 0.8395 | 0.4957 | 0.639 | +0.0045 |
| `elo_recalibrated` | 97 | 0.1549 | 0.8296 | 0.4941 | 0.639 | +0.0044 |
| `dc_squad_fusion` | 97 | 0.1551 | 0.8342 | 0.4940 | 0.639 | +0.0043 |
| `dc_elo_fusion` | 97 | 0.1554 | 0.8355 | 0.4945 | 0.639 | +0.0040 |
| `elo_calibrated` | 97 | 0.1554 | 0.8334 | 0.4944 | 0.639 | +0.0040 |
| `opp_adj_form` | 97 | 0.1565 | 0.8597 | 0.5005 | 0.639 | +0.0029 |
| `dixon_coles_tuned` | 97 | 0.1567 | 0.8443 | 0.4973 | 0.649 | +0.0027 |
| `ewma_goal_form` | 97 | 0.1569 | 0.8607 | 0.5011 | 0.639 | +0.0025 |
| `attack_defense_form` | 97 | 0.1570 | 0.8616 | 0.5017 | 0.639 | +0.0024 |
| `scoring_form` | 97 | 0.1570 | 0.8616 | 0.5017 | 0.639 | +0.0024 |
| `competitive_form` | 97 | 0.1573 | 0.8622 | 0.5023 | 0.639 | +0.0021 |
| `ensemble_top_k` | 97 | 0.1575 | 0.8625 | 0.5020 | 0.639 | +0.0019 |
| `opp_adj_recent_form` | 97 | 0.1575 | 0.8622 | 0.5024 | 0.639 | +0.0018 |
| `recent_form` | 97 | 0.1579 | 0.8636 | 0.5032 | 0.639 | +0.0015 |
| `defensive_form` | 97 | 0.1580 | 0.8652 | 0.5035 | 0.629 | +0.0014 |
| `weighted_recent_form` | 97 | 0.1580 | 0.8634 | 0.5032 | 0.639 | +0.0013 |
| `rest_days` | 97 | 0.1589 | 0.8687 | 0.5054 | 0.639 | +0.0004 |
| `elo_baseline` (baseline) | 97 | 0.1594 | 0.8701 | 0.5062 | 0.639 | +0.0000 |
| `match_congestion` | 97 | 0.1597 | 0.8705 | 0.5066 | 0.639 | -0.0003 |
| `form_trend` | 97 | 0.1597 | 0.8691 | 0.5059 | 0.639 | -0.0003 |
| `group_incentive` | 97 | 0.1600 | 0.8700 | 0.5062 | 0.670 | -0.0006 |
| `tournament_form` | 97 | 0.1601 | 0.8690 | 0.5057 | 0.639 | -0.0007 |
| `draw_guard` | 97 | 0.1606 | 0.8582 | 0.5052 | 0.639 | -0.0012 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
