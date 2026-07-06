"""Tests for the analyst CLI's pure helpers and mode handling."""

import json
from pathlib import Path

import pytest

from wc_predictor.lab.analyst_cli import (
    _forecast_from_json,
    _researched_fixture_ids,
    main,
)


def _payload(**over):
    base = {
        "fixture_id": "fx1", "as_of": "2026-07-06", "match_date": "2026-07-06",
        "home_team_name": "Portugal", "away_team_name": "Spain",
        "p_home": 0.22, "p_draw": 0.26, "p_away": 0.52,
        "pick": "away", "pick_team": "Spain", "rationale": "r", "sources": [],
    }
    base.update(over)
    return base


def test_forecast_from_json_default_mode_agent():
    fc = _forecast_from_json(_payload())
    assert fc.mode == "agent"
    assert fc.pick == "away"
    assert abs(fc.p_home + fc.p_draw + fc.p_away - 1.0) < 1e-9


def test_forecast_from_json_agent_late_mode():
    fc = _forecast_from_json(_payload(), mode="agent_late")
    assert fc.mode == "agent_late"


def test_forecast_from_json_rejects_bad_probability_sum():
    with pytest.raises(SystemExit):
        _forecast_from_json(_payload(p_home=0.9, p_draw=0.9, p_away=0.9))


def test_record_rejects_unknown_mode():
    scratch = Path("runs/analyst/tmp/test_analyst_cli")
    scratch.mkdir(parents=True, exist_ok=True)
    p = scratch / "bad_mode_forecast.json"
    p.write_text(json.dumps(_payload()), encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["record", "--json", str(p), "--mode", "banana"])


def test_researched_fixture_ids_filters_by_mode():
    rows = [
        {"fixture_id": "a", "mode": "agent"},
        {"fixture_id": "b", "mode": "agent_late"},
        {"fixture_id": "c", "mode": "deterministic"},
    ]
    assert _researched_fixture_ids(rows, "agent") == {"a"}
    assert _researched_fixture_ids(rows, "agent_late") == {"b"}
