# Running Forecast Scorecard

Lower is better for RPS, home/draw/away log loss, and Brier score.
Market differences are `market - ours`, so negative means market scored better
on the paired subset and positive means our ledger forecasts scored better.

## Ledger Coverage

- Ledger predictions: 163
- Scored predictions: 153
- Pending predictions: 10

## Our Running Metrics

Bootstrap 95% CIs are reported once the metric has at least 30 finite observations.

| Metric | n | Mean |
| --- | ---: | --- |
| RPS | 153 | 0.1519 [0.1315, 0.1736] |
| H/D/A log loss | 153 | 0.8322 [0.7506, 0.9121] |
| Brier | 153 | 0.4774 [0.4198, 0.5332] |

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
