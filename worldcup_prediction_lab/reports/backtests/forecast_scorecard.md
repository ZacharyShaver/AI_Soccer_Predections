# Running Forecast Scorecard

Lower is better for RPS, home/draw/away log loss, and Brier score.
Market differences are `market - ours`, so negative means market scored better
on the paired subset and positive means our ledger forecasts scored better.

## Ledger Coverage

- Ledger predictions: 165
- Scored predictions: 157
- Pending predictions: 8

## Our Running Metrics

Bootstrap 95% CIs are reported once the metric has at least 30 finite observations.

| Metric | n | Mean |
| --- | ---: | --- |
| RPS | 157 | 0.1504 [0.1309, 0.1711] |
| H/D/A log loss | 157 | 0.8334 [0.7516, 0.9167] |
| Brier | 157 | 0.4781 [0.4209, 0.5369] |

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
