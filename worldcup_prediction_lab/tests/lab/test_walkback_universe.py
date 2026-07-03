import pandas as pd

from wc_predictor.lab.walkback.universe import CUTOFF_DEFAULT, load_universe


def _fake_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "date": pd.to_datetime(["2024-06-01", "2025-03-10", "2025-11-02"]),
            "home_team": ["Spain", "Brazil", "Egypt"],
            "away_team": ["Austria", "Norway", "Ghana"],
            "home_score": [3, 1, 0],
            "away_score": [0, 1, 2],
            "tournament": ["Friendly"] * 3,
            "city": ["Sevilla", "Rio", "Cairo"],
            "elo_prob_home": [0.6, 0.5, 0.3],
            "elo_prob_draw": [0.25, 0.3, 0.3],
            "elo_prob_away": [0.15, 0.2, 0.4],
            "elo_home_rating": [2000.0, 2100.0, 1700.0],
            "elo_away_rating": [1800.0, 1950.0, 1750.0],
            "elo_home_advantage": [50.0, 50.0, 50.0],
            "market_prob_home": [0.65, 0.5, 0.28],
            "market_prob_draw": [0.22, 0.28, 0.32],
            "market_prob_away": [0.13, 0.22, 0.40],
        }
    )


def test_filters_to_cutoff_and_adds_outcome():
    uni = load_universe(cutoff="2025-01-01", frame=_fake_frame())
    assert list(uni["match_id"]) == ["m2", "m3"]
    assert list(uni["outcome"]) == ["draw", "away"]


def test_default_cutoff_is_2025():
    assert CUTOFF_DEFAULT == "2025-01-01"
