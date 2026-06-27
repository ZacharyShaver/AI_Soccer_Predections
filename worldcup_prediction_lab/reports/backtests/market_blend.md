# Market route: Elo vs market vs blend

Generated: `2026-06-26T23:58:24Z`

Lower RPS is better. Blend = `lambda * market + (1 - lambda) * elo`.
Elo base is the tuned `elo_recalibrated` config (K=30, draw_base 0.33,
draw_scale 600, flat tournament weights). Paired CIs are bootstrap 95%
(1,000 resamples, seed 20260626); a diff is significant
when its CI excludes 0.

## Sample

- Usable joined result/market rows: 964
- Date range: 2014-06-12 to 2026-06-17

## Headline

- Tuned Elo RPS: **0.1574**
- Market RPS: **0.1496**
- Market minus Elo (positive = market better): +0.00778 [+0.00395, +0.01201]
- Best blend: **lambda = 1.00**, RPS **0.1496**

## Lambda sweep

| lambda | blend RPS | blend - Elo [95% CI] | blend - market [95% CI] |
| ---: | ---: | --- | --- |
| 0.00 | 0.1574 | +0.00000 [+0.00000, +0.00000] | -0.00778 [-0.01201, -0.00395] |
| 0.05 | 0.1567 | +0.00071 [+0.00050, +0.00094] | -0.00707 [-0.01105, -0.00346] |
| 0.10 | 0.1560 | +0.00138 [+0.00096, +0.00184] | -0.00640 [-0.01015, -0.00298] |
| 0.15 | 0.1553 | +0.00202 [+0.00140, +0.00271] | -0.00576 [-0.00931, -0.00255] |
| 0.20 | 0.1547 | +0.00262 [+0.00181, +0.00354] | -0.00516 [-0.00850, -0.00214] |
| 0.25 | 0.1542 | +0.00320 [+0.00218, +0.00434] | -0.00458 [-0.00771, -0.00174] |
| 0.30 | 0.1536 | +0.00374 [+0.00251, +0.00511] | -0.00405 [-0.00695, -0.00138] |
| 0.35 | 0.1531 | +0.00424 [+0.00282, +0.00583] | -0.00354 [-0.00621, -0.00105] |
| 0.40 | 0.1526 | +0.00471 [+0.00310, +0.00651] | -0.00307 [-0.00552, -0.00077] |
| 0.45 | 0.1522 | +0.00515 [+0.00334, +0.00717] | -0.00263 [-0.00486, -0.00053] |
| 0.50 | 0.1518 | +0.00556 [+0.00355, +0.00779] | -0.00222 [-0.00424, -0.00032] |
| 0.55 | 0.1514 | +0.00593 [+0.00374, +0.00837] | -0.00185 [-0.00367, -0.00015] |
| 0.60 | 0.1511 | +0.00627 [+0.00389, +0.00891] | -0.00151 [-0.00312, -0.00000] |
| 0.65 | 0.1508 | +0.00657 [+0.00400, +0.00942] | -0.00121 [-0.00260, +0.00011] |
| 0.70 | 0.1505 | +0.00685 [+0.00409, +0.00989] | -0.00093 [-0.00213, +0.00019] |
| 0.75 | 0.1503 | +0.00709 [+0.00414, +0.01033] | -0.00069 [-0.00168, +0.00024] |
| 0.80 | 0.1501 | +0.00729 [+0.00417, +0.01073] | -0.00049 [-0.00127, +0.00026] |
| 0.85 | 0.1499 | +0.00746 [+0.00416, +0.01112] | -0.00032 [-0.00090, +0.00025] |
| 0.90 | 0.1498 | +0.00760 [+0.00412, +0.01146] | -0.00018 [-0.00057, +0.00020] |
| 0.95 | 0.1497 | +0.00771 [+0.00404, +0.01176] | -0.00007 [-0.00027, +0.00011] |
| 1.00 | 0.1496 | +0.00778 [+0.00395, +0.01201] | +0.00000 [+0.00000, +0.00000] |

## Verdict

The de-vigged market significantly beats the tuned Elo (paired RPS CI excludes 0) and the optimal linear blend is essentially pure market (lambda>=0.95): blending Elo back in does not help. Use the market where it exists and fall back to the recalibrated Elo where it does not.

## Honesty caveats

- Sample is only the Football-Data odds rows that resolve to canonical teams and join martj42 results; extending the alias table would change it.
- The market embeds information Elo never sees (injuries, lineups, late money).
- 'Use the market where it exists' only covers matches that HAVE tradeable odds; most of the ~49k history does not, so Elo remains the backbone.
- Elo predictions are point-in-time by match date with all same-date results withheld (leak-free).
