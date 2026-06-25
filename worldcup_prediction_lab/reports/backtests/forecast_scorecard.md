# Running Forecast Scorecard

Lower is better for RPS, home/draw/away log loss, and Brier score.
Market differences are `market - ours`, so negative means market scored better
on the paired subset and positive means our ledger forecasts scored better.

## Ledger Coverage

- Ledger predictions: 114
- Scored predictions: 0
- Pending predictions: 114

## Current Status

- No ledger forecasts have resolved yet.

## Our Running Metrics

Bootstrap 95% CIs are reported once the metric has at least 30 finite observations.

| Metric | n | Mean |
| --- | ---: | --- |
| RPS | 0 | n/a |
| H/D/A log loss | 0 | n/a |
| Brier | 0 | n/a |

## Market Comparison

No scored ledger forecasts are available for market comparison.

- Paired scored matches: 0

## Notable Hits

- None yet.

## Notable Misses

- None yet.

## Caveats

- Early in the tournament, resolved ledger forecasts may be zero or too few to support CIs.
- Market comparison only uses matches with both a resolved ledger forecast and market probabilities.
- Polymarket live snapshots are optional and are not assumed to join completed matches here.
