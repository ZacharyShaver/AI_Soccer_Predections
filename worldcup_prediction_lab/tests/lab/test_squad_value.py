from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.lab import registry
from wc_predictor.lab.variants.elo_recalibrated import recalibrated_elo_kwargs
from wc_predictor.lab.variants.squad_value import CAP, MIN_VALUED_PLAYERS, SquadValueEloModel


def _squad_rows(team_id, dates_values, valued_players=MIN_VALUED_PLAYERS):
    return [
        {
            "team_id": team_id,
            "team_name": team_id,
            "date": date,
            "squad_value_eur": value,
            "valued_players": valued_players,
        }
        for date, value in dates_values
    ]


SQUAD = pd.DataFrame(
    _squad_rows("RUR", [("2020-01-31", 100_000_000), ("2020-03-31", 150_000_000)])
    + _squad_rows("FEN", [("2020-01-31", 10_000_000)])
    + _squad_rows("THN", [("2020-01-31", 500_000_000)], valued_players=3)  # too thin
)


def _model(squad=SQUAD):
    return SquadValueEloModel(squad_values=squad, **recalibrated_elo_kwargs())


def _row(home, away, date, *, neutral=False):
    return pd.Series(
        {
            "home_team_id": home,
            "away_team_id": away,
            "home_team": home,
            "away_team": away,
            "date": date,
            "neutral": neutral,
        }
    )


def test_registry_discovers_squad_value():
    assert "squad_value" in registry.discover()


def test_value_edge_shifts_probabilities_toward_richer_side():
    with_edge = _model().predict_match(_row("RUR", "FEN", "2020-02-15"))
    without = _model(SQUAD.iloc[0:0]).predict_match(_row("RUR", "FEN", "2020-02-15"))
    assert with_edge.prob_home > without.prob_home  # 10x value ratio favors home


def test_lookup_is_strictly_before_match_date():
    model = _model()
    # Match ON the month-end date must not see that month's value.
    on_boundary = model._squad_value_delta(_row("RUR", "FEN", "2020-01-31"), "RUR", "FEN")
    after = model._squad_value_delta(_row("RUR", "FEN", "2020-02-01"), "RUR", "FEN")
    assert on_boundary == 0.0
    assert after > 0.0


def test_delta_is_capped():
    squad = pd.DataFrame(
        _squad_rows("RUR", [("2020-01-31", 1_000_000_000_000)])
        + _squad_rows("FEN", [("2020-01-31", 1)])
    )
    delta = _model(squad)._squad_value_delta(_row("RUR", "FEN", "2020-02-15"), "RUR", "FEN")
    assert delta == pytest.approx(CAP)


def test_missing_or_thin_coverage_means_no_delta():
    model = _model()
    # FEN vs unknown team -> no delta; THN has < MIN_VALUED_PLAYERS -> excluded.
    assert model._squad_value_delta(_row("FEN", "XXX", "2020-02-15"), "FEN", "XXX") == 0.0
    assert model._squad_value_delta(_row("THN", "FEN", "2020-02-15"), "THN", "FEN") == 0.0


def test_delta_applies_on_neutral_ground():
    model = _model()
    prediction = model.predict_match(_row("RUR", "FEN", "2020-02-15", neutral=True))
    flipped = model.predict_match(_row("FEN", "RUR", "2020-02-15", neutral=True))
    assert prediction.prob_home > prediction.prob_away
    assert flipped.prob_away > flipped.prob_home  # symmetric on neutral ground
