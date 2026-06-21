# Model Card: baseline_climatology

## Model

`baseline_climatology` is a team-agnostic global-rate baseline. It fits historical average home and away goals plus the empirical draw rate from the current walk-forward training window, then predicts every matchup from those global rates.

## Backtest Config

- Data: `data/silver/martj42_matches.parquet`
- Training start: `1990-01-01`
- Prediction period: `2010-01-01` through `2026-06-10`
- Prediction window: 30 days
- Scored matches: 15817
- Hyperparameters: `max_goals=10`; no team-strength features; no tournament-specific tuning.

## Headline Metrics

| Metric | Mean | 95% CI | n |
| --- | ---: | ---: | ---: |
| RPS | 0.228737 | [0.226966, 0.230469] | 15817 |
| H/D/A log loss | 1.054322 | [1.048637, 1.060153] | 15817 |
| Multiclass Brier | 0.635758 | [0.631604, 0.639570] | 15817 |

## Caveats

- This is the metric floor, not a competitive forecasting model.
- It ignores team strength, venue context, tournament importance, and player availability.
- In-tournament samples are too small to justify promoting or rejecting later models without historical walk-forward evidence.
