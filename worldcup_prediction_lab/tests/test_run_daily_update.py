import json
from pathlib import Path

import pandas as pd

from wc_predictor.data.ingest_international_results import _write_parquet
from wc_predictor.run_daily_update import run_daily_update


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


def _write_silver_inputs(silver_dir: Path, *, fixtures: list[dict[str, object]]) -> None:
    silver_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(
        pd.DataFrame(
            [
                _match("old-1", "2026-06-19", "CAN", "ARG", 2, 1),
                _match("cutoff-include", "2026-06-20", "USA", "MEX", 1, 0),
                _match("later-result", "2026-06-22", "ARG", "CAN", 0, 0),
            ]
        ),
        silver_dir / "martj42_matches.parquet",
    )
    _write_parquet(
        pd.DataFrame(fixtures),
        silver_dir / "openfootball_worldcup_2026_fixtures.parquet",
    )
    _write_parquet(
        pd.DataFrame(
            [
                {"canonical_team_id": "USA", "canonical_name": "United States"},
                {"canonical_team_id": "MEX", "canonical_name": "Mexico"},
                {"canonical_team_id": "CAN", "canonical_name": "Canada"},
                {"canonical_team_id": "ARG", "canonical_name": "Argentina"},
            ]
        ),
        silver_dir / "martj42_teams.parquet",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_run_daily_update_is_idempotent_and_preserves_prior_as_of_partitions(tmp_path):
    silver_dir = tmp_path / "silver"
    runs_dir = tmp_path / "runs"
    reports_dir = tmp_path / "reports"
    _write_silver_inputs(
        silver_dir,
        fixtures=[
            _fixture("played", "CAN", "USA", "2026-06-21"),
            _fixture("forecast-1", "USA", "MEX", "2026-06-22", venue="Seattle"),
            _fixture("forecast-2", "ARG", "CAN", "2026-06-23", group="B"),
        ],
    )

    first_summary = run_daily_update(
        as_of="2026-06-21",
        silver_dir=silver_dir,
        runs_dir=runs_dir,
        reports_dir=reports_dir,
        refresh_results=False,
        refresh_odds=False,
    )
    first_partition = runs_dir / "predictions" / "date=2026-06-21" / "predictions.jsonl"
    first_bytes = first_partition.read_bytes()
    first_rows = _read_jsonl(first_partition)

    second_summary = run_daily_update(
        as_of="2026-06-21",
        silver_dir=silver_dir,
        runs_dir=runs_dir,
        reports_dir=reports_dir,
        refresh_results=False,
        refresh_odds=False,
    )
    second_rows = _read_jsonl(first_partition)

    assert first_summary.as_of == "2026-06-21"
    assert first_summary.training_cutoff == "2026-06-20"
    assert first_summary.forecast_count == 2
    assert first_summary.ledger_path == first_partition
    assert first_summary.report_path == reports_dir / "backtests" / "live_forecast_2026-06-21.md"
    assert second_summary.forecast_count == 2
    assert first_partition.read_bytes() == first_bytes
    assert second_rows == first_rows
    assert [row["match_id"] for row in first_rows] == ["forecast-1", "forecast-2"]
    assert all(row["match_id"] != "played" for row in first_rows)
    assert len({row["prediction_id"] for row in first_rows}) == len(first_rows)
    assert all(row["as_of"] == "2026-06-21" for row in first_rows)
    assert all(row["generated_at_utc"] == "2026-06-21T00:00:00Z" for row in first_rows)

    next_summary = run_daily_update(
        as_of="2026-06-22",
        silver_dir=silver_dir,
        runs_dir=runs_dir,
        reports_dir=reports_dir,
        refresh_results=False,
        refresh_odds=False,
    )
    next_partition = runs_dir / "predictions" / "date=2026-06-22" / "predictions.jsonl"

    assert next_summary.as_of == "2026-06-22"
    assert next_summary.training_cutoff == "2026-06-22"
    assert next_summary.forecast_count == 1
    assert first_partition.read_bytes() == first_bytes
    assert next_partition.exists()
    assert [row["match_id"] for row in _read_jsonl(next_partition)] == ["forecast-2"]


def test_run_daily_update_skips_gracefully_when_no_fixtures_are_after_as_of(tmp_path):
    silver_dir = tmp_path / "silver"
    runs_dir = tmp_path / "runs"
    reports_dir = tmp_path / "reports"
    _write_silver_inputs(
        silver_dir,
        fixtures=[
            _fixture("played-1", "CAN", "USA", "2026-06-21"),
            _fixture("played-2", "USA", "MEX", "2026-06-22", venue="Seattle"),
        ],
    )

    summary = run_daily_update(
        as_of="2026-06-22",
        silver_dir=silver_dir,
        runs_dir=runs_dir,
        reports_dir=reports_dir,
        refresh_results=False,
        refresh_odds=False,
    )
    partition = runs_dir / "predictions" / "date=2026-06-22" / "predictions.jsonl"

    assert summary.as_of == "2026-06-22"
    assert summary.training_cutoff == "2026-06-22"
    assert summary.forecast_count == 0
    assert summary.ledger_path == partition
    assert not partition.exists() or partition.read_text(encoding="utf-8") == ""
