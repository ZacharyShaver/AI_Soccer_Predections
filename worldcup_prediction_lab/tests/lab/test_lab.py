import pandas as pd
import pytest

from wc_predictor.lab import registry
from wc_predictor.lab.experiment import generate_variant_predictions, read_variant_predictions
from wc_predictor.lab.leaderboard import build_standings


def _matches():
    rows = []
    teams = ["USA", "MEX", "CAN", "ARG"]
    date = pd.Timestamp("2026-06-01")
    mid = 0
    for i, h in enumerate(teams):
        for a in teams[i + 1 :]:
            mid += 1
            rows.append({
                "match_id": f"m{mid}", "date": date + pd.Timedelta(days=mid),
                "home_team_id": h, "away_team_id": a,
                "home_score": 2, "away_score": 0,
                "tournament": "Friendly", "neutral": True, "occurrence_index": 0,
            })
    return pd.DataFrame(rows)


def _fixtures():
    return pd.DataFrame([
        {"fixture_id": "fx-played", "stage": "group", "group": "A",
         "home_team_id": "USA", "away_team_id": "MEX",
         "match_date": pd.Timestamp("2026-06-20"), "venue": "Dallas"},
        {"fixture_id": "fx1", "stage": "group", "group": "A",
         "home_team_id": "ARG", "away_team_id": "CAN",
         "match_date": pd.Timestamp("2026-06-22"), "venue": "Toronto"},
        {"fixture_id": "fx2", "stage": "group", "group": "B",
         "home_team_id": "USA", "away_team_id": "ARG",
         "match_date": pd.Timestamp("2026-06-23"), "venue": "Seattle"},
    ])


def _teams():
    return pd.DataFrame([
        {"canonical_team_id": "USA", "canonical_name": "United States"},
        {"canonical_team_id": "MEX", "canonical_name": "Mexico"},
        {"canonical_team_id": "CAN", "canonical_name": "Canada"},
        {"canonical_team_id": "ARG", "canonical_name": "Argentina"},
    ])


def test_registry_discovers_baseline():
    found = registry.discover()
    assert "elo_baseline" in found
    model = registry.build("elo_baseline", generated_at_utc="2026-06-21T00:00:00Z")
    assert hasattr(model, "fit") and hasattr(model, "predict_match")
    with pytest.raises(KeyError):
        registry.build("does_not_exist", generated_at_utc="2026-06-21T00:00:00Z")


def test_generate_predictions_only_after_as_of_and_idempotent(tmp_path):
    out = tmp_path / "experiments"
    path = generate_variant_predictions(
        "elo_baseline",
        matches_df=_matches(), fixtures_df=_fixtures(), teams_df=_teams(),
        as_of="2026-06-21", training_cutoff="2026-06-20", out_root=out,
    )
    rows = read_variant_predictions(path)
    assert path == out / "date=2026-06-21" / "elo_baseline.jsonl"
    assert sorted(r["match_id"] for r in rows) == ["fx1", "fx2"]  # fx-played excluded
    assert all(r["model_id"] == "elo_baseline" for r in rows)
    assert all(r["as_of"] == "2026-06-21" for r in rows)

    before = path.read_bytes()
    generate_variant_predictions(
        "elo_baseline",
        matches_df=_matches(), fixtures_df=_fixtures(), teams_df=_teams(),
        as_of="2026-06-21", training_cutoff="2026-06-20", out_root=out,
    )
    assert path.read_bytes() == before  # byte-identical re-write is a no-op


def test_build_standings_scores_and_ranks_against_baseline(tmp_path):
    out = tmp_path / "experiments"
    generate_variant_predictions(
        "elo_baseline",
        matches_df=_matches(), fixtures_df=_fixtures(), teams_df=_teams(),
        as_of="2026-06-21", training_cutoff="2026-06-20", out_root=out,
    )
    results = pd.DataFrame([{"match_id": "fx1", "home_score": 1, "away_score": 0}])

    standings = build_standings(experiments_root=out, results_df=results)
    by_id = {s.variant_id: s for s in standings}
    assert "elo_baseline" in by_id
    base = by_id["elo_baseline"]
    assert base.n_scored == 1
    assert base.mean_rps is not None
    assert base.edge_vs_baseline_rps == 0.0  # baseline vs itself
