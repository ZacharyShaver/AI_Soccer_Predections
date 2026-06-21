from dataclasses import asdict
import json

import pytest

from wc_predictor.evaluation.ledger import score_predictions, write_prediction
from wc_predictor.models.base import (
    MatchPrediction,
    canonical_json,
    compute_prediction_hash,
)


def make_prediction(
    *,
    prediction_id: str = "pred-arg-bra-2026",
    match_id: str = "match-arg-bra-2026",
    prob_home: float = 0.5,
    prob_draw: float = 0.25,
    prob_away: float = 0.25,
) -> MatchPrediction:
    return MatchPrediction(
        prediction_id=prediction_id,
        match_id=match_id,
        model_id="unit_model",
        model_version="v1",
        generated_at_utc="2026-06-21T12:00:00Z",
        training_cutoff="2026-06-20",
        as_of="2026-06-21",
        prob_home=prob_home,
        prob_draw=prob_draw,
        prob_away=prob_away,
    )


def test_prediction_ledger_allows_only_byte_identical_idempotent_rewrite(tmp_path):
    prediction = make_prediction()

    ledger_path = write_prediction(prediction, runs_dir=tmp_path)
    rewrite_path = write_prediction(prediction, runs_dir=tmp_path)

    assert rewrite_path == ledger_path
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    conflicting_prediction = make_prediction(prob_home=0.49, prob_draw=0.26)
    with pytest.raises(ValueError, match="Conflicting prediction_id"):
        write_prediction(conflicting_prediction, runs_dir=tmp_path)


def test_prediction_hash_uses_canonical_json_with_six_decimal_rounding():
    payload = {
        "prediction_id": "pred-fixed",
        "match_id": "match-1",
        "model_id": "unit_model",
        "prob_home": 0.333333333,
        "prob_draw": 0.333333333,
        "prob_away": 0.333333334,
    }
    expected_canonical = (
        '{"match_id":"match-1","model_id":"unit_model",'
        '"prediction_id":"pred-fixed","prob_away":0.333333,'
        '"prob_draw":0.333333,"prob_home":0.333333}'
    )
    expected_hash = "af7caf9ef2e0cb8c95240cf936496b50db9deb66da7d89bef704ad67583cb37e"

    assert canonical_json(payload) == expected_canonical
    assert canonical_json(payload) == canonical_json(json.loads(canonical_json(payload)))
    assert compute_prediction_hash(payload) == expected_hash
    assert compute_prediction_hash(payload) == compute_prediction_hash(
        json.loads(canonical_json(payload))
    )


def test_match_prediction_hash_excludes_hash_field_and_validates_probability_sum():
    prediction = make_prediction(
        prob_home=0.333333333,
        prob_draw=0.333333333,
        prob_away=0.333333334,
    )
    payload = asdict(prediction)
    payload["prediction_hash"] = "wrong"

    assert prediction.prediction_hash == compute_prediction_hash(payload)

    with pytest.raises(ValueError, match="sum to 1.0"):
        make_prediction(prob_home=0.4, prob_draw=0.3, prob_away=0.2)


def test_score_predictions_returns_joined_rows_without_mutating_predictions():
    prediction = make_prediction()
    prediction_row = asdict(prediction)
    original_prediction_row = dict(prediction_row)

    scored = score_predictions(
        predictions=[prediction_row],
        results=[
            {
                "match_id": "match-arg-bra-2026",
                "home_score": 2,
                "away_score": 1,
            }
        ],
    )

    assert prediction_row == original_prediction_row
    assert scored == [
        {
            **original_prediction_row,
            "actual_home_score": 2,
            "actual_away_score": 1,
            "actual_outcome": "home",
        }
    ]
