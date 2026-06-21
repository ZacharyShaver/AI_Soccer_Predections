import pytest
import pandas as pd

from wc_predictor.models.elo import elo_model


def _match(
    match_id,
    date,
    home_team_id,
    away_team_id,
    home_score,
    away_score,
    *,
    tournament="Friendly",
    neutral=False,
    occurrence_index=0,
    country="",
):
    return {
        "match_id": match_id,
        "date": date,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team": home_team_id,
        "away_team": away_team_id,
        "home_score": home_score,
        "away_score": away_score,
        "tournament": tournament,
        "neutral": neutral,
        "occurrence_index": occurrence_index,
        "country": country,
    }


def _fixture(home_team_id="alpha", away_team_id="beta", *, neutral=True, country=""):
    return pd.Series(
        {
            "match_id": "fixture-1",
            "date": "2026-06-01",
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_team": home_team_id,
            "away_team": away_team_id,
            "tournament": "Friendly",
            "neutral": neutral,
            "country": country,
            "occurrence_index": 0,
        }
    )


def test_home_win_increases_winner_and_decreases_loser_by_same_magnitude():
    model = elo_model(k_factor=20.0, home_advantage=0.0, tournament_weights={"Friendly": 1.0})

    model.fit(pd.DataFrame([_match("m1", "2026-01-01", "alpha", "beta", 1, 0)]))

    assert model.get_rating("alpha") > model.base_rating
    assert model.get_rating("beta") < model.base_rating
    assert model.get_rating("alpha") - model.base_rating == pytest.approx(
        model.base_rating - model.get_rating("beta")
    )


def test_draw_moves_higher_rated_team_down_by_less_than_decisive_result():
    setup = pd.DataFrame(
        [_match("setup", "2026-01-01", "strong", "weak", 3, 0)]
    )
    decisive = pd.DataFrame(
        [
            _match("setup", "2026-01-01", "strong", "weak", 3, 0),
            _match("decisive", "2026-01-02", "strong", "weak", 1, 0),
        ]
    )
    draw = pd.DataFrame(
        [
            _match("setup", "2026-01-01", "strong", "weak", 3, 0),
            _match("draw", "2026-01-02", "strong", "weak", 1, 1),
        ]
    )
    config = {
        "k_factor": 20.0,
        "home_advantage": 0.0,
        "tournament_weights": {"Friendly": 1.0},
    }

    before = elo_model(**config).fit(setup)
    decisive_model = elo_model(**config).fit(decisive)
    draw_model = elo_model(**config).fit(draw)

    decisive_change = decisive_model.get_rating("strong") - before.get_rating("strong")
    draw_change = draw_model.get_rating("strong") - before.get_rating("strong")

    assert draw_model.get_rating("strong") < before.get_rating("strong")
    assert draw_model.get_rating("weak") > before.get_rating("weak")
    assert abs(draw_change) < abs(decisive_change)


def test_home_advantage_respects_neutral_flag_when_predicting():
    model = elo_model(home_advantage=100.0).fit(pd.DataFrame())

    neutral_alpha_home = model.predict_match(
        _fixture("alpha", "beta", neutral=True)
    )
    neutral_beta_home = model.predict_match(
        _fixture("beta", "alpha", neutral=True)
    )
    non_neutral_alpha_home = model.predict_match(
        _fixture("alpha", "beta", neutral=False)
    )

    assert neutral_alpha_home.prob_home == pytest.approx(neutral_beta_home.prob_away)
    assert neutral_alpha_home.prob_draw == pytest.approx(neutral_beta_home.prob_draw)
    assert neutral_alpha_home.prob_away == pytest.approx(neutral_beta_home.prob_home)
    assert non_neutral_alpha_home.prob_home > neutral_alpha_home.prob_home


def test_home_advantage_can_be_applied_by_host_hook_for_neutral_fixtures():
    model = elo_model(
        home_advantage=100.0,
        host_advantage_fn=lambda match_row, home_team_id, away_team_id: "home",
    ).fit(pd.DataFrame())

    hosted = model.predict_match(_fixture("usa", "canada", neutral=True, country="USA"))
    neutral = elo_model(home_advantage=100.0).fit(pd.DataFrame()).predict_match(
        _fixture("usa", "canada", neutral=True, country="USA")
    )

    assert hosted.prob_home > neutral.prob_home


def test_goal_difference_scaling_makes_bigger_margin_update_larger():
    one_goal = elo_model(k_factor=20.0, home_advantage=0.0).fit(
        pd.DataFrame([_match("m1", "2026-01-01", "alpha", "beta", 1, 0)])
    )
    big_margin = elo_model(k_factor=20.0, home_advantage=0.0).fit(
        pd.DataFrame([_match("m1", "2026-01-01", "alpha", "beta", 4, 0)])
    )

    assert big_margin.get_rating("alpha") - big_margin.base_rating > (
        one_goal.get_rating("alpha") - one_goal.base_rating
    )


def test_processing_same_match_sequence_twice_is_deterministic():
    matches = pd.DataFrame(
        [
            _match("m2", "2026-01-02", "beta", "gamma", 0, 0),
            _match("m1", "2026-01-01", "alpha", "beta", 2, 0),
            _match("m3", "2026-01-02", "alpha", "gamma", 1, 3, occurrence_index=1),
        ]
    )

    first = elo_model().fit(matches)
    second = elo_model().fit(matches)

    assert first.ratings == second.ratings
    assert first.last_updated == second.last_updated


def test_predict_match_returns_normalized_home_draw_away_probabilities():
    model = elo_model().fit(
        pd.DataFrame([_match("m1", "2026-01-01", "alpha", "beta", 2, 0)])
    )

    prediction = model.predict_match(_fixture("alpha", "gamma", neutral=True))

    assert prediction.prob_home + prediction.prob_draw + prediction.prob_away == pytest.approx(1.0)
    assert 0.0 <= prediction.prob_home <= 1.0
    assert 0.0 <= prediction.prob_draw <= 1.0
    assert 0.0 <= prediction.prob_away <= 1.0
