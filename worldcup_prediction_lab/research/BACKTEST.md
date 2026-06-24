# Walk-forward backtest — played WC 2026 matches

Generated: `2026-06-24 00:34 UTC`

Leak-free walk-forward: each variant is trained only on results strictly before each match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; accuracy = share of matches whose argmax pick was correct.

- Matches backtested: **44** (2026-06-11 → 2026-06-22)

| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rest_days` | 44 | 0.1711 | 0.9577 | 0.5712 | 0.614 | +0.0010 |
| `opp_adj_form` | 44 | 0.1711 | 0.9569 | 0.5721 | 0.614 | +0.0009 |
| `attack_defense_form` | 44 | 0.1717 | 0.9592 | 0.5735 | 0.614 | +0.0004 |
| `scoring_form` | 44 | 0.1717 | 0.9592 | 0.5735 | 0.614 | +0.0004 |
| `elo_baseline` (baseline) | 44 | 0.1720 | 0.9605 | 0.5728 | 0.614 | +0.0000 |
| `match_congestion` | 44 | 0.1722 | 0.9607 | 0.5732 | 0.614 | -0.0002 |
| `recent_form` | 44 | 0.1726 | 0.9612 | 0.5748 | 0.614 | -0.0006 |

Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each variant per match date, so it grows automatically as more WC matches are played.
