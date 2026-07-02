# Running Forecast Scorecard

Lower is better for RPS, home/draw/away log loss, and Brier score.
Market differences are `market - ours`, so negative means market scored better
on the paired subset and positive means our ledger forecasts scored better.

## Ledger Coverage

- Ledger predictions: 147
- Scored predictions: 127
- Pending predictions: 20

## Our Running Metrics

Bootstrap 95% CIs are reported once the metric has at least 30 finite observations.

| Metric | n | Mean |
| --- | ---: | --- |
| RPS | 127 | 0.1490 [0.1280, 0.1713] |
| H/D/A log loss | 127 | 0.8369 [0.7539, 0.9290] |
| Brier | 127 | 0.4794 [0.4208, 0.5441] |

## Market Comparison

No overlapping market data for scored ledger forecasts.

- Paired scored matches: 0

## Notable Hits

- 54a091654a78: predicted away, actual away, RPS 0.0133, log loss 0.1689
- 54a091654a78: predicted away, actual away, RPS 0.0133, log loss 0.1689
- 54a091654a78: predicted away, actual away, RPS 0.0133, log loss 0.1689
- 54a091654a78: predicted away, actual away, RPS 0.0133, log loss 0.1689
- 54a091654a78: predicted away, actual away, RPS 0.0154, log loss 0.1819

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
