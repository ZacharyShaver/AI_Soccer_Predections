from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.lab import registry
from wc_predictor.lab.variants.squad_value import SquadValueEloModel


def _match(mid, date, home, away, home_score, away_score):
    return {
        "match_id": mid,
        "date": date,
        "home_team_id": home,
        "away_team_id": away,
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "neutral": False,
        "occurrence_index": 0,
        "tournament": "Friendly",
    }


TRAIN = pd.DataFrame(
    [
        _match("m1", "2020-01-01", "alpha", "beta", 3, 0),
        _match("m2", "2020-01-08", "beta", "alpha", 0, 2),
    ]
)


def test_registry_discovers_dc_squad_fusion():
    assert "dc_squad_fusion" in registry.discover()


def test_elo_leg_is_squad_value_model():
    model = registry.build("dc_squad_fusion", generated_at_utc="2026-07-02T00:00:00Z")
    assert isinstance(model.elo, SquadValueEloModel)
    assert model.dixon_coles.model_id.startswith("dixon_coles")


def test_fused_probabilities_are_valid():
    model = registry.build("dc_squad_fusion", generated_at_utc="2026-07-02T00:00:00Z")
    model.fit(TRAIN)
    pred = model.predict_match(pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0)))
    probs = (pred.prob_home, pred.prob_draw, pred.prob_away)
    assert sum(probs) == pytest.approx(1.0, abs=1e-9)
    assert all(0.0 < p < 1.0 for p in probs)
    assert pred.prob_home > pred.prob_away  # alpha dominated the training data


def test_differs_from_dc_elo_fusion_only_via_squad_signal():
    """With no squad data loaded for these synthetic teams, the two fusions agree."""

    base = registry.build("dc_elo_fusion", generated_at_utc="2026-07-02T00:00:00Z")
    stacked = registry.build("dc_squad_fusion", generated_at_utc="2026-07-02T00:00:00Z")
    base.fit(TRAIN)
    stacked.fit(TRAIN)
    row = pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0))
    b, s = base.predict_match(row), stacked.predict_match(row)
    assert s.prob_home == pytest.approx(b.prob_home, abs=1e-9)
    assert s.prob_draw == pytest.approx(b.prob_draw, abs=1e-9)
