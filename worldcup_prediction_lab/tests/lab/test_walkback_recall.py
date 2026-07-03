from unittest.mock import MagicMock

import pandas as pd

from wc_predictor.lab.walkback.recall import recall_check


def _row(hs=2, aws=1):
    return pd.Series({"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
                      "date": pd.Timestamp("2025-03-10"),
                      "home_score": hs, "away_score": aws})


def _client_recalling(payload):
    client = MagicMock()
    client.chat_json.return_value = payload
    return client


def test_exact_score_recall_is_contaminated():
    client = _client_recalling({"known": True, "home_goals": 2, "away_goals": 1})
    assert recall_check(_row(), client)["contaminated"] is True


def test_string_goal_recall_is_still_contaminated():
    client = _client_recalling({"known": True, "home_goals": "2", "away_goals": "1"})
    assert recall_check(_row(), client)["contaminated"] is True


def test_correct_outcome_wrong_score_is_not_contaminated():
    client = _client_recalling({"known": True, "home_goals": 3, "away_goals": 0})
    assert recall_check(_row(), client)["contaminated"] is False


def test_unknown_is_not_contaminated():
    client = _client_recalling({"known": False, "home_goals": None, "away_goals": None})
    assert recall_check(_row(), client)["contaminated"] is False


def test_prompt_does_not_leak_the_result():
    client = _client_recalling({"known": False, "home_goals": None, "away_goals": None})
    recall_check(_row(), client)
    user_prompt = client.chat_json.call_args[0][1]
    assert "2" not in user_prompt.replace("2025", "")  # scores absent (date year allowed)
