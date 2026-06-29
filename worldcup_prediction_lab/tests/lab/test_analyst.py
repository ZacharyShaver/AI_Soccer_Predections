"""Tests for the deterministic match-analyst core (packet + market-anchored forecast)."""

from __future__ import annotations

import pandas as pd

from wc_predictor.lab.analyst import (
    ContextPacket,
    build_packet,
    deterministic_analyst,
    recent_form,
    signal_delta_elo,
)


def _packet(*, market=None, form_home=0.5, form_away=0.5, altitude=0.0, elo=(0.4, 0.3, 0.3)):
    return ContextPacket(
        fixture_id="f1", as_of="2026-06-30", match_date="2026-07-01",
        home_team_id="H", away_team_id="A", home_team_name="Home", away_team_name="Away",
        venue="Test City", elo_probs=elo, elo_ratings=(1600.0, 1500.0, 75.0),
        market_probs=market, offered_prices=None,
        form_home=form_home, form_away=form_away, altitude_delta_elo=altitude,
    )


def test_market_only_returns_market():
    # No signal (form even, no altitude) → analyst == market anchor exactly.
    mkt = (0.55, 0.25, 0.20)
    fc = deterministic_analyst(_packet(market=mkt))
    assert abs(fc.p_home - 0.55) < 1e-9
    assert abs(fc.p_draw - 0.25) < 1e-9
    assert abs(fc.p_away - 0.20) < 1e-9
    assert fc.pick == "home" and fc.pick_team == "Home"
    assert fc.mode == "deterministic"


def test_form_shifts_toward_in_form_side_and_keeps_draw():
    mkt = (0.40, 0.30, 0.30)
    fc = deterministic_analyst(_packet(market=mkt, form_home=1.0, form_away=0.0))
    assert fc.p_home > 0.40  # home in form → home prob up
    assert fc.p_away < 0.30
    assert abs(fc.p_draw - 0.30) < 1e-9  # form moves H-vs-A, not the draw
    assert abs(fc.p_home + fc.p_draw + fc.p_away - 1.0) < 1e-9


def test_shift_is_capped():
    # Form alone (coef 40) maxes at 40; form + altitude is clamped to max_shift_elo.
    assert signal_delta_elo(_packet(form_home=1.0, form_away=0.0)) == 40.0
    assert signal_delta_elo(
        _packet(form_home=1.0, form_away=0.0, altitude=130.0), max_shift_elo=60.0
    ) == 60.0
    assert signal_delta_elo(
        _packet(form_home=0.0, form_away=1.0, altitude=-130.0), max_shift_elo=60.0
    ) == -60.0


def test_no_market_falls_back_to_elo():
    fc = deterministic_analyst(_packet(market=None, elo=(0.5, 0.3, 0.2)))
    assert abs(fc.p_home - 0.5) < 1e-9  # even form → elo anchor unchanged
    assert "elo" in fc.rationale


def test_probs_sum_to_one_and_pick_is_argmax():
    fc = deterministic_analyst(_packet(market=(0.2, 0.3, 0.5), form_away=1.0, form_home=0.0))
    assert abs(fc.p_home + fc.p_draw + fc.p_away - 1.0) < 1e-9
    assert fc.pick == "away" and fc.confidence == max(fc.probs)


def test_recent_form_is_as_of_bounded():
    matches = pd.DataFrame([
        # team H: a win (06-01) then a loss (06-10); both before 06-30
        {"match_id": "m1", "date": "2026-06-01", "home_team_id": "H", "away_team_id": "X",
         "home_score": 2, "away_score": 0},
        {"match_id": "m2", "date": "2026-06-10", "home_team_id": "Y", "away_team_id": "H",
         "home_score": 3, "away_score": 1},
        # a future match must be ignored (leak guard)
        {"match_id": "m3", "date": "2026-07-15", "home_team_id": "H", "away_team_id": "Z",
         "home_score": 5, "away_score": 0},
    ])
    # results before cutoff: win (1.0) + loss (0.0) -> mean 0.5
    assert recent_form(matches, "H", "2026-06-30") == 0.5
    # unknown team -> neutral
    assert recent_form(matches, "NOPE", "2026-06-30") == 0.5


def test_build_packet_reads_market_columns():
    row = pd.Series({
        "match_id": "f9", "date": "2026-07-01",
        "home_team_id": "H", "away_team_id": "A",
        "home_team": "Home", "away_team": "Away", "city": "Quito",
        "elo_prob_home": 0.5, "elo_prob_draw": 0.3, "elo_prob_away": 0.2,
        "elo_home_rating": 1600.0, "elo_away_rating": 1500.0, "elo_home_advantage": 75.0,
        "market_prob_home": 0.45, "market_prob_draw": 0.30, "market_prob_away": 0.25,
    })
    packet = build_packet(row, "2026-06-30", matches=pd.DataFrame())
    assert packet.market_probs is not None
    assert abs(sum(packet.market_probs) - 1.0) < 1e-9
    assert packet.home_team_name == "Home" and packet.venue == "Quito"
