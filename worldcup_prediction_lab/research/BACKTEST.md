# Walk-forward backtest — played WC 2026 matches

Generated: `2026-07-03 11:32 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **78** (2026-06-11 → 2026-07-02)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accuracy_pick_tuned` | 78 | 0.1507 | 0.8163 | 0.4921 | 0.718 | +0.0132 |
| `dixon_coles_poisson` | 78 | 0.1523 | 0.8474 | 0.4994 | 0.628 | +0.0116 |
| `dc_squad_fusion` | 78 | 0.1567 | 0.8539 | 0.5099 | 0.615 | +0.0072 |
| `dc_elo_fusion` | 78 | 0.1570 | 0.8553 | 0.5104 | 0.615 | +0.0069 |
| `dixon_coles_tuned` | 78 | 0.1575 | 0.8633 | 0.5118 | 0.615 | +0.0064 |
| `squad_value` | 78 | 0.1576 | 0.8494 | 0.5114 | 0.615 | +0.0063 |
| `ml_elo_correction` | 78 | 0.1580 | 0.8644 | 0.5154 | 0.615 | +0.0059 |
| `elo_recalibrated` | 78 | 0.1582 | 0.8518 | 0.5128 | 0.615 | +0.0057 |
| `elo_calibrated` | 78 | 0.1601 | 0.8602 | 0.5159 | 0.615 | +0.0038 |
| `opp_adj_form` | 78 | 0.1616 | 0.8954 | 0.5260 | 0.615 | +0.0024 |
| `ewma_goal_form` | 78 | 0.1617 | 0.8959 | 0.5263 | 0.615 | +0.0022 |
| `attack_defense_form` | 78 | 0.1622 | 0.8977 | 0.5274 | 0.615 | +0.0017 |
| `scoring_form` | 78 | 0.1622 | 0.8977 | 0.5274 | 0.615 | +0.0017 |
| `ensemble_top_k` | 78 | 0.1624 | 0.8978 | 0.5274 | 0.615 | +0.0016 |
| `competitive_form` | 78 | 0.1624 | 0.8982 | 0.5279 | 0.615 | +0.0015 |
| `defensive_form` | 78 | 0.1626 | 0.8990 | 0.5277 | 0.603 | +0.0013 |
| `opp_adj_recent_form` | 78 | 0.1630 | 0.8987 | 0.5285 | 0.615 | +0.0010 |
| `rest_days` | 78 | 0.1634 | 0.9019 | 0.5292 | 0.615 | +0.0006 |
| `recent_form` | 78 | 0.1634 | 0.9004 | 0.5295 | 0.615 | +0.0005 |
| `weighted_recent_form` | 78 | 0.1636 | 0.9004 | 0.5297 | 0.615 | +0.0003 |
| `match_congestion` | 78 | 0.1639 | 0.9031 | 0.5301 | 0.615 | +0.0000 |
| `elo_baseline` (baseline) | 78 | 0.1639 | 0.9036 | 0.5302 | 0.615 | +0.0000 |
| `draw_guard` | 78 | 0.1640 | 0.8823 | 0.5244 | 0.615 | -0.0001 |
| `form_trend` | 78 | 0.1644 | 0.9038 | 0.5312 | 0.615 | -0.0005 |
| `group_incentive` | 78 | 0.1647 | 0.9035 | 0.5301 | 0.654 | -0.0008 |
| `tournament_form` | 78 | 0.1657 | 0.9056 | 0.5320 | 0.615 | -0.0017 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
