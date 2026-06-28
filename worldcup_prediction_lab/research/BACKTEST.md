# Walk-forward backtest — played WC 2026 matches

Generated: `2026-06-28 14:19 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **72** (2026-06-11 → 2026-06-27)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `elo_recalibrated` | 72 | 0.1606 | 0.8628 | 0.5224 | 0.597 | +0.0054 |
| `elo_calibrated` | 72 | 0.1625 | 0.8715 | 0.5254 | 0.597 | +0.0035 |
| `ewma_goal_form` | 72 | 0.1642 | 0.9103 | 0.5373 | 0.597 | +0.0019 |
| `opp_adj_form` | 72 | 0.1643 | 0.9108 | 0.5378 | 0.597 | +0.0017 |
| `defensive_form` | 72 | 0.1645 | 0.9120 | 0.5376 | 0.583 | +0.0016 |
| `ensemble_top_k` | 72 | 0.1647 | 0.9117 | 0.5380 | 0.597 | +0.0014 |
| `attack_defense_form` | 72 | 0.1650 | 0.9135 | 0.5394 | 0.597 | +0.0010 |
| `scoring_form` | 72 | 0.1650 | 0.9135 | 0.5394 | 0.597 | +0.0010 |
| `opp_adj_recent_form` | 72 | 0.1652 | 0.9127 | 0.5391 | 0.597 | +0.0008 |
| `competitive_form` | 72 | 0.1653 | 0.9138 | 0.5398 | 0.597 | +0.0008 |
| `draw_guard` | 72 | 0.1654 | 0.8916 | 0.5320 | 0.597 | +0.0006 |
| `rest_days` | 72 | 0.1654 | 0.9155 | 0.5395 | 0.597 | +0.0006 |
| `weighted_recent_form` | 72 | 0.1657 | 0.9138 | 0.5400 | 0.597 | +0.0003 |
| `recent_form` | 72 | 0.1657 | 0.9146 | 0.5403 | 0.597 | +0.0003 |
| `match_congestion` | 72 | 0.1660 | 0.9169 | 0.5404 | 0.597 | +0.0000 |
| `elo_baseline` (baseline) | 72 | 0.1660 | 0.9172 | 0.5405 | 0.597 | +0.0000 |
| `form_trend` | 72 | 0.1662 | 0.9159 | 0.5403 | 0.597 | -0.0001 |
| `group_incentive` | 72 | 0.1669 | 0.9171 | 0.5404 | 0.639 | -0.0009 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
