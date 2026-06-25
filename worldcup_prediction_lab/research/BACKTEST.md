# Walk-forward backtest — played WC 2026 matches

Generated: `2026-06-25 13:34 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **54** (2026-06-11 → 2026-06-24)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `form_trend` | 54 | 0.1714 | 0.9260 | 0.5494 | 0.630 | +0.0014 |
| `opp_adj_form` | 54 | 0.1718 | 0.9272 | 0.5509 | 0.630 | +0.0010 |
| `rest_days` | 54 | 0.1720 | 0.9285 | 0.5506 | 0.630 | +0.0008 |
| `competitive_form` | 54 | 0.1721 | 0.9284 | 0.5517 | 0.630 | +0.0007 |
| `weighted_recent_form` | 54 | 0.1722 | 0.9276 | 0.5513 | 0.630 | +0.0006 |
| `attack_defense_form` | 54 | 0.1726 | 0.9300 | 0.5527 | 0.630 | +0.0002 |
| `scoring_form` | 54 | 0.1726 | 0.9300 | 0.5527 | 0.630 | +0.0002 |
| `match_congestion` | 54 | 0.1727 | 0.9304 | 0.5519 | 0.630 | +0.0000 |
| `elo_baseline` (baseline) | 54 | 0.1728 | 0.9308 | 0.5520 | 0.630 | +0.0000 |
| `recent_form` | 54 | 0.1730 | 0.9302 | 0.5529 | 0.630 | -0.0002 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
