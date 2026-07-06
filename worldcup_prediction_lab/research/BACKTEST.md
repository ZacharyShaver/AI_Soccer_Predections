# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-06 11:27 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **90** (2026-06-11 → 2026-07-04)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 90 | 0.1429 | 0.7842 | 0.4682 | 0.733 | +0.0126 |
| `dixon_coles_poisson` | 90 | 0.1462 | 0.8186 | 0.4792 | 0.667 | +0.0093 |
| `dc_squad_fusion` | 90 | 0.1502 | 0.8242 | 0.4880 | 0.644 | +0.0054 |
| `squad_value` | 90 | 0.1502 | 0.8185 | 0.4881 | 0.644 | +0.0053 |
| `ml_elo_correction` | 90 | 0.1504 | 0.8311 | 0.4909 | 0.644 | +0.0051 |
| `dc_elo_fusion` | 90 | 0.1504 | 0.8254 | 0.4884 | 0.644 | +0.0051 |
| `elo_recalibrated` | 90 | 0.1507 | 0.8206 | 0.4892 | 0.644 | +0.0048 |
| `dixon_coles_tuned` | 90 | 0.1513 | 0.8339 | 0.4906 | 0.644 | +0.0042 |
| `elo_calibrated` | 90 | 0.1518 | 0.8265 | 0.4908 | 0.644 | +0.0037 |
| `opp_adj_form` | 90 | 0.1525 | 0.8554 | 0.4976 | 0.644 | +0.0030 |
| `ewma_goal_form` | 90 | 0.1527 | 0.8560 | 0.4979 | 0.644 | +0.0028 |
| `attack_defense_form` | 90 | 0.1530 | 0.8574 | 0.4989 | 0.644 | +0.0025 |
| `scoring_form` | 90 | 0.1530 | 0.8574 | 0.4989 | 0.644 | +0.0025 |
| `competitive_form` | 90 | 0.1532 | 0.8577 | 0.4992 | 0.644 | +0.0023 |
| `ensemble_top_k` | 90 | 0.1533 | 0.8579 | 0.4989 | 0.644 | +0.0022 |
| `opp_adj_recent_form` | 90 | 0.1536 | 0.8581 | 0.4995 | 0.644 | +0.0019 |
| `defensive_form` | 90 | 0.1537 | 0.8599 | 0.4998 | 0.633 | +0.0018 |
| `recent_form` | 90 | 0.1540 | 0.8595 | 0.5004 | 0.644 | +0.0015 |
| `weighted_recent_form` | 90 | 0.1541 | 0.8593 | 0.5004 | 0.644 | +0.0014 |
| `rest_days` | 90 | 0.1550 | 0.8645 | 0.5024 | 0.644 | +0.0006 |
| `match_congestion` | 90 | 0.1554 | 0.8655 | 0.5031 | 0.644 | +0.0001 |
| `elo_baseline` (baseline) | 90 | 0.1555 | 0.8661 | 0.5034 | 0.644 | +0.0000 |
| `form_trend` | 90 | 0.1556 | 0.8643 | 0.5028 | 0.644 | -0.0000 |
| `tournament_form` | 90 | 0.1558 | 0.8636 | 0.5018 | 0.644 | -0.0003 |
| `group_incentive` | 90 | 0.1562 | 0.8660 | 0.5033 | 0.678 | -0.0007 |
| `draw_guard` | 90 | 0.1565 | 0.8506 | 0.5008 | 0.644 | -0.0010 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
