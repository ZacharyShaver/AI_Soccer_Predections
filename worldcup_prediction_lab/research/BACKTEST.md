# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-02 18:23 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **76** (2026-06-11 → 2026-06-30)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 76 | 0.1524 | 0.8255 | 0.4992 | 0.711 | +0.0129 |
| `dixon_coles_poisson` | 76 | 0.1532 | 0.8542 | 0.5047 | 0.618 | +0.0121 |
| `dc_elo_fusion` | 76 | 0.1583 | 0.8632 | 0.5166 | 0.605 | +0.0071 |
| `dixon_coles_tuned` | 76 | 0.1588 | 0.8714 | 0.5181 | 0.605 | +0.0066 |
| `squad_value` | 76 | 0.1588 | 0.8568 | 0.5172 | 0.605 | +0.0066 |
| `ml_elo_correction` | 76 | 0.1594 | 0.8730 | 0.5220 | 0.605 | +0.0060 |
| `elo_recalibrated` | 76 | 0.1594 | 0.8593 | 0.5186 | 0.605 | +0.0059 |
| `elo_calibrated` | 76 | 0.1614 | 0.8680 | 0.5218 | 0.605 | +0.0040 |
| `opp_adj_form` | 76 | 0.1634 | 0.9067 | 0.5341 | 0.605 | +0.0020 |
| `ewma_goal_form` | 76 | 0.1635 | 0.9071 | 0.5343 | 0.605 | +0.0019 |
| `attack_defense_form` | 76 | 0.1640 | 0.9090 | 0.5356 | 0.605 | +0.0014 |
| `scoring_form` | 76 | 0.1640 | 0.9090 | 0.5356 | 0.605 | +0.0014 |
| `ensemble_top_k` | 76 | 0.1641 | 0.9089 | 0.5353 | 0.605 | +0.0013 |
| `competitive_form` | 76 | 0.1643 | 0.9096 | 0.5361 | 0.605 | +0.0011 |
| `defensive_form` | 76 | 0.1644 | 0.9102 | 0.5358 | 0.592 | +0.0010 |
| `opp_adj_recent_form` | 76 | 0.1646 | 0.9094 | 0.5362 | 0.605 | +0.0008 |
| `rest_days` | 76 | 0.1648 | 0.9121 | 0.5365 | 0.605 | +0.0006 |
| `recent_form` | 76 | 0.1651 | 0.9112 | 0.5372 | 0.605 | +0.0003 |
| `draw_guard` | 76 | 0.1651 | 0.8899 | 0.5301 | 0.605 | +0.0003 |
| `weighted_recent_form` | 76 | 0.1651 | 0.9109 | 0.5372 | 0.605 | +0.0002 |
| `match_congestion` | 76 | 0.1653 | 0.9133 | 0.5373 | 0.605 | +0.0000 |
| `elo_baseline` (baseline) | 76 | 0.1654 | 0.9138 | 0.5375 | 0.605 | +0.0000 |
| `form_trend` | 76 | 0.1660 | 0.9146 | 0.5388 | 0.605 | -0.0006 |
| `group_incentive` | 76 | 0.1662 | 0.9137 | 0.5374 | 0.645 | -0.0008 |
| `tournament_form` | 76 | 0.1670 | 0.9152 | 0.5389 | 0.605 | -0.0016 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
