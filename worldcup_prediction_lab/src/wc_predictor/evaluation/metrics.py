"""Pure evaluation metrics for outcome and scoreline predictions."""

from __future__ import annotations

import math
import random
from typing import Iterable, Mapping, Sequence


PROBABILITY_SUM_TOLERANCE = 1e-6
OUTCOME_ORDER = ("home", "draw", "away")


def _validate_probability(value: float, *, label: str = "probability") -> float:
    probability = float(value)
    if not math.isfinite(probability):
        raise ValueError(f"{label} must be finite")
    if probability < 0.0 or probability > 1.0:
        raise ValueError(f"{label} must be between 0.0 and 1.0")
    return probability


def _validate_sum_to_one(probabilities: Sequence[float], *, label: str) -> list[float]:
    validated = [
        _validate_probability(probability, label=f"{label} probability")
        for probability in probabilities
    ]
    if abs(sum(validated) - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise ValueError(f"{label} probabilities must sum to 1.0")
    return validated


def _outcome_index(outcome: str) -> int:
    try:
        return OUTCOME_ORDER.index(outcome)
    except ValueError as exc:
        raise ValueError("outcome must be one of {'home', 'draw', 'away'}") from exc


def _validate_outcome_probs(probs: Sequence[float]) -> list[float]:
    if len(probs) != 3:
        raise ValueError("home/draw/away probabilities must contain exactly 3 values")
    return _validate_sum_to_one(probs, label="home/draw/away")


def _score_key(actual_score: tuple[int, int] | Sequence[int] | str) -> str:
    if isinstance(actual_score, str):
        return actual_score
    if len(actual_score) != 2:
        raise ValueError("actual_score must contain home and away goals")
    return f"{int(actual_score[0])}-{int(actual_score[1])}"


def _scoreline_probabilities(dist: Mapping[str, float]) -> dict[str, float]:
    if not dist:
        raise ValueError("scoreline distribution must not be empty")
    probabilities = {
        str(scoreline): _validate_probability(probability, label="scoreline probability")
        for scoreline, probability in dist.items()
    }
    if abs(sum(probabilities.values()) - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise ValueError("scoreline probabilities must sum to 1.0")
    return probabilities


def scoreline_log_loss(
    dist: Mapping[str, float],
    actual_score: tuple[int, int] | Sequence[int] | str,
) -> float:
    probabilities = _scoreline_probabilities(dist)
    actual_probability = probabilities.get(_score_key(actual_score), 0.0)
    if actual_probability <= 0.0:
        return math.inf
    return -math.log(actual_probability)


def home_draw_away_log_loss(probs: Sequence[float], outcome: str) -> float:
    probabilities = _validate_outcome_probs(probs)
    actual_probability = probabilities[_outcome_index(outcome)]
    if actual_probability <= 0.0:
        return math.inf
    return -math.log(actual_probability)


def brier_score(probs: Sequence[float], outcome: str) -> float:
    probabilities = _validate_outcome_probs(probs)
    actual_index = _outcome_index(outcome)
    return sum(
        (probability - (1.0 if index == actual_index else 0.0)) ** 2
        for index, probability in enumerate(probabilities)
    )


def ranked_probability_score(probs: Sequence[float], outcome: str) -> float:
    probabilities = _validate_outcome_probs(probs)
    actual_index = _outcome_index(outcome)
    score = 0.0
    for cutoff in range(len(probabilities) - 1):
        predicted_cdf = sum(probabilities[: cutoff + 1])
        actual_cdf = 1.0 if actual_index <= cutoff else 0.0
        score += (predicted_cdf - actual_cdf) ** 2
    return score / (len(probabilities) - 1)


def exact_score_hit(
    dist: Mapping[str, float],
    actual_score: tuple[int, int] | Sequence[int] | str,
) -> int:
    probabilities = _scoreline_probabilities(dist)
    return int(_score_key(actual_score) in probabilities)


def top_k_score_hit(
    dist: Mapping[str, float],
    actual_score: tuple[int, int] | Sequence[int] | str,
    k: int,
) -> int:
    if k <= 0:
        raise ValueError("k must be positive")
    probabilities = _scoreline_probabilities(dist)
    ranked_scorelines = sorted(probabilities, key=lambda key: (-probabilities[key], key))
    return int(_score_key(actual_score) in ranked_scorelines[:k])


def expected_goals_mae(
    pred_home_xg: float,
    pred_away_xg: float,
    actual_home: int,
    actual_away: int,
) -> float:
    return (
        abs(float(pred_home_xg) - int(actual_home))
        + abs(float(pred_away_xg) - int(actual_away))
    ) / 2.0


def calibration_bins(
    probs_list: Iterable[float],
    outcomes_list: Iterable[int | bool],
    n_bins: int = 10,
) -> list[dict[str, float | int]]:
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")

    pairs = list(zip(probs_list, outcomes_list, strict=True))
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for probability, outcome in pairs:
        predicted = _validate_probability(probability)
        actual = int(outcome)
        if actual not in (0, 1):
            raise ValueError("calibration outcomes must be 0/1 values")
        bin_index = min(int(predicted * n_bins), n_bins - 1)
        bins[bin_index].append((predicted, actual))

    summaries: list[dict[str, float | int]] = []
    for bin_values in bins:
        if not bin_values:
            continue
        count = len(bin_values)
        summaries.append(
            {
                "mean_predicted": sum(item[0] for item in bin_values) / count,
                "empirical_rate": sum(item[1] for item in bin_values) / count,
                "count": count,
            }
        )
    return summaries


def _quantile(sorted_values: Sequence[float], quantile: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute a quantile for an empty sample")
    if quantile <= 0.0:
        return sorted_values[0]
    if quantile >= 1.0:
        return sorted_values[-1]

    position = quantile * (len(sorted_values) - 1)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return sorted_values[lower_index]
    weight = position - lower_index
    return (
        sorted_values[lower_index] * (1.0 - weight)
        + sorted_values[upper_index] * weight
    )


def bootstrap_ci(
    per_match_metric_values: Sequence[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float, float, int]:
    values = [float(value) for value in per_match_metric_values]
    if not values:
        raise ValueError("per_match_metric_values must not be empty")
    if n_boot <= 0:
        raise ValueError("n_boot must be positive")
    if alpha <= 0.0 or alpha >= 1.0:
        raise ValueError("alpha must be between 0.0 and 1.0")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("per_match_metric_values must be finite")

    rng = random.Random(seed)
    n = len(values)
    point_estimate = sum(values) / n
    bootstrap_means = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot)
    )
    return (
        point_estimate,
        _quantile(bootstrap_means, alpha / 2.0),
        _quantile(bootstrap_means, 1.0 - alpha / 2.0),
        n,
    )
