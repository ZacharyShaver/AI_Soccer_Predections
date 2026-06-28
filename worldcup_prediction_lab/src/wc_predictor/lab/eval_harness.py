"""Standard evaluation harness shared by every tuning/fusion/market experiment.

One module so every result this session is comparable and every number can be
traced back to the same three samples and the same scoring code:

* ``score_on_history``   — online walk-forward over martj42 results from
  2010-01-01 (15.8k matches). Generalization sample.
* ``score_on_wc60``      — leak-free walk-forward over the already-played WC-2026
  matches (the live-tournament sample) via :mod:`wc_predictor.lab.backtest`.
* ``score_on_market964`` — the martj42 ∩ Football-Data odds join (964 matches),
  scored against outcomes AND paired against the de-vigged market.

The harness is the regression guard for the whole session: with the recalibrated
config it must reproduce the established bars
(history 0.1744 / current WC sample 0.1606 / market964 0.1574). Every later
number depends on this, so the bars are pinned by tests.

Model / prediction contracts (deliberately three, because the three samples need
different things):

* history wants an *online* model — an ``EloModel``-like object exposing
  ``predict_match(row)`` and ``_update_from_match(row)`` so ratings evolve as the
  walk-forward advances.
* wc60 wants a *factory* ``build_model_fn(generated_at_utc=...) -> model`` that
  yields a fresh, unfitted model re-fit per match date (same contract as the lab
  variant registry's ``build_model``).
* market964 wants a *predict_fn* ``(row) -> (p_home, p_draw, p_away)`` evaluated on
  the aligned frame; pass ``None`` to score the leak-free Elo predictions that the
  harness attaches from ``model_factory``.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.elo_vs_market import (
    MARKET_ODDS_FILE,
    MATCHES_FILE,
    MIN_USABLE_SAMPLE,
    _read_parquet,
    add_elo_predictions,
    align_matches_with_market,
)
from wc_predictor.evaluation.metrics import (
    bootstrap_ci,
    brier_score,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.models.elo import EloModel

HISTORY_EVAL_START = "2010-01-01"
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20260627

# The de-vigged-market bar on the 964-match join, measured this session. Kept
# here so the dashboard's "distance to market" headline has a single source.
MARKET_BAR_RPS = 0.1496

ProbTriple = tuple[float, float, float]
PredictFn = Callable[[pd.Series], ProbTriple]

# ---------------------------------------------------------------------------
# Recalibrated reference model (the champion). No host fn: history and the
# market join are historical games, matching how the bars were measured.
# ---------------------------------------------------------------------------
_FLAT_TOURNAMENT_WEIGHTS = {
    "Friendly": 1.0,
    "FIFA World Cup": 1.0,
    "FIFA World Cup qualification": 1.0,
    "UEFA Euro": 1.0,
    "Copa America": 1.0,
    "CONCACAF Championship": 1.0,
    "CONCACAF Nations League": 1.0,
    "UEFA Nations League": 1.0,
    "African Cup of Nations": 1.0,
    "AFC Asian Cup": 1.0,
}


def recalibrated_elo() -> EloModel:
    """The elo_recalibrated config without a host fn (historical scoring)."""

    return EloModel(
        k_factor=30.0,
        home_advantage=75.0,
        draw_base_probability=0.33,
        draw_rating_scale=600.0,
        tournament_weights=_FLAT_TOURNAMENT_WEIGHTS,
        default_tournament_weight=1.0,
    )


def _outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def _normalize(probs: ProbTriple) -> list[float]:
    total = sum(probs) or 1.0
    return [p / total for p in probs]


# ---------------------------------------------------------------------------
# Sample 1: 15.8k online walk-forward history
# ---------------------------------------------------------------------------
def load_history_matches() -> pd.DataFrame:
    matches = _read_parquet(settings.SILVER_DIR / MATCHES_FILE)
    matches = matches.copy()
    matches["date"] = pd.to_datetime(matches["date"])
    sort_columns = [c for c in ("date", "occurrence_index", "match_id") if c in matches.columns]
    return matches.sort_values(sort_columns).reset_index(drop=True)


def score_on_history(
    model: EloModel,
    *,
    matches: pd.DataFrame | None = None,
    eval_start: str = HISTORY_EVAL_START,
) -> dict:
    """Online walk-forward: predict each match >= eval_start, then update on it.

    ``model`` must be a fresh, unfitted online model (``predict_match`` +
    ``_update_from_match``). Ports ``hist_sweep2.evaluate`` exactly so the
    recalibrated config reproduces RPS 0.1745.
    """

    if matches is None:
        matches = load_history_matches()
    start = pd.Timestamp(eval_start)

    rps_s = ll_s = brier_s = 0.0
    n = hits = dec_n = dec_hits = 0
    for row in matches.itertuples(index=False):
        record = row._asdict()
        if record["date"] >= start:
            series = pd.Series(record)
            pred = model.predict_match(series)
            probs = _normalize((pred.prob_home, pred.prob_draw, pred.prob_away))
            actual = _outcome(record["home_score"], record["away_score"])
            rps_s += ranked_probability_score(probs, actual)
            ll = home_draw_away_log_loss(probs, actual)
            ll_s += ll if ll != float("inf") else 0.0
            brier_s += brier_score(probs, actual)
            pick = ("home", "draw", "away")[probs.index(max(probs))]
            n += 1
            hits += int(pick == actual)
            if actual != "draw":
                dec_n += 1
                dec_hits += int(pick == actual)
        model._update_from_match(pd.Series(record))

    if n == 0:
        raise RuntimeError("no history matches scored; check eval_start and data")
    return {
        "n": n,
        "rps": rps_s / n,
        "log_loss": ll_s / n,
        "brier": brier_s / n,
        "acc": hits / n,
        "dec_acc": dec_hits / dec_n if dec_n else float("nan"),
    }


# ---------------------------------------------------------------------------
# Sample 2: current played-WC leak-free walk-forward backtest
# ---------------------------------------------------------------------------
def score_on_wc60(build_model_fn: Callable[..., object]) -> dict:
    """Score one model config on the played-WC matches via the lab backtest.

    ``build_model_fn`` is a registry-style factory
    ``build_model_fn(generated_at_utc=...) -> fresh model``. Returns the same
    metric dict shape as the other samples.
    """

    from datetime import timedelta

    from wc_predictor.forecast_live import (
        _fixture_match_row,
        _team_names,
        _training_matches,
        load_silver_data,
    )
    from wc_predictor.lab.backtest import _played_world_cup_matches

    matches_df, fixtures_df, teams_df = load_silver_data()
    names = _team_names(teams_df)
    played = _played_world_cup_matches(matches_df, fixtures_df)
    if played.empty:
        raise RuntimeError("no played WC matches available for wc60 scoring")

    match_dates = sorted(played["match_date"].dt.strftime("%Y-%m-%d").unique())
    rps_s = ll_s = brier_s = 0.0
    n = hits = dec_n = dec_hits = 0
    for day in match_dates:
        day_ts = pd.Timestamp(day)
        cutoff = (day_ts - timedelta(days=1)).strftime("%Y-%m-%d")
        model = build_model_fn(generated_at_utc=f"{day}T00:00:00Z")
        model.fit(_training_matches(matches_df, training_cutoff=cutoff))
        for fixture in played.loc[played["match_date"] == day_ts].itertuples(index=False):
            match_row = _fixture_match_row(pd.Series(fixture._asdict()), names)
            pred = model.predict_match(match_row)
            probs = _normalize((pred.prob_home, pred.prob_draw, pred.prob_away))
            actual = _outcome(fixture.home_score, fixture.away_score)
            rps_s += ranked_probability_score(probs, actual)
            ll = home_draw_away_log_loss(probs, actual)
            ll_s += ll if ll != float("inf") else 0.0
            brier_s += brier_score(probs, actual)
            pick = ("home", "draw", "away")[probs.index(max(probs))]
            n += 1
            hits += int(pick == actual)
            if actual != "draw":
                dec_n += 1
                dec_hits += int(pick == actual)

    if n == 0:
        raise RuntimeError("no WC fixtures scored")
    return {
        "n": n,
        "rps": rps_s / n,
        "log_loss": ll_s / n,
        "brier": brier_s / n,
        "acc": hits / n,
        "dec_acc": dec_hits / dec_n if dec_n else float("nan"),
    }


# ---------------------------------------------------------------------------
# Sample 3: 964-match market join
# ---------------------------------------------------------------------------
def build_market964_frame(
    *,
    model_factory: Callable[[], EloModel] = recalibrated_elo,
    matches_path=None,
    market_odds_path=None,
) -> pd.DataFrame:
    """Aligned 964-row frame with leak-free Elo probs + market probs attached.

    Reuses the exact market_blend / elo_vs_market alignment so the sample matches
    the established bars. The returned frame carries ``elo_prob_*`` and
    ``market_prob_*`` columns plus the result columns.
    """

    matches = _read_parquet(matches_path or settings.SILVER_DIR / MATCHES_FILE)
    market_odds = _read_parquet(market_odds_path or settings.SILVER_DIR / MARKET_ODDS_FILE)
    aligned, alignment = align_matches_with_market(matches, market_odds)
    if alignment.usable_joined_rows < MIN_USABLE_SAMPLE:
        raise RuntimeError(
            f"usable joined sample too small: {alignment.usable_joined_rows} < {MIN_USABLE_SAMPLE}"
        )
    return add_elo_predictions(aligned, matches, model_factory=model_factory)


def _probs_from_columns(row: pd.Series, prefix: str) -> list[float]:
    return _normalize(
        (
            float(row[f"{prefix}_prob_home"]),
            float(row[f"{prefix}_prob_draw"]),
            float(row[f"{prefix}_prob_away"]),
        )
    )


def score_on_market964(
    predict_fn: PredictFn | None = None,
    *,
    frame: pd.DataFrame | None = None,
    model_factory: Callable[[], EloModel] = recalibrated_elo,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Score predictions on the market join and pair them against the market.

    ``predict_fn`` maps each aligned row -> (p_home, p_draw, p_away). Pass
    ``None`` to score the leak-free Elo probabilities the harness attached via
    ``model_factory`` (this reproduces the Elo bar RPS 0.1574).

    Returns rps/log_loss/brier/n plus ``vs_market_paired`` = the paired bootstrap
    CI of (model_rps - market_rps); positive mean_diff means the model trails the
    market, ``excludes_0`` flags significance.
    """

    if frame is None:
        frame = build_market964_frame(model_factory=model_factory)

    model_rps_series: list[float] = []
    market_rps_series: list[float] = []
    ll_s = brier_s = 0.0
    n = 0
    for _, row in frame.iterrows():
        actual = _outcome(int(row["home_score"]), int(row["away_score"]))
        if predict_fn is None:
            probs = _probs_from_columns(row, "elo")
        else:
            probs = _normalize(tuple(predict_fn(row)))
        market_probs = _probs_from_columns(row, "market")
        model_rps_series.append(ranked_probability_score(probs, actual))
        market_rps_series.append(ranked_probability_score(market_probs, actual))
        ll = home_draw_away_log_loss(probs, actual)
        ll_s += ll if ll != float("inf") else 0.0
        brier_s += brier_score(probs, actual)
        n += 1

    if n == 0:
        raise RuntimeError("no market rows scored")
    model_rps = sum(model_rps_series) / n
    market_rps = sum(market_rps_series) / n
    diffs = [m - k for m, k in zip(model_rps_series, market_rps_series)]
    point, low, high, _ = bootstrap_ci(diffs, n_boot=BOOTSTRAP_N, alpha=0.05, seed=seed)
    return {
        "n": n,
        "rps": model_rps,
        "log_loss": ll_s / n,
        "brier": brier_s / n,
        "market_rps": market_rps,
        "vs_market_paired": {
            "mean_diff": point,
            "ci95": [low, high],
            "excludes_0": (low > 0.0) or (high < 0.0),
        },
    }
