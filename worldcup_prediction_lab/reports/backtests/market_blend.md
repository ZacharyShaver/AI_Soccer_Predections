# Market route: Elo vs market vs blend

Generated: `2026-06-26T22:48:24Z`

Lower RPS is better. Blend = `lambda * market + (1 - lambda) * elo`.
Elo base is the tuned `elo_recalibrated` config (K=30, draw_base 0.33,
draw_scale 600, flat tournament weights). Paired CIs are bootstrap 95%
(1,000 resamples, seed 20260626); a diff is significant
when its CI excludes 0.

## Sample

- Usable joined result/market rows: 174
- Date range: 2014-06-12 to 2026-06-17

## Headline

- Tuned Elo RPS: **0.2155**
- Market RPS: **0.2016**
- Market minus Elo (positive = market better): +0.01395 [+0.00324, +0.02600]
- Best blend: **lambda = 1.00**, RPS **0.2016**

## Lambda sweep

| lambda | blend RPS | blend - Elo [95% CI] | blend - market [95% CI] |
| ---: | ---: | --- | --- |
| 0.00 | 0.2155 | +0.00000 [+0.00000, +0.00000] | -0.01395 [-0.02600, -0.00324] |
| 0.05 | 0.2145 | +0.00107 [+0.00053, +0.00172] | -0.01288 [-0.02428, -0.00268] |
| 0.10 | 0.2134 | +0.00211 [+0.00102, +0.00339] | -0.01184 [-0.02262, -0.00218] |
| 0.15 | 0.2124 | +0.00310 [+0.00147, +0.00501] | -0.01085 [-0.02099, -0.00174] |
| 0.20 | 0.2115 | +0.00406 [+0.00190, +0.00659] | -0.00989 [-0.01940, -0.00132] |
| 0.25 | 0.2106 | +0.00497 [+0.00229, +0.00813] | -0.00898 [-0.01786, -0.00094] |
| 0.30 | 0.2097 | +0.00585 [+0.00264, +0.00962] | -0.00810 [-0.01633, -0.00061] |
| 0.35 | 0.2088 | +0.00668 [+0.00296, +0.01108] | -0.00727 [-0.01486, -0.00031] |
| 0.40 | 0.2080 | +0.00748 [+0.00324, +0.01249] | -0.00647 [-0.01349, -0.00006] |
| 0.45 | 0.2073 | +0.00824 [+0.00344, +0.01385] | -0.00571 [-0.01213, +0.00016] |
| 0.50 | 0.2066 | +0.00895 [+0.00360, +0.01519] | -0.00500 [-0.01081, +0.00032] |
| 0.55 | 0.2059 | +0.00963 [+0.00372, +0.01648] | -0.00432 [-0.00953, +0.00045] |
| 0.60 | 0.2053 | +0.01027 [+0.00382, +0.01771] | -0.00368 [-0.00829, +0.00053] |
| 0.65 | 0.2047 | +0.01087 [+0.00388, +0.01889] | -0.00308 [-0.00709, +0.00063] |
| 0.70 | 0.2041 | +0.01143 [+0.00390, +0.02005] | -0.00252 [-0.00593, +0.00067] |
| 0.75 | 0.2036 | +0.01195 [+0.00388, +0.02113] | -0.00200 [-0.00484, +0.00064] |
| 0.80 | 0.2031 | +0.01243 [+0.00383, +0.02219] | -0.00152 [-0.00378, +0.00057] |
| 0.85 | 0.2027 | +0.01287 [+0.00381, +0.02321] | -0.00108 [-0.00276, +0.00048] |
| 0.90 | 0.2023 | +0.01327 [+0.00366, +0.02418] | -0.00068 [-0.00179, +0.00037] |
| 0.95 | 0.2019 | +0.01363 [+0.00347, +0.02511] | -0.00032 [-0.00088, +0.00021] |
| 1.00 | 0.2016 | +0.01395 [+0.00324, +0.02600] | +0.00000 [+0.00000, +0.00000] |

## Verdict

The de-vigged market significantly beats the tuned Elo (paired RPS CI excludes 0) and the optimal linear blend is essentially pure market (lambda>=0.95): blending Elo back in does not help. Use the market where it exists and fall back to the recalibrated Elo where it does not.

## Honesty caveats

- Sample is only the Football-Data odds rows that resolve to canonical teams and join martj42 results; extending the alias table would change it.
- The market embeds information Elo never sees (injuries, lineups, late money).
- 'Use the market where it exists' only covers matches that HAVE tradeable odds; most of the ~49k history does not, so Elo remains the backbone.
- Elo predictions are point-in-time by match date with all same-date results withheld (leak-free).
