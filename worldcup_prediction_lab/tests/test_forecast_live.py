import json
from pathlib import Path
from uuid import uuid4

import pandas as pd

from wc_predictor.forecast_live import (
    build_world_cup_host_advantage_fn,
    run_live_forecast,
    split_live_fixtures,
)


def _fixture(
    fixture_id,
    home_team_id,
    away_team_id,
    match_date,
    *,
    stage="group",
    group="A",
    venue="Toronto",
    match_number=None,
    home_slot=None,
    away_slot=None,
):
    return {
        "fixture_id": fixture_id,
        "stage": stage,
        "group": group,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_slot": home_slot,
        "away_slot": away_slot,
        "match_date": match_date,
        "venue": venue,
        "match_number": match_number,
    }


def _match(match_id, date, home_team_id, away_team_id, home_score, away_score):
    return {
        "match_id": match_id,
        "date": date,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team": home_team_id,
        "away_team": away_team_id,
        "home_score": home_score,
        "away_score": away_score,
        "tournament": "Friendly",
        "city": "",
        "country": "",
        "neutral": True,
        "source": "unit",
        "occurrence_index": 0,
    }


def test_split_live_fixtures_counts_forecast_played_and_pending_rows():
    fixtures = pd.DataFrame(
        [
            _fixture("played", "CAN", "USA", "2026-06-21"),
            _fixture("forecast", "MEX", "USA", "2026-06-22", group="B"),
            _fixture(
                "pending",
                None,
                None,
                "2026-06-28",
                stage="round_of_32",
                group=None,
                home_slot="1A",
                away_slot="2B",
            ),
        ]
    )

    split = split_live_fixtures(fixtures, as_of="2026-06-21")

    assert split.total_fixtures == 3
    assert split.forecast_count == 1
    assert split.skipped_already_played_count == 1
    assert split.skipped_knockout_pending_count == 1
    assert split.forecast_fixtures["fixture_id"].tolist() == ["forecast"]


def test_host_advantage_applies_only_to_host_team_in_its_host_country():
    host_advantage_fn = build_world_cup_host_advantage_fn()

    assert host_advantage_fn(pd.Series(_fixture("can-home", "CAN", "ARG", "2026-06-22")), "CAN", "ARG") == "home"
    assert host_advantage_fn(
        pd.Series(
            _fixture(
                "usa-real-sf-label",
                "TUR",
                "USA",
                "2026-06-25",
                venue="San Francisco Bay Area (Santa Clara)",
            )
        ),
        "TUR",
        "USA",
    ) == "away"
    assert host_advantage_fn(
        pd.Series(_fixture("usa-away", "MEX", "USA", "2026-06-22", venue="Seattle")),
        "MEX",
        "USA",
    ) == "away"
    assert (
        host_advantage_fn(
            pd.Series(_fixture("neutral-host-city", "MEX", "USA", "2026-06-22", venue="Toronto")),
            "MEX",
            "USA",
        )
        is None
    )
    assert (
        host_advantage_fn(
            pd.Series(_fixture("unknown-city", "MEX", "USA", "2026-06-22", venue="Unknown")),
            "MEX",
            "USA",
        )
        is None
    )


def test_run_live_forecast_writes_predictions_and_report_to_requested_paths():
    scratch_dir = Path("runs") / f"pytest-forecast-live-{uuid4().hex}"

    matches = pd.DataFrame(
        [
            _match("old-1", "2026-06-19", "CAN", "ARG", 2, 1),
            _match("cutoff-include", "2026-06-20", "USA", "MEX", 1, 0),
            _match("future-exclude", "2026-06-22", "ARG", "CAN", 5, 0),
        ]
    )
    fixtures = pd.DataFrame(
        [
            _fixture("played", "CAN", "USA", "2026-06-21"),
            _fixture("forecast", "USA", "MEX", "2026-06-22", venue="Seattle"),
            _fixture(
                "pending",
                None,
                None,
                "2026-06-28",
                stage="round_of_32",
                group=None,
                home_slot="1A",
                away_slot="2B",
            ),
        ]
    )
    teams = pd.DataFrame(
        [
            {"canonical_team_id": "USA", "canonical_name": "United States"},
            {"canonical_team_id": "MEX", "canonical_name": "Mexico"},
            {"canonical_team_id": "CAN", "canonical_name": "Canada"},
            {"canonical_team_id": "ARG", "canonical_name": "Argentina"},
        ]
    )

    summary = run_live_forecast(
        matches_df=matches,
        fixtures_df=fixtures,
        teams_df=teams,
        runs_dir=scratch_dir / "runs",
        reports_dir=scratch_dir / "reports",
    )

    assert summary.total_fixtures == 3
    assert summary.training_match_count == 2
    assert summary.forecast_count == 1
    assert summary.skipped_already_played_count == 1
    assert summary.skipped_knockout_pending_count == 1
    assert summary.ledger_path == scratch_dir / "runs" / "predictions" / "date=2026-06-21" / "predictions.jsonl"
    assert summary.report_path == scratch_dir / "reports" / "backtests" / "live_forecast_2026-06-21.md"

    ledger_rows = summary.ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(ledger_rows) == 1
    payload = json.loads(ledger_rows[0])
    assert payload["prediction_id"] == "elo_poisson_v1:forecast:as_of=2026-06-21"
    assert payload["match_id"] == "forecast"
    assert payload["training_cutoff"] == "2026-06-20"
    assert payload["as_of"] == "2026-06-21"
    assert payload["generated_at_utc"] == "2026-06-21T00:00:00Z"
    assert payload["scoreline_distribution"]["match_id"] == "forecast"

    report = summary.report_path.read_text(encoding="utf-8")
    assert "Elo-only" in report
    assert "United States vs Mexico" in report
    assert "pending bracket resolution" in report
