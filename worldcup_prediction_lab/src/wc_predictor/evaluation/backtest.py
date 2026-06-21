"""Walk-forward backtest runner for match prediction models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.ledger import score_predictions, write_prediction
from wc_predictor.evaluation.metrics import (
    brier_score,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.models.base import MatchPrediction, ScorelineDistribution


class BacktestModel(Protocol):
    """Minimal model protocol for backtests.

    Models are fitted on a historical matches DataFrame and then asked for one
    match prediction at a time. ``predict_match`` must return an object or
    mapping with ``prob_home``, ``prob_draw``, and ``prob_away`` probabilities.
    It may also include a scoreline distribution for future model tasks.
    """

    def fit(self, train_matches_df: pd.DataFrame) -> Any | None:
        ...

    def predict_match(self, match_row: pd.Series) -> Any:
        ...


@dataclass(frozen=True)
class BacktestWindowReport:
    training_cutoff: str
    window_end: str
    training_match_count: int
    predicted_match_count: int
    match_ids: list[str]
    training_dates: list[str]
    prediction_dates: list[str]
    per_match_log_loss: list[float]
    per_match_brier: list[float]
    per_match_rps: list[float]
    mean_log_loss: float | None
    mean_brier: float | None
    mean_rps: float | None


@dataclass(frozen=True)
class BacktestReport:
    model_id: str
    train_start: str
    first_prediction_date: str
    final_prediction_date: str
    prediction_window_days: int
    windows: list[BacktestWindowReport]
    total_matches_predicted: int
    window_count: int
    per_match_log_loss: list[float]
    per_match_brier: list[float]
    per_match_rps: list[float]
    mean_log_loss: float | None
    mean_brier: float | None
    mean_rps: float | None


def _date_string(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m-%d")


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _prediction_value(prediction: Any, key: str) -> Any:
    if isinstance(prediction, Mapping):
        return prediction[key]
    return getattr(prediction, key)


def _optional_prediction_value(prediction: Any, key: str) -> Any:
    if isinstance(prediction, Mapping):
        return prediction.get(key)
    return getattr(prediction, key, None)


def _coerce_scoreline_distribution(value: Any) -> ScorelineDistribution | None:
    if value is None or isinstance(value, ScorelineDistribution):
        return value
    if isinstance(value, Mapping):
        return ScorelineDistribution(**value)
    raise TypeError("scoreline_distribution must be a ScorelineDistribution or mapping")


def _prepare_matches(matches_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"match_id", "date", "home_score", "away_score"}
    missing_columns = required_columns - set(matches_df.columns)
    if missing_columns:
        raise ValueError(f"matches_df missing required columns: {sorted(missing_columns)}")

    matches = matches_df.copy()
    matches["date"] = pd.to_datetime(matches["date"])
    return matches.sort_values(["date", "match_id"]).reset_index(drop=True)


def _build_prediction(
    *,
    model_prediction: Any,
    match_row: pd.Series,
    model_id: str,
    training_cutoff: str,
    generated_at_utc: str,
) -> MatchPrediction:
    match_id = str(match_row["match_id"])
    return MatchPrediction(
        prediction_id=f"{model_id}:{match_id}:{training_cutoff}",
        match_id=match_id,
        model_id=model_id,
        model_version="backtest",
        generated_at_utc=generated_at_utc,
        training_cutoff=training_cutoff,
        as_of=training_cutoff,
        prob_home=float(_prediction_value(model_prediction, "prob_home")),
        prob_draw=float(_prediction_value(model_prediction, "prob_draw")),
        prob_away=float(_prediction_value(model_prediction, "prob_away")),
        scoreline_distribution=_coerce_scoreline_distribution(
            _optional_prediction_value(model_prediction, "scoreline_distribution")
        ),
    )


def run_backtest(
    matches_df: pd.DataFrame,
    model_factory: Callable[[], BacktestModel],
    train_start: str,
    first_prediction_date: str,
    final_prediction_date: str,
    prediction_window_days: int,
    model_id: str,
    runs_dir: str | Path = settings.RUNS_DIR,
) -> BacktestReport:
    """Run a deterministic walk-forward backtest and write predictions to the ledger.

    Each window fits a fresh model on matches with
    ``train_start <= date < training_cutoff`` and predicts matches with
    ``training_cutoff <= date < window_end``. The model only needs the minimal
    ``BacktestModel`` protocol documented above; concrete climatology and Elo
    implementations plug in later through ``model_factory``.
    """

    if prediction_window_days <= 0:
        raise ValueError("prediction_window_days must be positive")

    matches = _prepare_matches(matches_df)
    train_start_ts = pd.Timestamp(train_start)
    first_prediction_ts = pd.Timestamp(first_prediction_date)
    final_prediction_ts = pd.Timestamp(final_prediction_date)
    if final_prediction_ts < first_prediction_ts:
        raise ValueError("final_prediction_date must be on or after first_prediction_date")

    generated_at_utc = f"{_date_string(first_prediction_ts)}T00:00:00Z"
    window_step = pd.Timedelta(days=prediction_window_days)
    inclusive_final_end = final_prediction_ts + pd.Timedelta(days=1)

    windows: list[BacktestWindowReport] = []
    all_log_loss: list[float] = []
    all_brier: list[float] = []
    all_rps: list[float] = []

    training_cutoff_ts = first_prediction_ts
    while training_cutoff_ts <= final_prediction_ts:
        window_end_ts = min(training_cutoff_ts + window_step, inclusive_final_end)
        training_cutoff = _date_string(training_cutoff_ts)
        window_end = _date_string(window_end_ts)

        train_matches = matches[
            (matches["date"] >= train_start_ts) & (matches["date"] < training_cutoff_ts)
        ].copy()
        prediction_matches = matches[
            (matches["date"] >= training_cutoff_ts) & (matches["date"] < window_end_ts)
        ].copy()

        model = model_factory()
        fitted = model.fit(train_matches)
        if fitted is not None:
            model = fitted

        predictions: list[MatchPrediction] = []
        for _, match_row in prediction_matches.iterrows():
            model_prediction = model.predict_match(match_row)
            prediction = _build_prediction(
                model_prediction=model_prediction,
                match_row=match_row,
                model_id=model_id,
                training_cutoff=training_cutoff,
                generated_at_utc=generated_at_utc,
            )
            write_prediction(prediction, runs_dir=runs_dir)
            predictions.append(prediction)

        scored_rows = score_predictions(
            predictions=[asdict(prediction) for prediction in predictions],
            results=prediction_matches[
                ["match_id", "home_score", "away_score"]
            ].to_dict(orient="records"),
        )

        window_log_loss: list[float] = []
        window_brier: list[float] = []
        window_rps: list[float] = []
        for scored_row in scored_rows:
            probabilities = [
                float(scored_row["prob_home"]),
                float(scored_row["prob_draw"]),
                float(scored_row["prob_away"]),
            ]
            outcome = str(scored_row["actual_outcome"])
            window_log_loss.append(home_draw_away_log_loss(probabilities, outcome))
            window_brier.append(brier_score(probabilities, outcome))
            window_rps.append(ranked_probability_score(probabilities, outcome))

        all_log_loss.extend(window_log_loss)
        all_brier.extend(window_brier)
        all_rps.extend(window_rps)

        windows.append(
            BacktestWindowReport(
                training_cutoff=training_cutoff,
                window_end=window_end,
                training_match_count=len(train_matches),
                predicted_match_count=len(prediction_matches),
                match_ids=[str(match_id) for match_id in prediction_matches["match_id"]],
                training_dates=[
                    _date_string(date) for date in train_matches["date"].tolist()
                ],
                prediction_dates=[
                    _date_string(date) for date in prediction_matches["date"].tolist()
                ],
                per_match_log_loss=window_log_loss,
                per_match_brier=window_brier,
                per_match_rps=window_rps,
                mean_log_loss=_mean(window_log_loss),
                mean_brier=_mean(window_brier),
                mean_rps=_mean(window_rps),
            )
        )
        training_cutoff_ts += window_step

    return BacktestReport(
        model_id=model_id,
        train_start=_date_string(train_start_ts),
        first_prediction_date=_date_string(first_prediction_ts),
        final_prediction_date=_date_string(final_prediction_ts),
        prediction_window_days=prediction_window_days,
        windows=windows,
        total_matches_predicted=len(all_log_loss),
        window_count=len(windows),
        per_match_log_loss=all_log_loss,
        per_match_brier=all_brier,
        per_match_rps=all_rps,
        mean_log_loss=_mean(all_log_loss),
        mean_brier=_mean(all_brier),
        mean_rps=_mean(all_rps),
    )
