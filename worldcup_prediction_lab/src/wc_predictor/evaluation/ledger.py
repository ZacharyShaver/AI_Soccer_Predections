"""Immutable prediction ledger writing and result joins."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from wc_predictor.config import settings
from wc_predictor.models.base import MatchPrediction, canonical_json


def _prediction_payload(prediction: MatchPrediction | Mapping[str, Any]) -> dict[str, Any]:
    if is_dataclass(prediction) and not isinstance(prediction, type):
        return asdict(prediction)
    return dict(prediction)


def _ledger_date(payload: Mapping[str, Any]) -> str:
    date_source = payload.get("generated_at_utc") or payload.get("as_of")
    if not date_source:
        raise ValueError("prediction requires generated_at_utc or as_of for ledger partition")
    return str(date_source)[:10]


def write_prediction(
    prediction: MatchPrediction | Mapping[str, Any],
    runs_dir: str | Path = settings.RUNS_DIR,
) -> Path:
    """Append a prediction to the JSONL ledger unless it is an exact idempotent re-write."""

    payload = _prediction_payload(prediction)
    prediction_id = payload.get("prediction_id")
    if not prediction_id:
        raise ValueError("prediction requires prediction_id")

    ledger_dir = Path(runs_dir) / "predictions" / f"date={_ledger_date(payload)}"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "predictions.jsonl"
    serialized = canonical_json(payload)

    if ledger_path.exists():
        with ledger_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                existing_serialized = line.rstrip("\n")
                if not existing_serialized:
                    continue
                existing_payload = json.loads(existing_serialized)
                if existing_payload.get("prediction_id") != prediction_id:
                    continue
                if existing_serialized == serialized:
                    return ledger_path
                raise ValueError(
                    f"Conflicting prediction_id {prediction_id!r} in "
                    f"{ledger_path}:{line_number}"
                )

    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized + "\n")
    return ledger_path


def _actual_outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if home_score < away_score:
        return "away"
    return "draw"


def score_predictions(
    predictions: Iterable[Mapping[str, Any]],
    results: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return prediction rows joined to results without mutating the prediction rows."""

    results_by_match_id = {result["match_id"]: dict(result) for result in results}
    scored_rows: list[dict[str, Any]] = []

    for prediction in predictions:
        prediction_row = dict(prediction)
        result = results_by_match_id.get(prediction_row.get("match_id"))
        if result is None:
            continue

        home_score = int(result["home_score"])
        away_score = int(result["away_score"])
        scored_rows.append(
            {
                **prediction_row,
                "actual_home_score": home_score,
                "actual_away_score": away_score,
                "actual_outcome": _actual_outcome(home_score, away_score),
            }
        )

    return scored_rows

