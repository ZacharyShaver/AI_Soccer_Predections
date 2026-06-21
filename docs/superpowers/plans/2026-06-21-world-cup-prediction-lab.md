# World Cup Prediction Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Revision note (2026-06-21, post-review):** This plan was revised after reviewing three near-identical public projects (see "Closest comparators already built"). Key changes: (1) reframed the model ladder around the finding that calibrated Elo is ~90% of achievable signal on sparse international data and fancier rungs must *beat Elo* or be recorded as negative results; (2) marked FiveThirtyEight SPI as a frozen pre-2023 dataset (removed from live sources); (3) added an explicit external-API credit budget (The Odds API free tier is ~500 credits/month); (4) added a "Role Of The LLM" section (no LLM in the probability path); (5) made the prediction ledger deterministic (canonical JSON + 6-decimal rounding + SHA-256 hash) and Monte Carlo seeded; (6) added the 2026 48-team / best-third-placed bracket tiebreaker as an explicit tested requirement; (7) added calibration-regression and no-vig tests; (8) added a statistical-honesty gate (small sample sizes can't justify promotion); (9) shrank the first milestone to an Elo-first vertical slice.

**Goal:** Build a local-first World Cup forecasting lab that ingests curated football data, prediction-market data, betting odds, and compliant social/news aggregates, then produces live-updating calibrated probability forecasts for match winner, draw, exact scoreline, expected goals, and tournament simulations.

**Architecture:** Use a layered data lake (`raw -> bronze -> silver -> gold`) plus reproducible model runs. Start with interpretable statistical baselines, add market-calibrated and ML models only after walk-forward evaluation proves the data pipeline is trustworthy, and keep an immutable prediction ledger so the system learns from its own forecast errors without training on its own predictions as labels.

**Tech Stack:** Windows PowerShell, Python 3.11.15, `uv` 0.11.17, DuckDB, Parquet, Polars/Pandas, scikit-learn, statsmodels/scipy, LightGBM or CatBoost after baseline, PyTorch for optional small neural models, MLflow or local JSONL run registry, Great Expectations or pandera for data contracts, Streamlit or FastAPI + simple dashboard later.

---

## Executive Summary

This project should be built as a forecasting lab, not a one-shot "accurate score picker." Exact soccer scores are low-probability events. The correct output is a full probability distribution over scorelines, with a top scoreline shown as the headline prediction. A good prediction might say `Argentina 1-0 France: 11%`, `1-1: 10%`, `2-1: 9%`, not pretend a single exact score is certain.

The highest-value first version is:

1. Ingest historical international matches and World Cup fixture data.
2. Build team strength features from results, Elo-like ratings, venue, tournament importance, recency, and travel/rest.
3. Train a Poisson expected-goals baseline and turn it into scoreline probabilities.
4. Add a prediction ledger that records every forecast before kickoff.
5. After each match, append the result, score the old forecast, update ratings/features, and retrain or recalibrate.
6. Add market signals from Polymarket, betting odds, and public forecast sources as features.
7. Add social/news only as compliant timestamped aggregates, not raw user-content training text.

The local computer is strong enough for serious tabular modeling and moderate neural experiments. It is not storage-rich enough to hoard unlimited raw API snapshots forever without retention rules.

---

## Local Machine Constraints

Collected on 2026-06-21 from this Windows machine.

| Component | Observed spec | Planning implication |
| --- | --- | --- |
| System | Micro-Star International Co., Ltd. MS-7E12 | Desktop workstation, suitable for local services and scheduled jobs. |
| CPU | AMD Ryzen 9 9950X, 16 cores, 32 logical processors | Excellent for DuckDB, feature generation, cross-validation, simulation, and CPU-based ML. |
| RAM | 66,144,620,544 bytes, roughly 61.6 GiB usable; four 16 GiB DIMMs at 3600 MHz | Enough for large Parquet/DuckDB workflows, local model grids, and in-memory feature sets. |
| GPU | NVIDIA GeForce RTX 5070, 12,227 MiB VRAM from `nvidia-smi`; driver 610.47 | Good for small PyTorch MLPs, embeddings, and transformer inference on short text; avoid large deep models or LLM fine-tuning locally. |
| Integrated GPU | AMD Radeon Graphics, 2 GiB WMI-reported adapter RAM | Ignore for model training. |
| Disk | Samsung SSD 990 EVO Plus 2TB | Fast local store, good for Parquet and DuckDB. |
| Free space | C: about 268 GB free | Use strict data retention. Do not keep every raw market/social snapshot indefinitely. |
| Python | Python 3.11.15 | Use Python 3.11 environment. |
| Package manager | `uv` 0.11.17 | Use `uv` for reproducible setup and fast dependency sync. |
| Git | 2.49.0.windows.1 | Use frequent commits after each task. |

Machine-specific decisions:

- Keep canonical analytical data in DuckDB + partitioned Parquet, not a heavyweight database service at first.
- Store raw snapshots compressed and expire low-value market/social snapshots after they are aggregated.
- Prefer CPU-first models for the champion production model until GPU experiments show measurable walk-forward improvement.
- Use the GPU for optional small neural team-embedding models, short text classifiers, or local sentiment experiments.
- Use batch retraining after each match and light online updates for Elo/calibration, not always-on deep training.

---

## Research Findings And Lessons Learned

### Public data and GitHub sources reviewed

- [FiveThirtyEight soccer SPI data](https://github.com/fivethirtyeight/data/tree/master/soccer-spi): match-by-match ratings, win/draw/loss probabilities, projected scores, actual scores, xG, non-shot xG, and international SPI files. **WARNING: this dataset is frozen.** FiveThirtyEight stopped publishing SPI in 2023 after Nate Silver left, and the GitHub data has not updated since. SPI is therefore usable ONLY as a historical-era benchmark (pre-2023 backtests), never as a live 2026 feature or live benchmark. Do not build any live-loop dependency on it.
- [martj42/international_results](https://github.com/martj42/international_results): broad men's international results dataset with `results.csv`, `shootouts.csv`, `goalscorers.csv`, and former names. The GitHub page reports 49,398 international results through 2024, so the pipeline must verify freshness before trusting it for 2026 work.
- [openfootball/worldcup](https://github.com/openfootball/worldcup): public-domain World Cup and qualifier data, including Canada/USA/Mexico 2026 fixtures in Football.TXT format.
- [StatsBomb open-data](https://github.com/statsbomb/open-data): free event, lineup, match, and selected 360 JSON data. It requires attribution when publishing research or analysis.
- [Football-Data.co.uk](https://www.football-data.co.uk/): free historical results and odds in Excel/CSV format for quantitative analysis.
- GitHub repository searches for `soccer prediction poisson python`, `world cup prediction python football`, `football betting odds prediction python`, and `dixon coles football python` found many small repos and student projects. The lesson is to borrow ideas, not architecture: most projects are notebooks, thin scripts, or one-off apps without serious leakage control, immutable prediction logs, data contracts, or live evaluation.

### Closest comparators already built (review them before coding)

Three public projects are almost exactly this idea and have already published results. Their lessons are load-bearing for this plan:

- [Hicruben/world-cup-2026-prediction-model](https://github.com/Hicruben/world-cup-2026-prediction-model): the exact intended stack (Elo + Dixon-Coles bivariate Poisson + 50k-iteration Monte Carlo). It deliberately trained on only **913 recent matches (Oct 2023 - Jun 2026), not a 49k-row historical corpus**, because old international results carry little signal for current squads. Realistic published metrics to benchmark against: **RPS 0.175, ~62% result accuracy, 2.3% expected calibration error.** Explicit caveat: "no claim to beat the betting market."
- [hjjbh1314/worldcup-predictor](https://github.com/hjjbh1314/worldcup-predictor): leakage-free international Elo predictor (~60% accuracy, RPS 0.171). Most important finding for our model ladder: **gradient-boosting with recent form, fatigue, and congestion features added "essentially nothing" beyond plain Elo; permutation importance was dominated entirely by the Elo rating gap.** Also: "international football data is sparse, making per-team attack/defence metrics unreliable compared to pooled ratings."
- [tuantqse90/epl-prediction-lab](https://github.com/tuantqse90/epl-prediction-lab): uses our exact pre-kickoff ledger idea ("a prediction without a pre-kickoff hash is marketing, not a forecast"). Two transferable details: (1) deterministic verifiable hashes require **canonical JSON + probabilities rounded to 6 decimals + fixed RNG seeds**; (2) even with far more data than international football, it beats bookmakers by ~+2pp over 30 days but **loses to them all-time** - a realistic ceiling on "beat the market" ambitions.

**Synthesis used throughout this plan:** for international football, Elo captures roughly 90% of the achievable signal. Dixon-Coles adds a small real correction on low scores. Everything above that (attack/defense Poisson, tabular ML, neural embeddings, social/news) carries a strong prior of adding nothing on sparse international data. Those rungs stay in the ladder so we can *prove the negative*, but none is assumed to be an improvement, and each must beat a plain Elo champion to be promoted.

### Market and API sources reviewed

- [Polymarket market data docs](https://docs.polymarket.com/market-data/overview): public REST market data does not require an API key. It exposes events, markets, search, prices, order books, historical prices, midpoints, spreads, open interest, holders, and trades. Polymarket docs state `outcomePrices` map to implied probabilities.
- [Polymarket trading overview](https://docs.polymarket.com/trading/overview): trading APIs require wallets and signing. This project should ingest public market data only at first and should not place trades.
- [The Odds API v4 docs](https://the-odds-api.com/liveapi/guides/v4/): provides current odds and paid historical odds snapshots. Historical odds are available from 2020-06-06, with 10-minute snapshots initially and 5-minute snapshots from September 2022. This is useful for line movement and market-implied probability. **Quota warning:** the free tier is ~500 credits/month (~16 requests/day), and a single request costs 1 credit per region per market - multi-region/multi-market calls cost several credits each. The match-day "every 15 minutes" loop would exhaust a month's quota in hours. Any odds ingestion MUST enforce an explicit credit budget (see Live Tournament Operations) and degrade gracefully when exhausted.
- **Polymarket coverage caveat:** outright-winner markets are liquid, but per-match, per-group, and scoreline proposition markets for soccer are frequently thin or absent. Verify a market actually exists and has non-trivial liquidity per fixture before building features that depend on it; treat missing markets as a normal, expected case, not an error.
- [X Developer Platform](https://docs.x.com/overview): provides access to posts, users, trends, and more using pay-per-use or enterprise access. Treat this as optional because cost and terms can change.
- [Reddit Data API Terms](https://redditinc.com/policies/data-api-terms): Reddit user content cannot be used to train a machine learning or AI model without express permission from rightsholders. For this project, Reddit should be limited to compliant metadata/aggregate signals only unless rights are secured.

### Modeling and academic lessons reviewed

- Poisson score models remain a sensible first baseline for soccer because goals are count events and exact scoreline probabilities can be derived from expected goals.
- Dixon-Coles style corrections are useful because independent Poisson models mis-handle low-score correlation, especially `0-0`, `1-0`, `0-1`, and `1-1`.
- Tournament forecasts benefit from Monte Carlo simulation because match-level uncertainty compounds through group standings and knockout brackets.
- Research comparing machine learning and Poisson approaches reports that model family alone often has modest impact compared with feature quality, backtesting design, and leakage control.
- Sports-betting ML research strongly suggests calibration matters more than raw accuracy when the output is a probability used for decisions.
- Recent market-calibrated football forecasting research suggests betting-exchange prices and market calibration can dominate predictive accuracy, especially for in-play forecasts.

Practical lesson:

The project should never measure success only by "did we guess the exact score." It should track exact-score hit rate, but the main scorecard must use log loss, Brier score, calibration, expected-goals error, winner/draw probabilities, and comparison against market baselines.

---

## Core Product Definition

The system predicts upcoming World Cup matches and learns during the tournament.

For each match, it should produce:

- Match metadata: fixture id, kickoff time, venue, stage, home/away/neutral framing.
- Win/draw/loss probabilities.
- Expected goals for each team.
- Scoreline probability matrix from `0-0` through at least `6-6`, with tail mass tracked.
- Most likely exact score.
- Probability of over/under goal totals.
- Confidence and uncertainty bands.
- Market comparison: model probability vs Polymarket, bookmaker odds, SPI, or other benchmark.
- Explanation fields: top drivers such as Elo gap, attack/defense strength, injuries, market movement, recent form, rest, and venue.
- Immutable prediction id and model version.

After the match finishes, it should record:

- Final score after regulation/extra time as separate fields.
- Penalty shootout result if applicable.
- Winner according to the market being scored.
- Prediction metrics for every model version that forecasted the match.
- Error residuals used for calibration updates.
- Data sources available at prediction time and data sources added after the match.

---

## Role Of The LLM

The forecasting system contains **no LLM in the probability path.** All probabilities come from statistical/ML models (Elo, Poisson, Dixon-Coles, calibration). The LLM's only roles are developer-facing: generating and editing code for this repo, and optionally drafting human-readable prose inside model cards and reports from already-computed numbers. An LLM must never produce, adjust, or "sanity-edit" a probability, expected-goals value, or scoreline. This keeps the forecaster auditable and reproducible and avoids smuggling untraceable judgment into calibrated outputs.

## Non-Goals For The First Build

- No automated betting or wallet-connected trading.
- No scraping that violates site terms.
- No training directly on raw Reddit user content.
- No large LLM fine-tuning.
- No live in-play model until pre-match forecasting is reliable.
- No "single best model" commitment before walk-forward benchmarks.
- No UI dashboard before the data/model/evaluation loop is trustworthy.

---

## Data Strategy

### Layered storage

Use this structure under `worldcup_prediction_lab/`:

```text
worldcup_prediction_lab/
  data/
    raw/
      source=<source_name>/ingested_at=<YYYY-MM-DDTHH-mm-ssZ>/
    bronze/
      source=<source_name>/
    silver/
      entity=<entity_name>/
    gold/
      dataset=<dataset_name>/
  notebooks/
    exploration/
  reports/
    data_quality/
    model_cards/
    backtests/
  runs/
    predictions/
    evaluations/
    models/
  src/
    wc_predictor/
      config/
      data/
      features/
      models/
      evaluation/
      simulation/
      live/
      cli/
  tests/
    data/
    features/
    models/
    evaluation/
    live/
```

Data layers:

- `raw`: exact snapshots as received, compressed where possible, with source URL/API endpoint, request timestamp, license note, and response hash.
- `bronze`: parsed source-shaped tables with stable column names and source-specific identifiers.
- `silver`: normalized entities across sources: teams, matches, fixtures, venues, tournaments, markets, odds snapshots, ratings, player availability, social aggregates.
- `gold`: model-ready point-in-time datasets with leakage checks.

### Source priority ladder

Phase 1 sources:

1. International results from `martj42/international_results` (verify freshness on every ingest; recency-weight heavily - prefer the last ~3 years, per the Hicruben comparator).
2. World Cup 2026 fixtures from OpenFootball and official schedule cross-checks.
3. Football-Data odds where it covers relevant competitions and historical odds.

FiveThirtyEight SPI is intentionally NOT a Phase 1 source. It is a frozen pre-2023 dataset (see Research Findings) usable only for historical-era backtest benchmarking, never as a live 2026 feature or benchmark.

Phase 2 sources:

1. Polymarket public market data for World Cup outright, match, group, and proposition markets.
2. The Odds API current odds and historical odds if an API key/paid access is available.
3. World Football Elo or equivalent rating snapshots if a legally usable feed is selected.
4. FIFA rankings snapshots if source licensing is acceptable.

Phase 3 sources:

1. StatsBomb open data for event/lineup features from past World Cups and selected competitions.
2. News/injury APIs or curated RSS feeds.
3. X posts/trends through official API, aggregated into counts/sentiment only.
4. Reddit aggregates only when compliant with the Data API Terms and not used as raw training text.

### Data contracts

Every ingested source needs:

- A source registry entry.
- License and terms note.
- Refresh schedule.
- Required fields.
- Allowed null fields.
- Primary key rules.
- Point-in-time availability rules.
- Entity resolution rules.
- Quality checks.

Example source registry fields:

```yaml
source_id: polymarket_gamma_events
display_name: Polymarket Gamma Events
source_type: market_data_api
access_method: public_rest
license_or_terms_url: https://docs.polymarket.com/market-data/overview
allowed_use: public market-data features for research predictions
raw_retention_days: 30
bronze_retention_days: 3650
refresh_cadence: 15m during tournament, 6h before tournament
requires_secret: false
point_in_time_safe: true
primary_keys:
  - event_id
  - market_id
required_fields:
  - id
  - question
  - outcomes
  - outcomePrices
  - endDate
```

### Entity resolution

Create a team alias system early. Soccer data sources disagree on country/team names.

Examples:

- `United States`, `USA`, `USMNT`, `U.S.A.`
- `England`, `ENG`
- `Czech Republic`, `Czechia`
- `DR Congo`, `Congo DR`, `Democratic Republic of the Congo`
- `Ivory Coast`, `Cote d'Ivoire`

The alias table must include:

- `canonical_team_id`
- `canonical_name`
- `source_name`
- `source_team_name`
- `valid_from`
- `valid_to`
- `confidence`
- `manual_review_status`

---

## Modeling Strategy

### Model ladder

Do not start with the fanciest model. Build a ladder where each model must beat previous baselines in walk-forward tests.

**Prior from comparators (treat as the default expectation):** on sparse international data, a calibrated Elo model is expected to be the champion, and rungs 3 and above are expected to add little or nothing. That is not a reason to skip them - it is a reason to build them as *falsification experiments*. Every rung from `attack_defense_poisson_v1` onward must beat a plain calibrated-Elo champion (not just climatology) in walk-forward tests to be promoted; a rung that fails to beat Elo is a published negative result, recorded in a model card, not a failure of the project. Budget time accordingly: do not over-invest in rungs 6-8 before rungs 1-2 have a trustworthy backtest number.

1. `baseline_climatology`
   - Uses global historical home/neutral goal rates and draw rates.
   - Purpose: sanity check and metric baseline.

2. `elo_poisson_v1`
   - Maintains Elo-like team ratings.
   - Converts rating difference, venue, recency, and tournament importance into expected goals.
   - Converts expected goals into scoreline probabilities.

3. `attack_defense_poisson_v1`
   - Learns team attack and defense strengths.
   - Includes venue, neutral-site, host, recency, match importance, confederation, and rest features.

4. `dixon_coles_v1`
   - Adds low-score correlation correction.
   - Evaluates improvement specifically on `0-0`, `1-0`, `0-1`, `1-1`, draw probability, and scoreline log loss.

5. `market_calibrated_poisson_v1`
   - Uses bookmaker/Polymarket implied probabilities as calibration targets or features.
   - Separates "model-only" and "market-aware" variants so the project can learn how much markets add.

6. `tabular_ml_xg_v1`
   - Uses LightGBM/CatBoost/sklearn to predict expected goals or discrete outcome probabilities.
   - Trained only after point-in-time feature generation is proven.

7. `ensemble_calibrated_v1`
   - Blends statistical, market, and ML models.
   - Applies calibration using time-split validation.

8. `neural_team_embedding_v1`
   - Optional GPU experiment using small team/tournament embeddings and tabular features.
   - Must beat calibrated tabular models in walk-forward tests before being used as champion.

### Exact scoreline generation

Every model should expose:

```python
class ScorelineDistribution:
    match_id: str
    model_id: str
    generated_at_utc: str
    max_goals: int
    home_expected_goals: float
    away_expected_goals: float
    probabilities: dict[str, float]
    tail_probability: float
```

Scoreline probabilities should support:

- Top exact score.
- Top 5 scorelines.
- Draw probability from sum of diagonal cells.
- Home win probability from lower triangle.
- Away win probability from upper triangle.
- Over/under goal markets.
- Both teams to score.

### Learning from its own predictions

The system should learn from predictions in three ways:

1. Immutable forecast ledger
   - Every prediction is stored before kickoff with model version, features, source timestamps, and generated probabilities.
   - Forecast records are never overwritten.

2. Post-match scoring
   - After the result arrives, compare actual outcome against the stored probability distribution.
   - Compute log loss, Brier score, ranked probability score, exact-score hit, top-3-score hit, expected-goals error, calibration bins, and market-relative error.

3. Online adaptation
   - Update Elo and form features immediately after each match (Elo is designed for sequential single-match updates and is safe here).
   - Do NOT refit calibration on tournament-only samples. A World Cup is ~104 matches; reliable calibration needs hundreds of samples, so recalibrating on a handful of match-days chases noise. Calibration layers are fit on the full historical walk-forward set and only *refreshed* in-tournament once a hard minimum sample floor is met (set an explicit floor, e.g. >=200 scored matches in the calibration window); otherwise keep the pre-tournament calibration frozen.
   - Retrain statistical and tabular models on a schedule, not after every match.
   - Promote candidate models only after they beat champion models on a locked walk-forward validation window, with the statistical-honesty note from Acceptance Gates applied (in-tournament sample sizes are too small to justify promotion on their own).

Important guardrail:

Predictions are not labels. The model must not train on its predicted scores as if they were true. It should train on actual results and use its own prediction errors as feedback for calibration, recency weighting, and model selection.

---

## Evaluation Strategy

### Core metrics

Track these for every prediction and aggregated window:

- Exact score hit rate.
- Top-3 exact score hit rate.
- Winner/draw/loser accuracy.
- Multiclass log loss for `home/draw/away`.
- Brier score for `home/draw/away`.
- Scoreline negative log likelihood.
- Ranked probability score for goal difference.
- Expected-goals MAE.
- Calibration by probability bin.
- Market comparison: model log loss vs implied market log loss.
- Closing-line comparison when odds are available.

### Backtesting design

Use walk-forward splits only:

```text
train through date T
predict matches in next window
lock predictions
score after results
advance T
repeat
```

Leakage rules:

- A feature may only use data available before prediction timestamp.
- Closing odds are not allowed for pre-kickoff predictions made before closing time.
- Final lineups are only allowed if prediction timestamp is after lineup release.
- Post-match xG is never allowed as a pre-match feature for that same match.
- Tournament advancement simulations must only use known bracket state at prediction time.

### Acceptance gates

Before a model can become champion:

- It must beat both `baseline_climatology` and a plain calibrated Elo model on RPS and log loss across a full walk-forward historical period. Beating only climatology is not sufficient - Elo is the bar that matters.
- It must not be worse than the current champion by more than 2% on calibration-sensitive metrics.
- It must produce valid probabilities that sum to 1 within tolerance.
- It must generate reproducible predictions from saved artifacts (deterministic: fixed RNG seeds, canonical serialization, 6-decimal rounding).
- It must pass data leakage tests.

Statistical-honesty note: because the relevant event count is small (few World Cups, mostly noisy friendlies), report confidence intervals / number of matches alongside every gate metric. A 1-2% edge over ~100 matches is inside the noise and is NOT sufficient evidence to promote.

---

## Live Tournament Operations

### Daily loop before tournament

Run every 6 hours:

1. Refresh fixtures.
2. Refresh team ratings.
3. Refresh market data.
4. Refresh odds.
5. Refresh curated news/injury feeds.
6. Build gold features for future matches.
7. Generate predictions for all upcoming matches.
8. Write prediction ledger entries.
9. Publish report.

### API credit budget (enforce before scheduling any refresh)

External market/odds APIs are quota-limited (The Odds API free tier ~500 credits/month, ~16 requests/day; credits are consumed per region per market). The refresh cadences below are aspirational and will exceed a free tier. Before running the live loop:

- Configure a per-source monthly credit budget in `live_schedule.yaml`.
- The runner must track spend, refuse calls once the budget is exhausted, and log the skip rather than failing.
- Concentrate paid refreshes on the highest-value windows (final hours before kickoff of matches actually being forecast), not blanket polling.
- Polymarket public data has no key/credit cost but uneven coverage; prefer it where markets exist.

### Match-day loop

Run more frequently (subject to the credit budget above):

- 24h to 3h before kickoff: hourly refresh.
- 3h to 75m before kickoff: every 15 minutes for market/odds/news, only when budget allows.
- After official lineups: one lineup-aware forecast.
- At kickoff: freeze pre-match prediction set.
- After final whistle: ingest result, score predictions, update ratings, retrain/recalibrate as configured.

### Champion/candidate model system

Use two model tracks:

- `champion`: the model whose predictions are shown as primary.
- `candidate`: experimental model being scored live but not trusted as primary.

Promotion rule:

- Candidate must beat champion across a pre-defined window and pass calibration checks.
- Promotion creates a model card and Git commit.
- Old champion remains available for comparison.

---

## Repository And File Plan

### Files and folders to create

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `worldcup_prediction_lab/data/.gitkeep`
- Create: `worldcup_prediction_lab/data/raw/.gitkeep`
- Create: `worldcup_prediction_lab/data/bronze/.gitkeep`
- Create: `worldcup_prediction_lab/data/silver/.gitkeep`
- Create: `worldcup_prediction_lab/data/gold/.gitkeep`
- Create: `worldcup_prediction_lab/notebooks/exploration/.gitkeep`
- Create: `worldcup_prediction_lab/reports/data_quality/.gitkeep`
- Create: `worldcup_prediction_lab/reports/model_cards/.gitkeep`
- Create: `worldcup_prediction_lab/reports/backtests/.gitkeep`
- Create: `worldcup_prediction_lab/runs/predictions/.gitkeep`
- Create: `worldcup_prediction_lab/runs/evaluations/.gitkeep`
- Create: `worldcup_prediction_lab/runs/models/.gitkeep`
- Create: `worldcup_prediction_lab/config/sources.yaml`
- Create: `worldcup_prediction_lab/config/model_registry.yaml`
- Create: `worldcup_prediction_lab/config/live_schedule.yaml`
- Create: `worldcup_prediction_lab/src/wc_predictor/__init__.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/config/settings.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/source_registry.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_international_results.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_openfootball_worldcup.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_spi.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_polymarket.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_odds.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/team_aliases.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/features/team_strength.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/features/match_features.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/features/market_features.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/base.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/baseline.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/elo.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/poisson.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/dixon_coles.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/calibration.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/evaluation/metrics.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/evaluation/backtest.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/evaluation/ledger.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/simulation/tournament.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/live/runner.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/cli/main.py`
- Create: `worldcup_prediction_lab/tests/conftest.py`
- Create tests matching each module above.

### Responsibility map

- `config/settings.py`: paths, environment variables, runtime settings.
- `data/source_registry.py`: load and validate source registry definitions.
- `data/ingest_*.py`: one source per file; raw download, bronze parse, manifest write.
- `data/team_aliases.py`: canonical team ID resolution.
- `features/*.py`: deterministic point-in-time features.
- `models/base.py`: shared interfaces and prediction schema.
- `models/baseline.py`: climatology model.
- `models/elo.py`: Elo update logic and rating features.
- `models/poisson.py`: independent Poisson expected-goals model.
- `models/dixon_coles.py`: low-score correction model.
- `models/calibration.py`: probability calibration utilities.
- `evaluation/metrics.py`: exact metrics used everywhere.
- `evaluation/backtest.py`: walk-forward orchestration.
- `evaluation/ledger.py`: immutable predictions and post-match scoring.
- `simulation/tournament.py`: group/knockout Monte Carlo simulation.
- `live/runner.py`: scheduled update flow.
- `cli/main.py`: command line entrypoint.

---

## Implementation Tasks

### Task 1: Project Skeleton And Environment

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: folder tree listed in "Repository And File Plan"

- [ ] **Step 1: Create dependency manifest**

Create `pyproject.toml` with:

```toml
[project]
name = "worldcup-prediction-lab"
version = "0.1.0"
description = "Local-first World Cup forecasting lab with live prediction evaluation."
requires-python = ">=3.11,<3.12"
dependencies = [
  "duckdb>=1.0.0",
  "polars>=1.0.0",
  "pandas>=2.2.0",
  "pyarrow>=16.0.0",
  "numpy>=1.26.0",
  "scipy>=1.12.0",
  "scikit-learn>=1.4.0",
  "statsmodels>=0.14.0",
  "pydantic>=2.7.0",
  "pandera>=0.19.0",
  "httpx>=0.27.0",
  "pyyaml>=6.0.0",
  "typer>=0.12.0",
  "rich>=13.7.0",
  "joblib>=1.4.0",
  "plotly>=5.22.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "pytest-cov>=5.0.0",
  "ruff>=0.5.0",
  "mypy>=1.10.0"
]
gpu = [
  "torch>=2.3.0"
]
dashboard = [
  "streamlit>=1.36.0"
]
boosting = [
  "lightgbm>=4.3.0",
  "catboost>=1.2.5"
]

[project.scripts]
wc-predictor = "wc_predictor.cli.main:app"

[tool.uv]
package = true

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["worldcup_prediction_lab/tests"]
pythonpath = ["worldcup_prediction_lab/src"]
```

- [ ] **Step 2: Add `.gitignore`**

Create `.gitignore` with:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
.env

worldcup_prediction_lab/data/raw/**
worldcup_prediction_lab/data/bronze/**
worldcup_prediction_lab/data/silver/**
worldcup_prediction_lab/data/gold/**
worldcup_prediction_lab/runs/models/**
worldcup_prediction_lab/runs/predictions/**
worldcup_prediction_lab/runs/evaluations/**

!worldcup_prediction_lab/data/**/.gitkeep
!worldcup_prediction_lab/runs/**/.gitkeep
```

- [ ] **Step 3: Add `.env.example`**

Create `.env.example` with:

```text
WC_PREDICTOR_DATA_DIR=worldcup_prediction_lab/data
WC_PREDICTOR_RUNS_DIR=worldcup_prediction_lab/runs
THE_ODDS_API_KEY=
X_API_BEARER_TOKEN=
NEWS_API_KEY=
```

- [ ] **Step 4: Sync environment**

Run:

```powershell
uv sync --extra dev
```

Expected:

```text
Resolved dependencies and created/updated .venv
```

- [ ] **Step 5: Commit skeleton**

Run:

```powershell
git add pyproject.toml .gitignore .env.example README.md worldcup_prediction_lab
git commit -m "chore: scaffold world cup prediction lab"
```

### Task 2: Source Registry And Data Contracts

**Files:**
- Create: `worldcup_prediction_lab/config/sources.yaml`
- Create: `worldcup_prediction_lab/src/wc_predictor/config/settings.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/source_registry.py`
- Test: `worldcup_prediction_lab/tests/data/test_source_registry.py`

- [ ] **Step 1: Write source registry tests**

Test required fields, retention days, and source IDs:

```python
from wc_predictor.data.source_registry import load_sources


def test_sources_have_required_fields():
    sources = load_sources("worldcup_prediction_lab/config/sources.yaml")
    assert "international_results" in sources
    assert "polymarket_market_data" in sources
    for source in sources.values():
        assert source.source_id
        assert source.display_name
        assert source.access_method
        assert source.license_or_terms_url
        assert source.raw_retention_days >= 0
        assert len(source.required_fields) > 0
```

- [ ] **Step 2: Create settings module**

Implement a small Pydantic settings object with `data_dir`, `runs_dir`, and optional API keys loaded from environment variables.

- [ ] **Step 3: Create source registry module**

Implement `SourceDefinition` and `load_sources(path: str) -> dict[str, SourceDefinition]`.

- [ ] **Step 4: Create initial source registry**

Include entries for:

- `international_results`
- `openfootball_worldcup`
- `fivethirtyeight_spi`
- `statsbomb_open_data`
- `football_data_uk`
- `polymarket_market_data`
- `the_odds_api`
- `x_api_aggregates`
- `reddit_aggregates`

- [ ] **Step 5: Run tests**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/data/test_source_registry.py -v
```

Expected: source registry tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add worldcup_prediction_lab/config/sources.yaml worldcup_prediction_lab/src/wc_predictor/config/settings.py worldcup_prediction_lab/src/wc_predictor/data/source_registry.py worldcup_prediction_lab/tests/data/test_source_registry.py
git commit -m "feat: add source registry contracts"
```

### Task 3: Team Entity Resolution

**Files:**
- Create: `worldcup_prediction_lab/config/team_aliases.csv`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/team_aliases.py`
- Test: `worldcup_prediction_lab/tests/data/test_team_aliases.py`

- [ ] **Step 1: Write alias tests**

Test known difficult aliases:

```python
from wc_predictor.data.team_aliases import TeamAliasResolver


def test_common_country_aliases_resolve_to_canonical_ids():
    resolver = TeamAliasResolver.from_csv("worldcup_prediction_lab/config/team_aliases.csv")
    assert resolver.resolve("USA", "manual").canonical_name == "United States"
    assert resolver.resolve("Czech Republic", "manual").canonical_name == "Czechia"
    assert resolver.resolve("DR Congo", "manual").canonical_name == "DR Congo"
    assert resolver.resolve("Ivory Coast", "manual").canonical_name == "Ivory Coast"
```

- [ ] **Step 2: Create alias CSV**

Seed `config/team_aliases.csv` with canonical teams expected for World Cup 2026 and common aliases across public sources.

- [ ] **Step 3: Implement resolver**

Implement exact-match resolution first, with explicit failure for unknown names. Fuzzy matching can be added only after exact aliases are validated.

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/data/test_team_aliases.py -v
git add worldcup_prediction_lab/config/team_aliases.csv worldcup_prediction_lab/src/wc_predictor/data/team_aliases.py worldcup_prediction_lab/tests/data/test_team_aliases.py
git commit -m "feat: add team alias resolver"
```

### Task 4: Historical Results Ingestion

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_international_results.py`
- Test: `worldcup_prediction_lab/tests/data/test_ingest_international_results.py`

- [ ] **Step 1: Write parser test using fixture CSV**

Use a small embedded fixture with `date`, `home_team`, `away_team`, `home_score`, `away_score`, `tournament`, `city`, `country`, `neutral`.

- [ ] **Step 2: Implement ingestion**

Implement:

- download raw CSV from configured URL
- save raw snapshot with hash
- parse to bronze Parquet
- normalize teams to silver match table
- write manifest JSON with source URL, ingest time, row count, and hash

- [ ] **Step 3: Add data-quality checks**

Checks:

- no missing date/team/score fields
- scores are non-negative integers
- no duplicate `(date, home_team, away_team, tournament, city)` records after normalization
- neutral flag is boolean

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/data/test_ingest_international_results.py -v
git add worldcup_prediction_lab/src/wc_predictor/data/ingest_international_results.py worldcup_prediction_lab/tests/data/test_ingest_international_results.py
git commit -m "feat: ingest international results"
```

### Task 5: World Cup Fixture Ingestion

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_openfootball_worldcup.py`
- Test: `worldcup_prediction_lab/tests/data/test_ingest_openfootball_worldcup.py`

- [ ] **Step 1: Write fixture parser tests**

Test parsing of a 2026-style group match line with date, time zone, teams, and venue.

- [ ] **Step 2: Implement Football.TXT parser**

Parse group and knockout fixture data into a normalized `fixtures` silver table.

- [ ] **Step 3: Add cross-check fields**

Include:

- `fixture_id`
- `stage`
- `group`
- `home_team_id`
- `away_team_id`
- `kickoff_utc`
- `venue_name`
- `city`
- `source_updated_at`
- `needs_manual_review`

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/data/test_ingest_openfootball_worldcup.py -v
git add worldcup_prediction_lab/src/wc_predictor/data/ingest_openfootball_worldcup.py worldcup_prediction_lab/tests/data/test_ingest_openfootball_worldcup.py
git commit -m "feat: ingest world cup fixtures"
```

### Task 6: SPI And Market Benchmark Ingestion

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_spi.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_polymarket.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_odds.py`
- Tests: matching files under `worldcup_prediction_lab/tests/data/`

- [ ] **Step 1: Add SPI ingestion test**

Test parsing of rows containing `date`, `team1`, `team2`, `spi1`, `spi2`, `prob1`, `prob2`, `probtie`, `proj_score1`, `proj_score2`, `score1`, `score2`.

- [ ] **Step 2: Implement SPI ingestion**

Download and parse international SPI CSV if reachable. Store ratings and forecasts as benchmark features and evaluation baselines.

- [ ] **Step 3: Add Polymarket parser test**

Use a fixture with `outcomes` and `outcomePrices` arrays. Assert probabilities are parsed as numeric values and mapped to outcome names.

- [ ] **Step 4: Implement Polymarket ingestion**

Use public market-data endpoints only. Store event, market, token, price, spread, order-book snapshot, open interest, and collected timestamp.

- [ ] **Step 5: Add odds parser test**

Use a fixture for `h2h`, `totals`, and `spreads`. Assert implied probabilities include bookmaker margin and normalized no-vig probabilities.

- [ ] **Step 6: Implement odds ingestion**

Support The Odds API when `THE_ODDS_API_KEY` is present. Skip gracefully with a clear message when the key is absent.

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/data/test_ingest_spi.py worldcup_prediction_lab/tests/data/test_ingest_polymarket.py worldcup_prediction_lab/tests/data/test_ingest_odds.py -v
git add worldcup_prediction_lab/src/wc_predictor/data/ingest_spi.py worldcup_prediction_lab/src/wc_predictor/data/ingest_polymarket.py worldcup_prediction_lab/src/wc_predictor/data/ingest_odds.py worldcup_prediction_lab/tests/data
git commit -m "feat: ingest forecast and market sources"
```

### Task 7: Feature Generation

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/features/team_strength.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/features/match_features.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/features/market_features.py`
- Tests: matching files under `worldcup_prediction_lab/tests/features/`

- [ ] **Step 1: Write point-in-time feature tests**

Build a small match history and assert a match on date `D` only sees matches before `D`.

- [ ] **Step 2: Implement team strength features**

Compute:

- rolling goals for/against
- rolling goal difference
- rolling win/draw/loss rates
- recency-weighted form
- tournament-weighted form
- opponent-adjusted goal strength

- [ ] **Step 3: Implement match features**

Compute:

- neutral-site flag
- host-team flag
- venue/country
- rest days
- travel proxy if coordinates are available
- stage/group/knockout flag
- confederation if source is added

- [ ] **Step 4: Implement market features**

Compute:

- no-vig home/draw/away probabilities
- market movement from earlier snapshot
- Polymarket midpoint probability
- spread and liquidity indicators
- source freshness in minutes

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/features -v
git add worldcup_prediction_lab/src/wc_predictor/features worldcup_prediction_lab/tests/features
git commit -m "feat: build point-in-time features"
```

### Task 8: Prediction Schema And Ledger

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/models/base.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/evaluation/ledger.py`
- Test: `worldcup_prediction_lab/tests/evaluation/test_ledger.py`

- [ ] **Step 1: Write ledger immutability and determinism tests**

Assert that writing a prediction with the same `prediction_id` twice fails unless the second write is byte-identical. Also assert determinism: serialize the prediction to canonical JSON (sorted keys, fixed separators) with all probabilities rounded to 6 decimals, compute a SHA-256 `prediction_hash`, and assert the hash is stable across re-serialization on this machine. This is the pattern the epl-prediction-lab comparator uses to make pre-kickoff predictions independently verifiable; without float rounding the hash will differ across runs/platforms.

- [ ] **Step 2: Implement model output schemas**

Define:

- `MatchPrediction` (includes `prediction_hash`: SHA-256 over canonical JSON of the rounded prediction payload)
- `ScorelineDistribution`
- `ModelMetadata`
- `FeatureSnapshotMetadata`

- [ ] **Step 3: Implement ledger writer**

Write prediction records as JSONL partitioned by prediction date:

```text
worldcup_prediction_lab/runs/predictions/date=YYYY-MM-DD/predictions.jsonl
```

- [ ] **Step 4: Implement result-scoring join**

Join final results to immutable predictions without changing the prediction row. Write evaluation rows separately.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/evaluation/test_ledger.py -v
git add worldcup_prediction_lab/src/wc_predictor/models/base.py worldcup_prediction_lab/src/wc_predictor/evaluation/ledger.py worldcup_prediction_lab/tests/evaluation/test_ledger.py
git commit -m "feat: add immutable prediction ledger"
```

### Task 9: Metrics And Backtesting

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/evaluation/metrics.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/evaluation/backtest.py`
- Tests: matching files under `worldcup_prediction_lab/tests/evaluation/`

- [ ] **Step 1: Write metric tests**

Use known probability vectors and outcomes. Assert exact Brier score, log loss, exact-score hit, and probability sums.

- [ ] **Step 2: Implement metrics**

Implement:

- `scoreline_log_loss`
- `home_draw_away_log_loss`
- `brier_score`
- `ranked_probability_score`
- `exact_score_hit`
- `top_k_score_hit`
- `expected_goals_mae`
- `calibration_bins`

- [ ] **Step 3: Write backtest leakage test**

Use synthetic matches to assert training window ends before prediction window starts.

- [ ] **Step 4: Implement walk-forward backtest runner**

Expose CLI-compatible function:

```python
run_backtest(
    train_start: str,
    first_prediction_date: str,
    final_prediction_date: str,
    prediction_window_days: int,
    model_id: str,
) -> BacktestReport
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/evaluation -v
git add worldcup_prediction_lab/src/wc_predictor/evaluation worldcup_prediction_lab/tests/evaluation
git commit -m "feat: add forecasting metrics and backtests"
```

### Task 10: Baseline And Poisson Models

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/models/baseline.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/elo.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/poisson.py`
- Tests: matching files under `worldcup_prediction_lab/tests/models/`

- [ ] **Step 1: Write baseline tests**

Assert probabilities sum to 1 and scoreline matrix has non-negative entries.

- [ ] **Step 2: Implement climatology baseline**

Fit average goals and draw rates from training data. Generate scorelines from global goal rates.

- [ ] **Step 3: Write Elo update tests**

Assert winner gains Elo, loser loses Elo, draw changes are smaller, and neutral/home flags are respected.

- [ ] **Step 4: Implement Elo model**

Maintain team Elo through historical match order. Export pre-match rating features.

- [ ] **Step 5: Write Poisson model tests**

Assert expected goals are positive and scoreline distribution sums to 1 including tail mass.

- [ ] **Step 6: Implement Poisson model**

Fit expected goals from rating difference, attack/defense features, venue, recency, and tournament importance.

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/models/test_baseline.py worldcup_prediction_lab/tests/models/test_elo.py worldcup_prediction_lab/tests/models/test_poisson.py -v
git add worldcup_prediction_lab/src/wc_predictor/models worldcup_prediction_lab/tests/models
git commit -m "feat: add baseline elo and poisson models"
```

### Task 11: Dixon-Coles And Calibration

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/models/dixon_coles.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/models/calibration.py`
- Tests: matching files under `worldcup_prediction_lab/tests/models/`

- [ ] **Step 1: Write Dixon-Coles low-score tests**

Assert the correction changes probabilities for `0-0`, `1-0`, `0-1`, `1-1` and leaves matrix normalized.

- [ ] **Step 2: Implement Dixon-Coles correction**

Add low-score dependency parameter and recency weighting.

- [ ] **Step 3: Write calibration tests**

Assert calibrated probabilities remain in `[0, 1]` and sum to 1. Add a calibration *regression* test: on a frozen synthetic or fixed-fixture set with known outcome frequencies, assert the reliability curve is within tolerance (e.g. expected calibration error below a set threshold) so that "calibration" is verified to actually calibrate, not just stay in range. Add a separate no-vig test for market features: assert bookmaker-implied probabilities are de-margined correctly (raw implied sum > 1, normalized no-vig sum == 1 within tolerance).

- [ ] **Step 4: Implement calibration**

Start with temperature scaling or isotonic calibration for `home/draw/away`. Add scoreline calibration only after match-level calibration works.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/models/test_dixon_coles.py worldcup_prediction_lab/tests/models/test_calibration.py -v
git add worldcup_prediction_lab/src/wc_predictor/models/dixon_coles.py worldcup_prediction_lab/src/wc_predictor/models/calibration.py worldcup_prediction_lab/tests/models
git commit -m "feat: add dixon coles and calibration models"
```

### Task 12: Tournament Simulation

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/simulation/tournament.py`
- Test: `worldcup_prediction_lab/tests/test_tournament_simulation.py`

- [ ] **Step 1: Write group-table and 2026-format tests**

Use a four-team group fixture set. Assert points, goal difference, goals for, and rankings are calculated correctly. **Critical for 2026:** the format is 48 teams in 12 groups of 4, and the round of 32 includes the **8 best third-placed teams** selected by a specific FIFA ranking procedure (points, then goal difference, then goals scored, etc., compared *across* groups). Write an explicit test for the third-place ranking and the resulting bracket seeding using a known fixture set - this is a common correctness trap and must not be left implicit. Also test the FIFA group-stage tiebreaker order, including head-to-head where it applies.

- [ ] **Step 2: Implement match simulation**

Sample scorelines from `ScorelineDistribution`, including knockout extra-time/penalty handling as separate assumptions.

- [ ] **Step 3: Implement tournament simulation**

Run Monte Carlo simulations from current fixture state using an explicit, recorded RNG seed (required for the reproducible-prediction acceptance gate) and output:

- group advancement probabilities
- round of 32/16/quarter/semi/final/winner probabilities
- expected points
- most likely bracket paths

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/test_tournament_simulation.py -v
git add worldcup_prediction_lab/src/wc_predictor/simulation/tournament.py worldcup_prediction_lab/tests/test_tournament_simulation.py
git commit -m "feat: add tournament simulation"
```

### Task 13: Live Runner

**Files:**
- Create: `worldcup_prediction_lab/config/live_schedule.yaml`
- Create: `worldcup_prediction_lab/src/wc_predictor/live/runner.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/cli/main.py`
- Test: `worldcup_prediction_lab/tests/live/test_runner.py`

- [ ] **Step 1: Write dry-run tests**

Assert a dry run prints planned actions and does not download or write raw data.

- [ ] **Step 2: Implement CLI commands**

Commands:

```text
wc-predictor ingest --source international_results
wc-predictor build-features --as-of 2026-06-11T12:00:00Z
wc-predictor train --model elo_poisson_v1 --as-of 2026-06-11T12:00:00Z
wc-predictor predict --fixture-id <fixture_id> --model champion
wc-predictor backtest --model elo_poisson_v1
wc-predictor score-results --results-date 2026-06-11
wc-predictor live-cycle --dry-run
```

- [ ] **Step 3: Implement live cycle**

Cycle order:

1. refresh eligible sources
2. validate data quality
3. build features
4. generate predictions
5. write ledger
6. score completed matches
7. update Elo
8. run candidate/champion comparison
9. write report

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/live/test_runner.py -v
git add worldcup_prediction_lab/config/live_schedule.yaml worldcup_prediction_lab/src/wc_predictor/live/runner.py worldcup_prediction_lab/src/wc_predictor/cli/main.py worldcup_prediction_lab/tests/live/test_runner.py
git commit -m "feat: add live prediction cycle"
```

### Task 14: Social And News Aggregate Features

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_news.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/data/ingest_social_aggregates.py`
- Create: `worldcup_prediction_lab/src/wc_predictor/features/social_news_features.py`
- Tests: matching files under `worldcup_prediction_lab/tests/`

- [ ] **Step 1: Add compliance tests**

Assert Reddit ingestion cannot write raw user text into training datasets. Assert X/news raw text retention is configurable and disabled unless explicitly enabled.

- [ ] **Step 2: Implement news ingestion**

Store article metadata, source, title hash, publication timestamp, entity tags, and injury/lineup category labels. Store full text only if the source license permits it.

- [ ] **Step 3: Implement social aggregates**

Aggregate by team and time bucket:

- mention count
- verified/source-weighted mention count
- sentiment score
- injury rumor count
- lineup confidence count
- market-related discussion count
- freshness

- [ ] **Step 4: Implement social/news features**

Join aggregates to fixtures using only timestamps before prediction time.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/data/test_ingest_social_aggregates.py worldcup_prediction_lab/tests/features/test_social_news_features.py -v
git add worldcup_prediction_lab/src/wc_predictor/data/ingest_news.py worldcup_prediction_lab/src/wc_predictor/data/ingest_social_aggregates.py worldcup_prediction_lab/src/wc_predictor/features/social_news_features.py worldcup_prediction_lab/tests
git commit -m "feat: add compliant social and news aggregates"
```

### Task 15: Model Cards And Reports

**Files:**
- Create: `worldcup_prediction_lab/src/wc_predictor/evaluation/reporting.py`
- Create: `worldcup_prediction_lab/reports/model_cards/model_card_template.md`
- Tests: `worldcup_prediction_lab/tests/evaluation/test_reporting.py`

- [ ] **Step 1: Write report tests**

Assert report generation includes model ID, training window, feature set, metrics, calibration table, source list, and known limitations.

- [ ] **Step 2: Implement model card writer**

Write Markdown model cards to:

```text
worldcup_prediction_lab/reports/model_cards/<model_id>/<run_id>.md
```

- [ ] **Step 3: Implement daily prediction report**

Write Markdown and JSON summaries to:

```text
worldcup_prediction_lab/reports/backtests/
worldcup_prediction_lab/runs/evaluations/
```

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
uv run pytest worldcup_prediction_lab/tests/evaluation/test_reporting.py -v
git add worldcup_prediction_lab/src/wc_predictor/evaluation/reporting.py worldcup_prediction_lab/reports/model_cards/model_card_template.md worldcup_prediction_lab/tests/evaluation/test_reporting.py
git commit -m "feat: add model cards and forecast reports"
```

---

## Review Checklist For Claude

Ask Claude to review the plan against these questions:

- Does the plan prevent time leakage in training and evaluation?
- Is the live learning loop correctly using actual results as labels and predictions as error feedback?
- Are market features separated from model-only features so we can measure their true value?
- Are social/news features legally safer as aggregates instead of raw text?
- Is the local hardware plan realistic for the 12 GB RTX 5070 and 268 GB free disk?
- Are the implementation tasks small enough for agentic execution?
- Are there missing tests for probability normalization, calibration, ledger immutability, or entity resolution?
- Is the champion/candidate promotion process strict enough?
- Are source licensing and attribution obligations visible enough?
- Is the plan overbuilt for a first milestone, and if so, which tasks should be deferred?

---

## First Milestone Recommendation

**Goal of milestone 1: produce one honest walk-forward backtest number for a calibrated Elo model before building any infrastructure around it.** The earlier "through Task 10" scope is still too large for a first pass - it pulls in 6 ingestion sources and 3+ model families before a single trustworthy metric exists.

### Milestone 1 (the real first ~2 weeks) - Elo-first vertical slice

Implement only:

1. Task 1 - project skeleton and environment.
2. Task 3 - team entity resolution (needed to join any results).
3. Task 4 - historical international results ingestion (the one essential source).
4. Task 10, Elo portion only - calibrated Elo -> win/draw/loss, plus the Poisson scoreline conversion.
5. Task 8 - immutable, deterministic prediction ledger.
6. Task 9 - core metrics (RPS, log loss, Brier, exact-score hit) and ONE walk-forward backtest.

Success test for milestone 1: a reproducible walk-forward backtest reporting RPS and log loss for calibrated Elo vs the climatology baseline, with sample sizes. Target reference values from comparators: RPS in the ~0.17-0.18 range, ~60-62% result accuracy. If we cannot reproduce roughly that, fix the pipeline before adding anything.

### Deliberately deferred past milestone 1

Defer until milestone 1 passes: SPI/Polymarket/odds ingestion (Task 6), features beyond Elo + rest + neutral-site (Task 7), Dixon-Coles (Task 11), tournament simulation (Task 12), live runner (Task 13), social/news (Task 14), reporting polish (Task 15), and all of model-ladder rungs 3 and 6-8. Each of those must beat the calibrated-Elo champion to earn its place (see Modeling Strategy).

Do not build social/news, deep learning, tournament UI, or live dashboard before milestone 1 passes a historical walk-forward backtest.

---

## Operating Principles

- Prediction timestamps are sacred.
- Raw data is evidence, not a training table.
- Every feature must prove it was available at prediction time.
- Exact scores are reported as probabilities, not certainties.
- Calibration beats theatrical confidence.
- The market-aware model and model-only version should both exist.
- The system learns from errors, not from believing its own guesses.
- Every live prediction gets stored before the match starts.
- Every model promotion leaves behind a model card.
- If a data source's terms are unclear, exclude raw content and keep only compliant aggregates.

---

## Source Links

- Comparator: World Cup 2026 model (Elo + Dixon-Coles + Monte Carlo): https://github.com/Hicruben/world-cup-2026-prediction-model
- Comparator: leakage-free international Elo predictor: https://github.com/hjjbh1314/worldcup-predictor
- Comparator: pre-kickoff SHA-256 prediction ledger pattern: https://github.com/tuantqse90/epl-prediction-lab
- FiveThirtyEight soccer SPI data (FROZEN, pre-2023 only): https://github.com/fivethirtyeight/data/tree/master/soccer-spi
- FiveThirtyEight SPI discontinuation context: https://fromthebyline.substack.com/p/fivethirtyeight-is-dead-long-live
- International results dataset: https://github.com/martj42/international_results
- OpenFootball World Cup data: https://github.com/openfootball/worldcup
- StatsBomb open data: https://github.com/statsbomb/open-data
- Football-Data.co.uk: https://www.football-data.co.uk/
- Polymarket market data docs: https://docs.polymarket.com/market-data/overview
- Polymarket trading docs: https://docs.polymarket.com/trading/overview
- The Odds API v4 docs: https://the-odds-api.com/liveapi/guides/v4/
- X Developer Platform: https://docs.x.com/overview
- Reddit Data API Terms: https://redditinc.com/policies/data-api-terms
- Match predictions in soccer: Machine learning vs. Poisson approaches: https://arxiv.org/abs/2408.08331
- Extending the Dixon and Coles model: https://arxiv.org/abs/2307.02139
- FIFA World Cup 2022 nested zero-inflated generalized Poisson regression: https://arxiv.org/abs/2205.04173
- Calibration in sports betting ML: https://arxiv.org/abs/2303.06021
- Market-calibrated in-play football forecasting: https://arxiv.org/abs/2605.16066
