"""Tests for the betting ledger: idempotent record, resolution, track record."""

from __future__ import annotations

from wc_predictor.lab.betting import BetSignal
from wc_predictor.lab.betting_ledger import (
    load_ledger,
    record_signals,
    resolve_signals,
    track_record,
)


def _sig(fixture_id, outcome, price, rec, kelly=0.04):
    return BetSignal(
        fixture_id=fixture_id, match_date="2026-06-30", venue="Mexico City",
        home_team_name="Mexico", away_team_name="Norway", outcome=outcome,
        selection="Mexico" if outcome == "home" else "Norway",
        our_prob=0.6, market_prob=0.5, offered_price=price, edge=0.1, ev=0.2,
        kelly_stake=kelly, altitude_delta_elo=130.0,
        structural="altitude" if rec == "BET" else None, recommendation=rec,
    )


def test_record_is_idempotent(tmp_path):
    path = tmp_path / "ledger.jsonl"
    sigs = [_sig("f1", "home", 0.5, "BET"), _sig("f2", "away", 0.4, "WATCH")]
    assert record_signals(sigs, as_of="2026-06-28", ledger_path=path) == 2
    # re-recording the same (fixture, outcome) adds nothing
    assert record_signals(sigs, as_of="2026-06-29", ledger_path=path) == 0
    # a new outcome on an existing fixture is a new row
    assert record_signals([_sig("f1", "draw", 0.3, "WATCH")], as_of="2026-06-29", ledger_path=path) == 1
    assert len(load_ledger(path)) == 3


def test_resolve_and_pnl():
    ledger = [
        {"fixture_id": "f1", "outcome": "home", "offered_price": 0.5, "kelly_stake": 0.04, "recommendation": "BET"},
        {"fixture_id": "f2", "outcome": "away", "offered_price": 0.4, "kelly_stake": 0.02, "recommendation": "WATCH"},
        {"fixture_id": "f3", "outcome": "home", "offered_price": 0.5, "kelly_stake": 0.0, "recommendation": "WATCH"},
    ]
    results = {"f1": (2, 0), "f2": (1, 0)}  # f1 home win (BET wins), f2 home win (WATCH away loses), f3 unresolved
    resolved = resolve_signals(ledger, results)
    by_id = {r["fixture_id"]: r for r in resolved}
    assert by_id["f1"]["won"] is True
    assert abs(by_id["f1"]["pnl_flat"] - (1 / 0.5 - 1)) < 1e-9  # +1.0
    assert by_id["f2"]["won"] is False and by_id["f2"]["pnl_flat"] == -1.0
    assert by_id["f3"]["resolved"] is False and by_id["f3"]["pnl_flat"] == 0.0


def test_track_record_aggregates():
    ledger = [
        {"fixture_id": "f1", "outcome": "home", "offered_price": 0.5, "kelly_stake": 0.04, "recommendation": "BET"},
        {"fixture_id": "f2", "outcome": "home", "offered_price": 0.25, "kelly_stake": 0.02, "recommendation": "WATCH"},
        {"fixture_id": "f3", "outcome": "home", "offered_price": 0.25, "kelly_stake": 0.02, "recommendation": "WATCH"},
    ]
    results = {"f1": (1, 0), "f2": (0, 1), "f3": (0, 1)}  # BET wins; both WATCH lose
    tr = track_record(resolve_signals(ledger, results))
    assert tr["BET"]["n"] == 1 and tr["BET"]["hits"] == 1 and tr["BET"]["roi_flat"] == 1.0
    assert tr["WATCH"]["n"] == 2 and tr["WATCH"]["hits"] == 0 and tr["WATCH"]["roi_flat"] == -1.0
