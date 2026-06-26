# Walk-forward backtest — played WC 2026 matches

Generated: `2026-06-26 15:33 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **60** (2026-06-11 → 2026-06-25)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rest_days` | 60 | 0.1756 | 0.9420 | 0.5601 | 0.600 | +0.0007 |
| `defensive_form` | 60 | 0.1758 | 0.9421 | 0.5607 | 0.583 | +0.0005 |
| `opp_adj_form` | 60 | 0.1759 | 0.9418 | 0.5616 | 0.600 | +0.0004 |
| `ewma_goal_form` | 60 | 0.1760 | 0.9419 | 0.5616 | 0.600 | +0.0003 |
| `ensemble_top_k` | 60 | 0.1761 | 0.9424 | 0.5617 | 0.600 | +0.0001 |
| `match_congestion` | 60 | 0.1762 | 0.9437 | 0.5613 | 0.600 | +0.0000 |
| `elo_baseline` (baseline) | 60 | 0.1763 | 0.9441 | 0.5613 | 0.600 | +0.0000 |
| `opp_adj_recent_form` | 60 | 0.1764 | 0.9428 | 0.5623 | 0.600 | -0.0002 |
| `attack_defense_form` | 60 | 0.1766 | 0.9443 | 0.5631 | 0.600 | -0.0004 |
| `scoring_form` | 60 | 0.1766 | 0.9443 | 0.5631 | 0.600 | -0.0004 |
| `recent_form` | 60 | 0.1769 | 0.9443 | 0.5631 | 0.600 | -0.0007 |
| `weighted_recent_form` | 60 | 0.1769 | 0.9437 | 0.5629 | 0.600 | -0.0007 |
| `competitive_form` | 60 | 0.1771 | 0.9455 | 0.5641 | 0.600 | -0.0008 |
| `form_trend` | 60 | 0.1772 | 0.9454 | 0.5633 | 0.600 | -0.0009 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
