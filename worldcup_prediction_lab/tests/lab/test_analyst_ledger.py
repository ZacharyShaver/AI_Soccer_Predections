"""Tests for the analyst ledger: idempotent record, resolution, track record, calibration."""

from __future__ import annotations

from wc_predictor.lab.analyst import AnalystForecast
from wc_predictor.lab.analyst_ledger import (
    calibration_summary,
    load_ledger,
    record_forecast,
    resolve_forecasts,
    track_record,
)


def _fc(fid, probs, pick, *, mode="deterministic"):
    return AnalystForecast(
        fixture_id=fid, as_of="2026-06-30", match_date="2026-07-01",
        home_team_name="Home", away_team_name="Away",
        p_home=probs[0], p_draw=probs[1], p_away=probs[2],
        pick=pick, pick_team="Home" if pick == "home" else "Away",
        confidence=max(probs), rationale="t", sources=["elo"], mode=mode,
    )


def test_record_is_idempotent(tmp_path):
    path = tmp_path / "ledger.jsonl"
    fcs = [_fc("f1", (0.6, 0.25, 0.15), "home"), _fc("f2", (0.2, 0.3, 0.5), "away")]
    assert record_forecast(fcs, as_of="2026-06-30", ledger_path=path) == 2
    # re-recording the same fixtures adds nothing (first sighting wins)
    assert record_forecast(fcs, as_of="2026-07-01", ledger_path=path) == 0
    assert len(load_ledger(path)) == 2


def test_record_freezes_baselines(tmp_path):
    path = tmp_path / "ledger.jsonl"
    record_forecast(
        [_fc("f1", (0.6, 0.25, 0.15), "home")], as_of="2026-06-30",
        elo_probs={"f1": (0.5, 0.3, 0.2)}, market_probs={"f1": (0.55, 0.25, 0.20)},
        ledger_path=path,
    )
    row = load_ledger(path)[0]
    assert row["elo_probs"] == [0.5, 0.3, 0.2]
    assert row["market_probs"] == [0.55, 0.25, 0.20]


def test_resolve_and_track():
    ledger = [
        {"fixture_id": "f1", "mode": "deterministic", "pick": "home",
         "p_home": 0.6, "p_draw": 0.25, "p_away": 0.15,
         "elo_probs": [0.5, 0.3, 0.2], "market_probs": [0.55, 0.25, 0.20]},
        {"fixture_id": "f2", "mode": "deterministic", "pick": "away",
         "p_home": 0.2, "p_draw": 0.3, "p_away": 0.5},  # pending
    ]
    results = {"f1": (2, 0)}  # home win → pick correct
    resolved = resolve_forecasts(ledger, results)
    by = {r["fixture_id"]: r for r in resolved}
    assert by["f1"]["resolved"] is True and by["f1"]["correct"] is True
    assert by["f1"]["rps"] is not None and by["f1"]["elo_rps"] is not None
    assert by["f2"]["resolved"] is False

    tr = track_record(resolved)
    assert tr["deterministic"]["n"] == 1
    assert tr["deterministic"]["accuracy"] == 1.0
    assert tr["deterministic"]["pending"] == 1
    # analyst (0.6 on home) is sharper than elo (0.5) on a home win → vs_elo negative
    assert tr["deterministic"]["vs_elo"] < 0


def test_calibration_summary_needs_history():
    # < 10 resolved rows → no recalibration, temp stays 1.0
    out = calibration_summary([{"resolved": True, "mode": "deterministic",
                                "p_home": 0.6, "p_draw": 0.25, "p_away": 0.15,
                                "actual": "home"}])
    assert out["fitted"] is False and out["temp"] == 1.0


def _agent_ledger_row(fid, home, probs, mkt, pick):
    return {
        "fixture_id": fid, "mode": "agent", "match_date": "2026-07-02",
        "home_team_name": home, "away_team_name": "Opp",
        "p_home": probs[0], "p_draw": probs[1], "p_away": probs[2],
        "pick": pick, "pick_team": home, "market_probs": list(mkt),
    }


def test_agent_record_summary_classifies_deviations():
    from wc_predictor.lab.analyst_ledger import agent_record_summary, resolve_forecasts

    ledger = [
        # deviated 5pts toward home; home happened -> helped
        _agent_ledger_row("f1", "Alpha", (0.60, 0.25, 0.15), (0.55, 0.27, 0.18), "home"),
        # no deviation -> neutral
        _agent_ledger_row("f2", "Beta", (0.30, 0.30, 0.40), (0.30, 0.30, 0.40), "away"),
    ]
    resolved = resolve_forecasts(ledger, {"f1": (2, 0), "f2": (0, 1)})
    rec = agent_record_summary(resolved)

    assert rec["mode"] == "agent"
    assert rec["n_resolved"] == 2
    assert rec["hits"] == 2
    assert rec["vs_market"] < 0  # beat the market on this pair
    d1 = next(d for d in rec["deviations"] if d["fixture"].startswith("Alpha"))
    d2 = next(d for d in rec["deviations"] if d["fixture"].startswith("Beta"))
    assert d1["toward"] == "home" and d1["outcome"] == "helped"
    assert abs(d1["size_pts"] - 5.0) < 0.01
    assert d2["outcome"] == "neutral"


def test_agent_record_summary_empty_history_has_caution():
    from wc_predictor.lab.analyst_ledger import agent_record_summary

    rec = agent_record_summary([])
    assert rec["n_resolved"] == 0
    assert rec["deviations"] == []
    assert "anecdote" in rec["caution"]


def test_agent_record_summary_ignores_other_modes_and_unresolved():
    from wc_predictor.lab.analyst_ledger import agent_record_summary, resolve_forecasts

    ledger = [
        {**_agent_ledger_row("f1", "Alpha", (0.5, 0.3, 0.2), (0.5, 0.3, 0.2), "home"),
         "mode": "deterministic"},
        _agent_ledger_row("f2", "Beta", (0.5, 0.3, 0.2), (0.5, 0.3, 0.2), "home"),
    ]
    resolved = resolve_forecasts(ledger, {"f1": (1, 0)})  # f2 unresolved
    rec = agent_record_summary(resolved)
    assert rec["n_resolved"] == 0
