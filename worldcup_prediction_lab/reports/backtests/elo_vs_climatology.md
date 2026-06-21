# Elo vs Climatology Walk-Forward Backtest

Date run: 2026-06-21

## Config

- Data: `data/silver/martj42_matches.parquet`
- Completed silver matches available: 49441
- Training start: `1990-01-01`
- First prediction date: `2010-01-01`
- Final prediction date: `2026-06-10`
- Prediction window: 30 days
- Scored matches: 15817
- Windows: 201
- Bootstrap: 1000 resamples, 95% percentile CI, seed `20260622`
- Runs directory: `runs\backtests\m6_elo_vs_climatology`
- Cutoff note: final prediction date is 2026-06-10, so the in-progress 2026 World Cup beginning 2026-06-11 is excluded from this acceptance-gate evaluation.

## Per-Model Metrics

Lower is better for all metrics.

| Model | Metric | Mean | 95% CI | n |
| --- | --- | ---: | ---: | ---: |
| baseline_climatology | RPS | 0.228737 | [0.226966, 0.230469] | 15817 |
| baseline_climatology | H/D/A log loss | 1.054322 | [1.048637, 1.060153] | 15817 |
| baseline_climatology | Multiclass Brier | 0.635758 | [0.631604, 0.639570] | 15817 |
| elo_poisson_v1 | RPS | 0.177610 | [0.175201, 0.179760] | 15817 |
| elo_poisson_v1 | H/D/A log loss | 0.904707 | [0.895976, 0.914462] | 15817 |
| elo_poisson_v1 | Multiclass Brier | 0.531301 | [0.524979, 0.537132] | 15817 |

## Paired Acceptance Gate

The paired difference is `climatology - Elo` on the same match order. Positive means Elo had lower loss.

| Metric | Mean paired difference (climatology - Elo) | 95% CI | n | Verdict |
| --- | ---: | ---: | ---: | --- |
| RPS | 0.051127 | [0.048685, 0.053691] | 15817 | Elo better beyond bootstrap noise |
| H/D/A log loss | 0.149615 | [0.141609, 0.157850] | 15817 | Elo better beyond bootstrap noise |
| Multiclass Brier | 0.104457 | [0.098948, 0.109971] | 15817 | Elo better beyond bootstrap noise |

## Verdict

Elo beats climatology on RPS, H/D/A log loss, and multiclass Brier, and all three paired mean-difference bootstrap CIs exclude 0 in the favorable direction. M6 acceptance gate passes.

## Determinism Check

Re-ran both models on a smaller walk-forward slice (`2012-01-01` through `2012-03-31`) into two independent runs directories and compared sorted `(model_id, prediction_id, prediction_hash)` tuples.

- Hash rows compared: 344
- Result: passed

## Caveats

- This gate evaluates historical completed matches only; it deliberately excludes the 2026 World Cup matches already present in silver data.
- The comparison is outcome-only: RPS, H/D/A log loss, and multiclass Brier. Scoreline distributions exist for the models, but exact-score promotion needs a separate gate.
- No Elo hyperparameters were tuned for this run. The backtest uses the defaults already in `src/wc_predictor/models/elo.py`.
- In-tournament samples are too small and too dependent on draw/fixture context to justify promotion by themselves.
