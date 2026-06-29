# Walk-forward backtest — played WC 2026 matches

Generated: `2026-06-29 13:11 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **73** (2026-06-11 → 2026-06-28)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 73 | 0.1524 | 0.8229 | 0.4985 | 0.712 | +0.0129 |
| `ml_elo_correction` | 73 | 0.1596 | 0.8718 | 0.5219 | 0.603 | +0.0057 |
| `elo_recalibrated` | 73 | 0.1597 | 0.8581 | 0.5187 | 0.603 | +0.0056 |
| `elo_calibrated` | 73 | 0.1618 | 0.8675 | 0.5223 | 0.603 | +0.0035 |
| `ewma_goal_form` | 73 | 0.1633 | 0.9049 | 0.5333 | 0.603 | +0.0020 |
| `opp_adj_form` | 73 | 0.1635 | 0.9054 | 0.5337 | 0.603 | +0.0019 |
| `ensemble_top_k` | 73 | 0.1638 | 0.9063 | 0.5340 | 0.603 | +0.0015 |
| `defensive_form` | 73 | 0.1639 | 0.9073 | 0.5341 | 0.589 | +0.0015 |
| `attack_defense_form` | 73 | 0.1641 | 0.9079 | 0.5353 | 0.603 | +0.0012 |
| `scoring_form` | 73 | 0.1641 | 0.9079 | 0.5353 | 0.603 | +0.0012 |
| `competitive_form` | 73 | 0.1643 | 0.9081 | 0.5355 | 0.603 | +0.0010 |
| `opp_adj_recent_form` | 73 | 0.1646 | 0.9079 | 0.5356 | 0.603 | +0.0008 |
| `rest_days` | 73 | 0.1648 | 0.9106 | 0.5358 | 0.603 | +0.0006 |
| `draw_guard` | 73 | 0.1650 | 0.8881 | 0.5293 | 0.603 | +0.0004 |
| `recent_form` | 73 | 0.1651 | 0.9097 | 0.5366 | 0.603 | +0.0003 |
| `weighted_recent_form` | 73 | 0.1651 | 0.9093 | 0.5365 | 0.603 | +0.0002 |
| `match_congestion` | 73 | 0.1653 | 0.9120 | 0.5368 | 0.603 | +0.0000 |
| `form_trend` | 73 | 0.1654 | 0.9106 | 0.5364 | 0.603 | +0.0000 |
| `elo_baseline` (baseline) | 73 | 0.1654 | 0.9123 | 0.5368 | 0.603 | +0.0000 |
| `group_incentive` | 73 | 0.1662 | 0.9122 | 0.5368 | 0.644 | -0.0009 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
