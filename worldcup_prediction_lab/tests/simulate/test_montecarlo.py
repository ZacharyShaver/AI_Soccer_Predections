"""Tests for the Monte Carlo tournament engine (P4 / S3)."""

import numpy as np
import pandas as pd

from wc_predictor.models.elo import EloModel
from wc_predictor.simulate.montecarlo import (
    played_group_results,
    run_tournament_simulation,
)

GROUPS = list("ABCDEFGHIJKL")
_RR_PAIRS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

# Real 2026 knockout slot structure (R32 third-slots + winner/loser chain).
_KNOCKOUT = [
    (73, "round_of_32", "2A", "2B"), (74, "round_of_32", "1E", "3A/B/C/D/F"),
    (75, "round_of_32", "1F", "2C"), (76, "round_of_32", "1C", "2F"),
    (77, "round_of_32", "1I", "3C/D/F/G/H"), (78, "round_of_32", "2E", "2I"),
    (79, "round_of_32", "1A", "3C/E/F/H/I"), (80, "round_of_32", "1L", "3E/H/I/J/K"),
    (81, "round_of_32", "1D", "3B/E/F/I/J"), (82, "round_of_32", "1G", "3A/E/H/I/J"),
    (83, "round_of_32", "2K", "2L"), (84, "round_of_32", "1H", "2J"),
    (85, "round_of_32", "1B", "3E/F/G/I/J"), (86, "round_of_32", "1J", "2H"),
    (87, "round_of_32", "1K", "3D/E/I/J/L"), (88, "round_of_32", "2D", "2G"),
    (89, "round_of_16", "W74", "W77"), (90, "round_of_16", "W73", "W75"),
    (91, "round_of_16", "W76", "W78"), (92, "round_of_16", "W79", "W80"),
    (93, "round_of_16", "W83", "W84"), (94, "round_of_16", "W81", "W82"),
    (95, "round_of_16", "W86", "W88"), (96, "round_of_16", "W85", "W87"),
    (97, "quarter_final", "W89", "W90"), (98, "quarter_final", "W93", "W94"),
    (99, "quarter_final", "W91", "W92"), (100, "quarter_final", "W95", "W96"),
    (101, "semi_final", "W97", "W98"), (102, "semi_final", "W99", "W100"),
    (103, "third_place", "L101", "L102"), (104, "final", "W101", "W102"),
]


def _build_fixtures() -> pd.DataFrame:
    rows = []
    n = 1
    for g in GROUPS:
        teams = [f"{g}{i}" for i in range(1, 5)]
        for hi, ai in _RR_PAIRS:
            rows.append(
                {
                    "stage": "group", "match_number": n, "group": g,
                    "home_team_id": teams[hi], "away_team_id": teams[ai],
                    "home_slot": None, "away_slot": None, "venue": "V",
                }
            )
            n += 1
    for match_number, stage, home_slot, away_slot in _KNOCKOUT:
        rows.append(
            {
                "stage": stage, "match_number": match_number, "group": None,
                "home_team_id": None, "away_team_id": None,
                "home_slot": home_slot, "away_slot": away_slot, "venue": "V",
            }
        )
    return pd.DataFrame(rows)


def _model(overrides: dict[str, float]) -> EloModel:
    model = EloModel()
    model.ratings = dict(overrides)
    return model


def test_played_group_results_uses_unordered_pairs_and_as_of():
    fixtures = _build_fixtures()
    matches = pd.DataFrame(
        [
            # A1 v A2 is a real group pair (played, in window)
            {"tournament": "FIFA World Cup", "date": "2026-06-12", "home_team_id": "A2", "away_team_id": "A1", "home_score": 0, "away_score": 3},
            # out of window -> excluded
            {"tournament": "FIFA World Cup", "date": "2026-07-01", "home_team_id": "B1", "away_team_id": "B2", "home_score": 1, "away_score": 1},
            # not a World Cup match -> excluded
            {"tournament": "Friendly", "date": "2026-06-12", "home_team_id": "C1", "away_team_id": "C2", "home_score": 2, "away_score": 2},
        ]
    )
    played = played_group_results(matches, fixtures, as_of="2026-06-21")
    assert played == {frozenset(("A1", "A2")): {"A2": 0, "A1": 3}}


def test_degenerate_strong_team_advances_always_and_usually_wins():
    fixtures = _build_fixtures()
    model = _model({"A1": 6000.0})  # everyone else defaults to base rating
    table = run_tournament_simulation(model, pd.DataFrame(columns=["tournament", "date", "home_team_id", "away_team_id", "home_score", "away_score"]), fixtures, n_sims=200, seed=0)

    assert len(table) == 48
    a1 = table[table["team_id"] == "A1"].iloc[0]
    assert a1["p_advance"] == 1.0          # always tops its group
    assert a1["p_win"] > 0.95              # dominant favourite wins almost always


def test_round_probabilities_are_nested_and_bounded():
    fixtures = _build_fixtures()
    model = _model({"A1": 2200.0, "B1": 2000.0, "C1": 1900.0})
    table = run_tournament_simulation(model, pd.DataFrame(columns=["tournament", "date", "home_team_id", "away_team_id", "home_score", "away_score"]), fixtures, n_sims=300, seed=1)

    for r in table.itertuples(index=False):
        for p in (r.p_advance, r.p_r16, r.p_qf, r.p_sf, r.p_final, r.p_win):
            assert 0.0 <= p <= 1.0
        # each deeper round is a subset of the previous
        assert r.p_win <= r.p_final <= r.p_sf <= r.p_qf <= r.p_r16 <= r.p_advance

    # exactly one champion per simulation -> win probabilities sum to 1
    assert abs(table["p_win"].sum() - 1.0) < 1e-9
    # 32 of 48 advance each sim -> advance probabilities sum to 32
    assert abs(table["p_advance"].sum() - 32.0) < 1e-9


def test_simulation_is_reproducible_for_a_fixed_seed():
    fixtures = _build_fixtures()
    empty = pd.DataFrame(columns=["tournament", "date", "home_team_id", "away_team_id", "home_score", "away_score"])
    model = _model({"A1": 2200.0, "F2": 2050.0})
    t1 = run_tournament_simulation(model, empty, fixtures, n_sims=150, seed=7)
    t2 = run_tournament_simulation(model, empty, fixtures, n_sims=150, seed=7)
    pd.testing.assert_frame_equal(t1, t2)
