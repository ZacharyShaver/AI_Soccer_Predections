"""Score immutable prediction-ledger rows against completed results."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from wc_predictor.evaluation.ledger import score_predictions
from wc_predictor.evaluation.metrics import (
    OUTCOME_ORDER,
    brier_score,
    exact_score_hit,
    home_draw_away_log_loss,
    ranked_probability_score,
)


PredictionInput = str | Path | Iterable[Mapping[str, Any]]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _jsonl_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(path)

    paths = sorted(path.rglob("*.jsonl"))
    if not paths:
        raise FileNotFoundError(f"no JSONL ledger files found under {path}")
    return paths


def _load_predictions(predictions: PredictionInput) -> list[dict[str, Any]]:
    if isinstance(predictions, (str, Path)):
        rows: list[dict[str, Any]] = []
        for path in _jsonl_paths(Path(predictions)):
            rows.extend(_read_jsonl(path))
        return rows

    return [dict(prediction) for prediction in predictions]


def _completed_results(results_df: pd.DataFrame) -> list[dict[str, Any]]:
    required = {"match_id", "home_score", "away_score"}
    missing = required - set(results_df.columns)
    if missing:
        raise ValueError(f"results_df missing required columns: {sorted(missing)}")

    completed = results_df.dropna(subset=["match_id", "home_score", "away_score"])
    return [
        {
            "match_id": row["match_id"],
            "home_score": int(row["home_score"]),
            "away_score": int(row["away_score"]),
        }
        for row in completed.to_dict(orient="records")
    ]


def _normalized_outcome_probs(row: Mapping[str, Any]) -> list[float]:
    """Home/draw/away probs renormalized to exactly sum to 1.0.

    Guards only against 6-dp rounding drift; a grossly malformed triple still
    fails the metrics' sum check downstream because each value stays in [0, 1].
    """

    probs = [float(row["prob_home"]), float(row["prob_draw"]), float(row["prob_away"])]
    total = sum(probs)
    if total <= 0.0:
        return probs
    return [value / total for value in probs]


def _argmax_outcome(row: Mapping[str, Any]) -> str:
    probs = _normalized_outcome_probs(row)
    return OUTCOME_ORDER[max(range(len(probs)), key=lambda index: probs[index])]


def _scoreline_probabilities(row: Mapping[str, Any]) -> dict[str, float] | None:
    distribution = row.get("scoreline_distribution")
    if distribution is None:
        return None
    if is_dataclass(distribution) and not isinstance(distribution, type):
        distribution = asdict(distribution)
    if not isinstance(distribution, Mapping):
        raise TypeError("scoreline_distribution must be a mapping")

    probabilities = distribution.get("probabilities")
    if probabilities is None:
        probabilities = distribution
    if not isinstance(probabilities, Mapping):
        raise TypeError("scoreline probabilities must be a mapping")

    # The stored grid sums to (1 - tail_probability) and each cell is 6-dp
    # rounded, so it does not sum to exactly 1.0. exact_score_hit only needs key
    # membership; renormalize so the metrics' sum check passes without touching
    # the immutable ledger row.
    cells = {str(key): float(value) for key, value in probabilities.items()}
    total = sum(cells.values())
    if total <= 0.0:
        return cells
    return {key: value / total for key, value in cells.items()}


def _finite_mean(values: Iterable[Any]) -> float | None:
    finite_values = [float(value) for value in values if math.isfinite(float(value))]
    if not finite_values:
        return None
    return sum(finite_values) / len(finite_values)


def _accuracy(values: pd.Series) -> float | None:
    if values.empty:
        return None
    return float(values.mean())


def _aggregate(evaluation: pd.DataFrame, *, n_total: int) -> dict[str, float | int | None]:
    n_scored = int(len(evaluation))
    if n_scored == 0:
        return {
            "n_total": n_total,
            "n_scored": 0,
            "n_pending": n_total,
            "mean_log_loss": None,
            "mean_brier": None,
            "mean_rps": None,
            "overall_accuracy": None,
            "decisive_accuracy": None,
            "exact_score_hit_rate": None,
        }

    exact_score_values = (
        evaluation["exact_score_hit"].dropna()
        if "exact_score_hit" in evaluation.columns
        else pd.Series(dtype=float)
    )
    decisive = evaluation.loc[evaluation["actual_outcome"] != "draw"]

    return {
        "n_total": n_total,
        "n_scored": n_scored,
        "n_pending": n_total - n_scored,
        "mean_log_loss": _finite_mean(evaluation["log_loss"]),
        "mean_brier": _finite_mean(evaluation["brier"]),
        "mean_rps": _finite_mean(evaluation["rps"]),
        "overall_accuracy": _accuracy(evaluation["called_it"]),
        # Decisive accuracy excludes drawn matches from the denominator.
        "decisive_accuracy": _accuracy(decisive["called_it"]) if not decisive.empty else None,
        "exact_score_hit_rate": (
            float(exact_score_values.mean()) if not exact_score_values.empty else None
        ),
    }


def score_ledger(
    predictions: PredictionInput,
    results_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float | int | None]]:
    """Score completed ledger predictions and summarize aggregate performance.

    Predictions without completed results are left unscored and counted as pending.
    Prediction input rows are copied before joining so scoring never mutates the ledger rows.
    Decisive accuracy excludes draws; overall accuracy includes every scored match.
    """

    prediction_rows = _load_predictions(predictions)
    scored_rows = score_predictions(
        predictions=prediction_rows,
        results=_completed_results(results_df),
    )

    evaluation_rows: list[dict[str, Any]] = []
    for row in scored_rows:
        # Ledger probabilities are stored rounded to 6 dp, so an independently
        # rounded home/draw/away triple can sum to 1.0 +/- ~1.5e-6 -- just past the
        # metrics' 1e-6 sum tolerance. Renormalize the rounding artifact here (the
        # on-disk prediction is untouched; predictions remain immutable labels).
        probs = _normalized_outcome_probs(row)
        actual_outcome = str(row["actual_outcome"])
        actual_score = (int(row["actual_home_score"]), int(row["actual_away_score"]))
        scoreline_probabilities = _scoreline_probabilities(row)

        evaluation_rows.append(
            {
                **row,
                "log_loss": home_draw_away_log_loss(probs, actual_outcome),
                "brier": brier_score(probs, actual_outcome),
                "rps": ranked_probability_score(probs, actual_outcome),
                "called_it": _argmax_outcome(row) == actual_outcome,
                "exact_score_hit": (
                    exact_score_hit(scoreline_probabilities, actual_score)
                    if scoreline_probabilities is not None
                    else None
                ),
            }
        )

    evaluation = pd.DataFrame(evaluation_rows)
    aggregate = _aggregate(evaluation, n_total=len(prediction_rows))
    return evaluation, aggregate
