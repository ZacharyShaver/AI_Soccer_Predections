# Overlay scorecard (market-where-available vs results)

As of: 2026-06-27. Overlay predictions are scored against completed results by
joining on match date and canonical team pair (live fixture ids do not match
result ids, but team ids do). Lower RPS/log loss/Brier is better.

## Aggregate

- Ledger predictions: 32
- Scored (resolved): 20
- Mean RPS: 0.1457
- Mean log loss: 0.7145
- Mean Brier: 0.4073
- Accuracy: 0.7500

## By source

| Source | n | Mean RPS | Accuracy |
| --- | ---: | ---: | ---: |
| market | 20 | 0.1457 | 0.7500 |

## Caveats

- Small samples early in the tournament; treat single-digit n as indicative only.
- `market` rows used the de-vigged Polymarket price at snapshot time; `elo` rows used the recalibrated Elo fallback.
- Predictions are immutable ledger labels; scoring never mutates them.
