import pandas as pd
import pytest

from wc_predictor.lab import registry


def _synthetic_matches() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": f"m{i}",
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
                "home_team_id": home,
                "away_team_id": away,
                "home_score": hs,
                "away_score": away_score,
                "tournament": "Friendly",
                "neutral": True,
                "occurrence_index": i,
            }
            for i, (home, away, hs, away_score) in enumerate(
                [
                    ("A", "B", 2, 0),
                    ("B", "C", 2, 0),
                    ("C", "A", 0, 2),
                    ("A", "C", 1, 1),
                    ("B", "A", 1, 1),
                    ("C", "B", 0, 2),
                    ("A", "B", 3, 1),
                    ("B", "C", 0, 0),
                    ("C", "A", 1, 2),
                ],
                start=1,
            )
        ]
    )


def test_softmax_correction_learns_separable_probabilities():
    from wc_predictor.lab.ml_correction import SoftmaxCorrection

    model = SoftmaxCorrection(learning_rate=0.2, max_iter=500, l2=0.001)
    model.fit(
        [
            [3.0, 0.0],
            [2.5, 0.2],
            [0.0, 3.0],
            [0.2, 2.5],
            [-3.0, 0.0],
            [-2.5, 0.2],
        ],
        [0, 0, 1, 1, 2, 2],
    )

    home, draw, away = model.predict_proba([[3.0, 0.0]])[0]
    assert home > draw
    assert home > away
    assert home + draw + away == pytest.approx(1.0)


def test_registry_discovers_ml_elo_correction():
    found = registry.discover()
    assert "ml_elo_correction" in found
    model = registry.build("ml_elo_correction", generated_at_utc="2026-06-28T00:00:00Z")
    assert hasattr(model, "fit") and hasattr(model, "predict_match")


def test_ml_elo_correction_predicts_normalized_probabilities_after_fit():
    model = registry.build("ml_elo_correction", generated_at_utc="2026-06-28T00:00:00Z")
    model.fit(_synthetic_matches())

    match_row = pd.Series(
        {
            "match_id": "future",
            "home_team_id": "A",
            "away_team_id": "B",
            "tournament": "Friendly",
            "neutral": True,
        }
    )
    prediction = model.predict_match(match_row)

    total = prediction.prob_home + prediction.prob_draw + prediction.prob_away
    assert total == pytest.approx(1.0)
    assert all(
        0.0 <= prob <= 1.0
        for prob in (prediction.prob_home, prediction.prob_draw, prediction.prob_away)
    )


def test_ml_elo_correction_exposes_scoreline_contract():
    model = registry.build("ml_elo_correction", generated_at_utc="2026-06-28T00:00:00Z")
    model.fit(_synthetic_matches())
    scoreline = model.predict_scoreline(
        pd.Series(
            {
                "match_id": "future",
                "home_team_id": "A",
                "away_team_id": "B",
                "tournament": "Friendly",
                "neutral": True,
            }
        )
    )

    assert scoreline.match_id == "future"
    assert scoreline.model_id
