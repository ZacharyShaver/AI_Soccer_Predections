# Running Forecast Scorecard

Lower is better for RPS, home/draw/away log loss, and Brier score.
Market differences are `market - ours`, so negative means market scored better
on the paired subset and positive means our ledger forecasts scored better.

## Ledger Coverage

- Ledger predictions: 160
- Scored predictions: 149
- Pending predictions: 11

## Our Running Metrics

Bootstrap 95% CIs are reported once the metric has at least 30 finite observations.

| Metric | n | Mean |
| --- | ---: | --- |
| RPS | 149 | 0.1516 [0.1313, 0.1724] |
| H/D/A log loss | 149 | 0.8360 [0.7526, 0.9243] |
| Brier | 149 | 0.4802 [0.4214, 0.5433] |

## Market Comparison

No overlapping market data for scored ledger forecasts.

- Paired scored matches: 0

## Notable Hits

- ba6df313fca5: predicted home, actual home, RPS 0.0097, log loss 0.1442
- ba6df313fca5: predicted home, actual home, RPS 0.0097, log loss 0.1442
- ba6df313fca5: predicted home, actual home, RPS 0.0097, log loss 0.1442
- ba6df313fca5: predicted home, actual home, RPS 0.0097, log loss 0.1442
- ba6df313fca5: predicted home, actual home, RPS 0.0097, log loss 0.1442

## Notable Misses

- 3c751910c0af: predicted away, actual home, RPS 0.5498, log loss 1.7307
- 3c751910c0af: predicted away, actual home, RPS 0.5498, log loss 1.7307
- 3c751910c0af: predicted away, actual home, RPS 0.5498, log loss 1.7307
- c28f68293b31: predicted home, actual away, RPS 0.4993, log loss 1.5787
- c28f68293b31: predicted home, actual away, RPS 0.4993, log loss 1.5787

## Caveats

- Early in the tournament, resolved ledger forecasts may be zero or too few to support CIs.
- Market comparison only uses matches with both a resolved ledger forecast and market probabilities.
- Polymarket live snapshots are optional and are not assumed to join completed matches here.
