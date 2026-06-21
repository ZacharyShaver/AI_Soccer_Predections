# Model Card: elo_poisson_v1

## Model

`elo_poisson_v1` is the plain sequential Elo model from `src/wc_predictor/models/elo.py`. It replays matches chronologically inside each walk-forward training window, updates team ratings after each completed match, and converts pre-match ratings to home/draw/away probabilities. The M5 scoreline layer maps Elo strength to a calibrated Poisson scoreline grid, but this acceptance gate evaluates outcome probabilities only.

## Configuration and Hyperparameters

- Training start: `1990-01-01`
- Prediction period: `2010-01-01` through `2026-06-10`
- Prediction window: 30 days
- Scored matches: 15817
- `base_rating=1500.0`
- `k_factor=20.0`
- `home_advantage=75.0`, suppressed on neutral matches unless a host-advantage hook says otherwise
- `draw_base_probability=0.27`
- `draw_rating_scale=400.0`
- `base_total_goals=2.65`
- `max_goals=10`
- `default_tournament_weight=1.0`
- Tournament weights: `{"AFC Asian Cup": 1.25, "African Cup of Nations": 1.25, "CONCACAF Championship": 1.2, "CONCACAF Nations League": 1.0, "Copa America": 1.35, "FIFA World Cup": 1.5, "FIFA World Cup qualification": 1.25, "Friendly": 0.75, "UEFA Euro": 1.35, "UEFA Nations League": 1.0}`

No hyperparameters were tuned during M6.

## Headline Metrics

| Metric | Mean | 95% CI | n |
| --- | ---: | ---: | ---: |
| RPS | 0.177610 | [0.175201, 0.179760] | 15817 |
| H/D/A log loss | 0.904707 | [0.895976, 0.914462] | 15817 |
| Multiclass Brier | 0.531301 | [0.524979, 0.537132] | 15817 |

## Caveats

- The edge over climatology is established on historical outcome metrics only; exact-score and market-calibration gates are separate future work.
- The model has no player, squad, travel, rest, injury, or betting-market features.
- The 2026 World Cup is in progress as of this project state. In-tournament samples are too small to justify promotion by themselves, so this card relies on the historical walk-forward gate.
