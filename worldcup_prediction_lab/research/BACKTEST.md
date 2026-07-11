# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-11 13:22 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **98** (2026-06-11 → 2026-07-10)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 98 | 0.1479 | 0.7950 | 0.4733 | 0.724 | +0.0108 |
| `dixon_coles_poisson` | 98 | 0.1533 | 0.8323 | 0.4883 | 0.663 | +0.0055 |
| `squad_value` | 98 | 0.1537 | 0.8241 | 0.4903 | 0.643 | +0.0051 |
| `ml_elo_correction` | 98 | 0.1542 | 0.8361 | 0.4931 | 0.643 | +0.0045 |
| `elo_recalibrated` | 98 | 0.1544 | 0.8266 | 0.4917 | 0.643 | +0.0044 |
| `elo_calibrated` | 98 | 0.1547 | 0.8300 | 0.4917 | 0.643 | +0.0041 |
| `dc_squad_fusion` | 98 | 0.1551 | 0.8327 | 0.4927 | 0.643 | +0.0037 |
| `dc_elo_fusion` | 98 | 0.1554 | 0.8341 | 0.4933 | 0.643 | +0.0034 |
| `opp_adj_form` | 98 | 0.1559 | 0.8560 | 0.4978 | 0.643 | +0.0029 |
| `ewma_goal_form` | 98 | 0.1564 | 0.8572 | 0.4986 | 0.643 | +0.0024 |
| `attack_defense_form` | 98 | 0.1564 | 0.8578 | 0.4989 | 0.643 | +0.0024 |
| `scoring_form` | 98 | 0.1564 | 0.8578 | 0.4989 | 0.643 | +0.0024 |
| `competitive_form` | 98 | 0.1567 | 0.8585 | 0.4995 | 0.643 | +0.0021 |
| `ensemble_top_k` | 98 | 0.1569 | 0.8589 | 0.4993 | 0.643 | +0.0019 |
| `opp_adj_recent_form` | 98 | 0.1569 | 0.8584 | 0.4995 | 0.643 | +0.0019 |
| `dixon_coles_tuned` | 98 | 0.1570 | 0.8437 | 0.4967 | 0.653 | +0.0018 |
| `defensive_form` | 98 | 0.1573 | 0.8610 | 0.5004 | 0.633 | +0.0015 |
| `recent_form` | 98 | 0.1573 | 0.8598 | 0.5003 | 0.643 | +0.0015 |
| `weighted_recent_form` | 98 | 0.1574 | 0.8597 | 0.5004 | 0.643 | +0.0014 |
| `rest_days` | 98 | 0.1583 | 0.8650 | 0.5026 | 0.643 | +0.0004 |
| `elo_baseline` (baseline) | 98 | 0.1588 | 0.8663 | 0.5034 | 0.643 | +0.0000 |
| `match_congestion` | 98 | 0.1591 | 0.8667 | 0.5038 | 0.643 | -0.0003 |
| `form_trend` | 98 | 0.1591 | 0.8654 | 0.5032 | 0.643 | -0.0003 |
| `group_incentive` | 98 | 0.1594 | 0.8663 | 0.5034 | 0.673 | -0.0006 |
| `tournament_form` | 98 | 0.1595 | 0.8653 | 0.5030 | 0.643 | -0.0007 |
| `draw_guard` | 98 | 0.1601 | 0.8553 | 0.5030 | 0.643 | -0.0013 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
