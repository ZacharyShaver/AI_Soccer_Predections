from unittest.mock import MagicMock

import pandas as pd
import pytest

from wc_predictor.lab.walkback.harness import CONDITIONS, build_prompt, forecast_one


def _row():
    return pd.Series({
        "match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
        "date": pd.Timestamp("2025-03-10"), "city": "Rio", "tournament": "Friendly",
        "elo_prob_home": 0.5, "elo_prob_draw": 0.3, "elo_prob_away": 0.2,
        "elo_home_rating": 2100.0, "elo_away_rating": 1950.0, "elo_home_advantage": 50.0,
        "market_prob_home": 0.55, "market_prob_draw": 0.27, "market_prob_away": 0.18,
        "home_score": 1, "away_score": 1, "outcome": "draw",
    })


def _well():
    return {"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
            "match_date": "2025-03-10", "built_at": "x",
            "docs": [{"url": "u", "title": "Haaland doubtful with knock",
                      "seendate": "2025-03-08", "source": "ex.com", "body": "Short body."}]}


def test_market_never_in_any_prompt():
    for condition in CONDITIONS:
        system, user = build_prompt(_row(), _well(), condition)
        blob = system + user
        assert "0.55" not in blob and "market" not in blob.lower()


def test_stats_condition_has_elo_no_news():
    _, user = build_prompt(_row(), _well(), "stats")
    assert "2100" in user and "Haaland" not in user


def test_news_condition_has_news_no_elo():
    _, user = build_prompt(_row(), _well(), "news")
    assert "Haaland" in user and "2100" not in user


def test_both_condition_has_both():
    _, user = build_prompt(_row(), _well(), "both")
    assert "Haaland" in user and "2100" in user


def test_news_condition_requires_well():
    with pytest.raises(ValueError):
        build_prompt(_row(), None, "news")


def test_forecast_one_normalizes_and_picks():
    client = MagicMock()
    client.model = "test-model"
    client.chat_json.return_value = {"p_home": 0.9, "p_draw": 0.3, "p_away": 0.0}
    out = forecast_one(_row(), _well(), "both", client)
    total = out["p_home"] + out["p_draw"] + out["p_away"]
    assert abs(total - 1.0) < 1e-9
    assert out["p_away"] > 0.0  # clamped, not zero
    assert out["pick"] == "home"
    assert out["condition"] == "both" and out["model"] == "test-model"
