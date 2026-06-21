"""Deterministic model prediction schemas and hashing helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from hashlib import sha256
import json
from typing import Any


PROBABILITY_SUM_TOLERANCE = 1e-6


def _json_ready(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def canonical_json(payload: Any) -> str:
    """Serialize payload with sorted keys, compact separators, and rounded floats."""

    return json.dumps(
        _json_ready(payload),
        sort_keys=True,
        separators=(",", ":"),
    )


def compute_prediction_hash(payload: Any) -> str:
    """Compute the prediction hash over canonical payload excluding its hash field."""

    if is_dataclass(payload) and not isinstance(payload, type):
        payload_for_hash = asdict(payload)
    else:
        payload_for_hash = dict(payload)
    payload_for_hash.pop("prediction_hash", None)
    return sha256(canonical_json(payload_for_hash).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScorelineDistribution:
    match_id: str
    model_id: str
    generated_at_utc: str
    max_goals: int
    home_expected_goals: float
    away_expected_goals: float
    probabilities: dict[str, float]
    tail_probability: float


@dataclass(frozen=True)
class ModelMetadata:
    model_id: str
    model_version: str
    generated_at_utc: str
    training_cutoff: str
    as_of: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureSnapshotMetadata:
    snapshot_id: str
    generated_at_utc: str
    as_of: str
    source_ids: list[str] = field(default_factory=list)
    feature_version: str | None = None


@dataclass(frozen=True)
class MatchPrediction:
    prediction_id: str
    match_id: str
    model_id: str
    model_version: str
    generated_at_utc: str
    training_cutoff: str
    as_of: str
    prob_home: float
    prob_draw: float
    prob_away: float
    scoreline_distribution: ScorelineDistribution | None = None
    prediction_hash: str = field(init=False, default="")

    def __post_init__(self) -> None:
        probabilities = (self.prob_home, self.prob_draw, self.prob_away)
        if any(probability < 0.0 or probability > 1.0 for probability in probabilities):
            raise ValueError("home/draw/away probabilities must be between 0.0 and 1.0")
        if abs(sum(probabilities) - 1.0) > PROBABILITY_SUM_TOLERANCE:
            raise ValueError("home/draw/away probabilities must sum to 1.0")

        payload = asdict(self)
        object.__setattr__(self, "prediction_hash", compute_prediction_hash(payload))
