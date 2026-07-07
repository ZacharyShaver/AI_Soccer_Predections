# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-07 11:27 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **92** (2026-06-11 → 2026-07-05)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 92 | 0.1495 | 0.8013 | 0.4790 | 0.717 | +0.0111 |
| `dixon_coles_poisson` | 92 | 0.1516 | 0.8303 | 0.4875 | 0.652 | +0.0090 |
| `squad_value` | 92 | 0.1554 | 0.8315 | 0.4964 | 0.630 | +0.0052 |
| `dc_squad_fusion` | 92 | 0.1555 | 0.8362 | 0.4960 | 0.630 | +0.0052 |
| `dc_elo_fusion` | 92 | 0.1558 | 0.8375 | 0.4965 | 0.630 | +0.0049 |
| `ml_elo_correction` | 92 | 0.1559 | 0.8440 | 0.4995 | 0.630 | +0.0047 |
| `elo_recalibrated` | 92 | 0.1561 | 0.8339 | 0.4977 | 0.630 | +0.0046 |
| `elo_calibrated` | 92 | 0.1566 | 0.8379 | 0.4982 | 0.630 | +0.0040 |
| `dixon_coles_tuned` | 92 | 0.1567 | 0.8455 | 0.4985 | 0.641 | +0.0040 |
| `opp_adj_form` | 92 | 0.1582 | 0.8666 | 0.5058 | 0.630 | +0.0025 |
| `ewma_goal_form` | 92 | 0.1585 | 0.8674 | 0.5063 | 0.630 | +0.0022 |
| `attack_defense_form` | 92 | 0.1587 | 0.8686 | 0.5071 | 0.630 | +0.0019 |
| `scoring_form` | 92 | 0.1587 | 0.8686 | 0.5071 | 0.630 | +0.0019 |
| `competitive_form` | 92 | 0.1589 | 0.8689 | 0.5074 | 0.630 | +0.0017 |
| `ensemble_top_k` | 92 | 0.1591 | 0.8694 | 0.5073 | 0.630 | +0.0015 |
| `opp_adj_recent_form` | 92 | 0.1591 | 0.8687 | 0.5074 | 0.630 | +0.0015 |
| `defensive_form` | 92 | 0.1594 | 0.8712 | 0.5081 | 0.620 | +0.0012 |
| `recent_form` | 92 | 0.1595 | 0.8702 | 0.5082 | 0.630 | +0.0011 |
| `weighted_recent_form` | 92 | 0.1596 | 0.8701 | 0.5083 | 0.630 | +0.0010 |
| `rest_days` | 92 | 0.1602 | 0.8744 | 0.5098 | 0.630 | +0.0004 |
| `elo_baseline` (baseline) | 92 | 0.1606 | 0.8757 | 0.5106 | 0.630 | +0.0000 |
| `match_congestion` | 92 | 0.1608 | 0.8759 | 0.5108 | 0.630 | -0.0002 |
| `tournament_form` | 92 | 0.1611 | 0.8738 | 0.5094 | 0.630 | -0.0005 |
| `group_incentive` | 92 | 0.1613 | 0.8757 | 0.5105 | 0.663 | -0.0007 |
| `form_trend` | 92 | 0.1614 | 0.8760 | 0.5113 | 0.630 | -0.0007 |
| `draw_guard` | 92 | 0.1616 | 0.8623 | 0.5086 | 0.630 | -0.0009 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
