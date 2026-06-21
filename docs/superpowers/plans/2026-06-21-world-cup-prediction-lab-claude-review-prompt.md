# Claude Review Prompt

Please review this implementation plan as a skeptical senior ML engineer and sports-forecasting systems architect:

`docs/superpowers/plans/2026-06-21-world-cup-prediction-lab.md`

The project goal is to build a local-first World Cup prediction lab that learns during the tournament. It should ingest historical football results, team ratings, fixtures, betting odds, Polymarket data, public forecast benchmarks, and compliant social/news aggregates. It should output calibrated probabilities for win/draw/loss, expected goals, and exact scorelines.

Please focus your review on practical risks rather than style.

Questions to answer:

1. Does the plan correctly separate the LLM's role from the forecasting model's role?
2. Does the live-learning loop avoid training on the model's own predictions as if they were labels?
3. Are the walk-forward backtesting and prediction-ledger rules enough to prevent time leakage?
4. Is the first milestone too large? If so, what should be deferred?
5. Is the data architecture realistic for a Windows local machine with a Ryzen 9 9950X, about 64 GB RAM, RTX 5070 with about 12 GB VRAM, and about 268 GB free disk?
6. Are the proposed sources useful and legally safe enough, especially Polymarket, betting odds, X, and Reddit?
7. Is the model ladder sensible: climatology -> Elo -> Poisson -> Dixon-Coles -> market-calibrated -> tabular ML -> optional neural?
8. Are there missing tests for probability normalization, calibration, data contracts, entity resolution, source freshness, or immutable predictions?
9. What parts are over-engineered for a first working version?
10. What would you change before implementation starts?

Please return:

- Top 5 risks, ordered by severity.
- Specific plan edits you recommend.
- A smaller "first 2 weeks" implementation scope.
- Any red flags that would make the project hard to evaluate honestly.
- Any source, model, or evaluation method you think should be added or removed.
