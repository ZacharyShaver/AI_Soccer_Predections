# Recency experiment: does down-weighting old matches help Elo?

Walk-forward backtest (train_start 1990-01-01, predictions 2010-01-01 -> 2026-06-10, 30-day windows). Lower is better. Bootstrap 95% CIs, 1000 resamples. Generated 2026-06-22T11:14:33Z.

## Per-variant metrics

| Variant | n | RPS [95% CI] | H/D/A log loss [95% CI] | Brier [95% CI] |
| --- | ---: | --- | --- | --- |
| full_history_k20 (baseline) | 15817 | 0.1776 [0.1755, 0.1801] | 0.9047 [0.8958, 0.9145] | 0.5313 [0.5250, 0.5380] |
| low_k10 | 15817 | 0.1816 [0.1796, 0.1837] | 0.9180 [0.9099, 0.9268] | 0.5392 [0.5333, 0.5453] |
| high_k30 | 15817 | 0.1767 [0.1745, 0.1793] | 0.9012 [0.8913, 0.9107] | 0.5299 [0.5235, 0.5369] |
| high_k40 | 15817 | 0.1770 [0.1746, 0.1796] | 0.9019 [0.8915, 0.9116] | 0.5306 [0.5240, 0.5377] |
| window_8y | 15817 | 0.1855 [0.1835, 0.1876] | 0.9299 [0.9218, 0.9381] | 0.5472 [0.5414, 0.5530] |
| window_4y | 15817 | 0.1933 [0.1915, 0.1951] | 0.9538 [0.9469, 0.9609] | 0.5630 [0.5582, 0.5681] |
| window_2y | 15817 | 0.2036 [0.2019, 0.2052] | 0.9840 [0.9779, 0.9901] | 0.5843 [0.5801, 0.5887] |

## Paired comparison vs `full_history_k20` (baseline minus variant; positive = variant better)

| Variant | mean RPS diff [95% CI] | Verdict |
| --- | --- | --- |
| low_k10 | -0.00398 [-0.00448, -0.00346] | variant WORSE than baseline beyond noise |
| high_k30 | +0.00086 [+0.00054, +0.00118] | variant BETTER than baseline beyond noise |
| high_k40 | +0.00066 [+0.00010, +0.00122] | variant BETTER than baseline beyond noise |
| window_8y | -0.00788 [-0.00859, -0.00709] | variant WORSE than baseline beyond noise |
| window_4y | -0.01567 [-0.01679, -0.01443] | variant WORSE than baseline beyond noise |
| window_2y | -0.02595 [-0.02756, -0.02424] | variant WORSE than baseline beyond noise |

## Conclusion (ship-of-Theseus hypothesis)

- Variants beating full-history Elo beyond noise: ['high_k30', 'high_k40'].
- Variants clearly worse: ['low_k10', 'window_8y', 'window_4y', 'window_2y'].

The hard trailing-window variants test the literal hypothesis (discard matches older than N years). If they are no better — or worse — than full-history Elo, that supports keeping the full history: sparse international data needs the cross-linking, and Elo's K-factor already down-weights old results recursively.
