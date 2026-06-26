import pandas as pd
import pytest

from wc_predictor.lab import registry
from wc_predictor.lab.experiment import generate_variant_predictions, read_variant_predictions
from wc_predictor.lab.leaderboard import build_standings, fixture_keyed_results


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


def test_registry_discovers_ensemble_top_k():
    found = registry.discover()
    assert "ensemble_top_k" in found
    model = registry.build("ensemble_top_k", generated_at_utc="2026-06-26T00:00:00Z")
    assert hasattr(model, "fit") and hasattr(model, "predict_match")


def test_ensemble_top_k_averages_component_probabilities():
    train = _matches()
    match_row = pd.Series({
        "match_id": "fx-ensemble",
        "home_team_id": "USA",
        "away_team_id": "ARG",
        "neutral": True,
        "tournament": "FIFA World Cup",
    })

    ensemble = registry.build("ensemble_top_k", generated_at_utc="2026-06-26T00:00:00Z")
    ensemble.fit(train)
    ensemble_prediction = ensemble.predict_match(match_row)

    component_ids = ("ewma_goal_form", "form_trend", "opp_adj_form")
    component_predictions = []
    for variant_id in component_ids:
        component = registry.build(variant_id, generated_at_utc="2026-06-26T00:00:00Z")
        component.fit(train)
        component_predictions.append(component.predict_match(match_row))

    expected_home = sum(p.prob_home for p in component_predictions) / len(component_predictions)
    expected_draw = sum(p.prob_draw for p in component_predictions) / len(component_predictions)
    expected_away = sum(p.prob_away for p in component_predictions) / len(component_predictions)

    assert ensemble_prediction.prob_home == pytest.approx(expected_home)
    assert ensemble_prediction.prob_draw == pytest.approx(expected_draw)
    assert ensemble_prediction.prob_away == pytest.approx(expected_away)
    assert (
        ensemble_prediction.prob_home
        + ensemble_prediction.prob_draw
        + ensemble_prediction.prob_away
    ) == pytest.approx(1.0)


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


def test_fixture_keyed_results_crosswalks_and_orients_scores():
    # martj42 stores ARG vs CAN, but the openfootball fixture has CAN at home and
    # a different (string) match_id. The crosswalk must resolve it by (pair, date)
    # and flip the score to the fixture's orientation.
    matches = pd.DataFrame([
        {"match_id": "martj42-1", "date": pd.Timestamp("2026-06-22"),
         "home_team_id": "ARG", "away_team_id": "CAN", "home_score": 3, "away_score": 1},
        {"match_id": "martj42-2", "date": pd.Timestamp("2026-06-22"),
         "home_team_id": "USA", "away_team_id": "MEX", "home_score": 0, "away_score": 0},
    ])
    fixtures = pd.DataFrame([
        # fixture orients CAN as home -> score must flip to 1-3
        {"fixture_id": "fx1", "home_team_id": "CAN", "away_team_id": "ARG",
         "match_date": pd.Timestamp("2026-06-22")},
        # same orientation as martj42 -> 0-0 unchanged
        {"fixture_id": "fx2", "home_team_id": "USA", "away_team_id": "MEX",
         "match_date": pd.Timestamp("2026-06-22")},
        # knockout placeholder (null team ids) cannot resolve
        {"fixture_id": "fx-pending", "home_team_id": None, "away_team_id": None,
         "match_date": pd.Timestamp("2026-07-01")},
        # right teams, wrong date -> no resolution
        {"fixture_id": "fx-otherday", "home_team_id": "ARG", "away_team_id": "CAN",
         "match_date": pd.Timestamp("2026-06-23")},
    ])
    resolved = fixture_keyed_results(matches, fixtures)
    by_id = {r["match_id"]: (r["home_score"], r["away_score"]) for r in resolved.to_dict("records")}
    assert by_id == {"fx1": (1, 3), "fx2": (0, 0)}


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
