# Historical Elo vs Football-Data market backtest

Generated: `2026-06-22T11:39:03Z`

Lower is better for all metrics. The paired difference is `market - Elo`, so
negative means the market scored better and positive means Elo scored better.

## Evaluation set

- Total Football-Data odds rows: 1,098
- Odds rows with both canonical team ids: 208
- Usable joined result/market rows: 174
- Date range: 2014-06-12 to 2026-06-17
- As-listed joins: 173
- Reversed-orientation joins: 1

Top unmatched Football-Data names from null canonical ids:

- Chile: 22
- Peru: 21
- Bolivia: 20
- Costa Rica: 20
- Indonesia: 20
- United Arab Emirates: 20
- Nigeria: 19
- Oman: 18
- Venezuela: 18
- Cameroon: 17
- Poland: 17
- Bahrain: 16
- China: 16
- Kuwait: 16
- Kyrgyzstan: 16
- Palestine: 16
- Denmark: 15
- North Korea: 15
- D.R. Congo: 14
- Serbia: 14

## Metrics

Bootstrap 95% CIs use 1,000 resamples with seed 20260622.
Non-finite log-loss rows are excluded from log-loss CIs only.

| Model | n | RPS [95% CI] | H/D/A log loss [95% CI] | Brier [95% CI] |
| --- | ---: | --- | --- | --- |
| Football-Data market | 174 | 0.2016 [0.1796, 0.2238] | 0.9958 [0.9154, 1.0784] | 0.5954 [0.5400, 0.6504] |
| Elo | 174 | 0.2168 [0.1952, 0.2393] | 1.0473 [0.9675, 1.1323] | 0.6303 [0.5727, 0.6903] |

## Paired differences: market minus Elo

| Metric | mean diff [95% CI] | Interpretation |
| --- | --- | --- |
| RPS | -0.01524 [-0.02568, -0.00411] | negative = market better; positive = Elo better |
| H/D/A log loss | -0.05152 [-0.08999, -0.01071] | negative = market better; positive = Elo better |
| Brier | -0.03483 [-0.05921, -0.01004] | negative = market better; positive = Elo better |

## Verdict

Elo trails the Football-Data market on RPS: the paired CI is below 0, so market probabilities scored lower on the same matches.

## Honesty caveats

- The market benchmark only covers Football-Data rows that resolve to canonical teams and join to martj42 results.
- Football-Data odds include information Elo does not use, including injuries, lineups, venue context, and broad market wisdom.
- The Elo predictions are point-in-time by match date, not kickoff timestamp; all same-date results are withheld to avoid leakage.
- Alias gaps in qualifier teams can change the sample if Claude extends the alias table.
