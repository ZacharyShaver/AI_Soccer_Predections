# Running Forecast Scorecard

Lower is better for RPS, home/draw/away log loss, and Brier score.
Market differences are `market - ours`, so negative means market scored better
on the paired subset and positive means our ledger forecasts scored better.

## Ledger Coverage

- Ledger predictions: 166
- Scored predictions: 160
- Pending predictions: 6

## Our Running Metrics

Bootstrap 95% CIs are reported once the metric has at least 30 finite observations.

| Metric | n | Mean |
| --- | ---: | --- |
| RPS | 160 | 0.1500 [0.1302, 0.1709] |
| H/D/A log loss | 160 | 0.8286 [0.7490, 0.9116] |
| Brier | 160 | 0.4746 [0.4173, 0.5335] |

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
