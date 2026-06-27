# Historical Elo vs Football-Data market backtest

Generated: `2026-06-26T23:58:29Z`

Lower is better for all metrics. The paired difference is `market - Elo`, so
negative means the market scored better and positive means Elo scored better.

## Evaluation set

- Total Football-Data odds rows: 1,098
- Odds rows with both canonical team ids: 1,098
- Usable joined result/market rows: 964
- Date range: 2014-06-12 to 2026-06-17
- As-listed joins: 945
- Reversed-orientation joins: 19

Top unmatched Football-Data names from null canonical ids:

- None among Football-Data odds rows.

## Metrics

Bootstrap 95% CIs use 1,000 resamples with seed 20260622.
Non-finite log-loss rows are excluded from log-loss CIs only.

| Model | n | RPS [95% CI] | H/D/A log loss [95% CI] | Brier [95% CI] |
| --- | ---: | --- | --- | --- |
| Football-Data market | 964 | 0.1496 [0.1406, 0.1589] | 0.7930 [0.7560, 0.8303] | 0.4631 [0.4372, 0.4895] |
| Elo | 964 | 0.1589 [0.1495, 0.1686] | 0.8353 [0.7956, 0.8773] | 0.4878 [0.4605, 0.5171] |

## Paired differences: market minus Elo

| Metric | mean diff [95% CI] | Interpretation |
| --- | --- | --- |
| RPS | -0.00928 [-0.01297, -0.00537] | negative = market better; positive = Elo better |
| H/D/A log loss | -0.04227 [-0.05713, -0.02749] | negative = market better; positive = Elo better |
| Brier | -0.02468 [-0.03406, -0.01572] | negative = market better; positive = Elo better |

## Verdict

Elo trails the Football-Data market on RPS: the paired CI is below 0, so market probabilities scored lower on the same matches.

## Honesty caveats

- The market benchmark only covers Football-Data rows that resolve to canonical teams and join to martj42 results.
- Football-Data odds include information Elo does not use, including injuries, lineups, venue context, and broad market wisdom.
- The Elo predictions are point-in-time by match date, not kickoff timestamp; all same-date results are withheld to avoid leakage.
- Alias gaps in qualifier teams can change the sample if Claude extends the alias table.
