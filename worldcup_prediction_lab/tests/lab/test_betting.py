"""Tests for the betting disagreement engine (pure logic)."""

from __future__ import annotations

from wc_predictor.lab.betting import (
    BetSignal,
    evaluate_fixture,
    kelly_fraction,
    rank_signals,
)

META = {
    "fixture_id": "f1",
    "match_date": "2026-06-30",
    "venue": "Mexico City",
    "home_team_name": "Mexico",
    "away_team_name": "Norway",
}


def test_kelly_basic_and_cap():
    # p=0.6, price=0.5 -> full Kelly (0.6-0.5)/(1-0.5)=0.2 ; quarter -> 0.05
    assert abs(kelly_fraction(0.6, 0.5, 0.25) - 0.05) < 1e-9
    # negative edge -> 0
    assert kelly_fraction(0.4, 0.5, 0.25) == 0.0
    # huge edge is capped at KELLY_CAP (0.05)
    assert kelly_fraction(0.95, 0.5, 1.0) == 0.05


def test_altitude_backed_disagreement_becomes_BET():
    # Altitude lifts our home prob above the offered price; delta supports home.
    base = (0.45, 0.27, 0.28)
    alt = (0.58, 0.24, 0.18)  # altitude-adjusted home up
    devig = (0.46, 0.27, 0.27)
    offered = (0.47, 0.28, 0.28)  # offered home price 0.47 < our 0.58 -> +EV
    sig = evaluate_fixture(META, base, alt, devig, offered, altitude_delta_elo=130.0)
    bet = [s for s in sig if s.outcome == "home"]
    assert bet and bet[0].recommendation == "BET"
    assert bet[0].structural == "altitude"
    assert bet[0].our_prob == 0.58  # used the altitude-adjusted prob
    assert bet[0].ev > 0 and bet[0].kelly_stake > 0


def test_disagreement_without_altitude_is_WATCH_only():
    base = (0.60, 0.22, 0.18)     # we love the home team
    alt = base                    # no altitude move
    devig = (0.50, 0.25, 0.25)
    offered = (0.51, 0.26, 0.26)  # +EV on home (0.60>0.51) but NO structural reason
    sig = evaluate_fixture(META, base, alt, devig, offered, altitude_delta_elo=0.0)
    home = [s for s in sig if s.outcome == "home"]
    assert home and home[0].recommendation == "WATCH"
    assert home[0].structural is None


def test_small_edge_or_negative_ev_produces_no_signal():
    base = (0.50, 0.25, 0.25)
    devig = (0.49, 0.255, 0.255)
    offered = (0.49, 0.255, 0.255)  # edge ~0.01 < threshold 0.04
    assert evaluate_fixture(META, base, base, devig, offered, 0.0) == []
    # negative EV: our prob below offered price
    offered2 = (0.62, 0.20, 0.20)
    assert evaluate_fixture(META, (0.55, 0.25, 0.20), (0.55, 0.25, 0.20), (0.50, 0.25, 0.25), offered2, 0.0) == []


def test_rank_puts_bets_first_then_by_ev():
    s_watch = BetSignal("f", "d", "v", "A", "B", "home", "A", 0.6, 0.5, 0.5, 0.1, 0.2, 0.02, 0.0, None, "WATCH")
    s_bet_lo = BetSignal("f", "d", "v", "A", "B", "away", "B", 0.55, 0.45, 0.45, 0.1, 0.22, 0.02, -130, "altitude", "BET")
    s_bet_hi = BetSignal("f", "d", "v", "A", "B", "home", "A", 0.6, 0.4, 0.45, 0.2, 0.33, 0.03, 130, "altitude", "BET")
    ranked = rank_signals([s_watch, s_bet_lo, s_bet_hi])
    assert [s.recommendation for s in ranked] == ["BET", "BET", "WATCH"]
    assert ranked[0] is s_bet_hi  # higher EV bet first
