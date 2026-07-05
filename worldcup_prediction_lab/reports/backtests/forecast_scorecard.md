# Running Forecast Scorecard

Lower is better for RPS, home/draw/away log loss, and Brier score.
Market differences are `market - ours`, so negative means market scored better
on the paired subset and positive means our ledger forecasts scored better.

## Ledger Coverage

- Ledger predictions: 151
- Scored predictions: 145
- Pending predictions: 6

## Our Running Metrics

Bootstrap 95% CIs are reported once the metric has at least 30 finite observations.

| Metric | n | Mean |
| --- | ---: | --- |
| RPS | 145 | 0.1420 [0.1230, 0.1619] |
| H/D/A log loss | 145 | 0.8155 [0.7373, 0.8971] |
| Brier | 145 | 0.4649 [0.4094, 0.5219] |

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
- dc7a375312a4: predicted away, actual home, RPS 0.3990, log loss 1.3129
- dc7a375312a4: predicted away, actual home, RPS 0.3990, log loss 1.3129

## Caveats

- Early in the tournament, resolved ledger forecasts may be zero or too few to support CIs.
- Market comparison only uses matches with both a resolved ledger forecast and market probabilities.
- Polymarket live snapshots are optional and are not assumed to join completed matches here.
