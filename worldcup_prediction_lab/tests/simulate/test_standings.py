"""Tests for group standings + FIFA tiebreakers (P4 / S0)."""

import pandas as pd

from wc_predictor.simulate.standings import compute_group_table


def _matches(rows):
    return pd.DataFrame(
        rows, columns=["home_team_id", "away_team_id", "home_score", "away_score"]
    )


def test_basic_points_and_goal_columns():
    # A beats B 2-0; A and B otherwise idle (single match group).
    table = compute_group_table(_matches([("A", "B", 2, 0)]))
    by_team = {r.team_id: r for r in table.itertuples(index=False)}
    assert by_team["A"].points == 3 and by_team["A"].gf == 2 and by_team["A"].gd == 2
    assert by_team["B"].points == 0 and by_team["B"].ga == 2 and by_team["B"].gd == -2
    assert by_team["A"].rank == 1 and by_team["B"].rank == 2


def test_goal_difference_breaks_equal_points():
    # A and B both win their two non-mutual games and draw each other,
    # but A has a much bigger goal difference.
    table = compute_group_table(
        _matches(
            [
                ("A", "B", 0, 0),
                ("A", "C", 3, 0),
                ("A", "D", 3, 0),
                ("B", "C", 1, 0),
                ("B", "D", 1, 0),
                ("C", "D", 0, 0),
            ]
        )
    )
    rank = {r.team_id: r.rank for r in table.itertuples(index=False)}
    pts = {r.team_id: r.points for r in table.itertuples(index=False)}
    assert pts["A"] == pts["B"] == 7
    assert rank["A"] == 1 and rank["B"] == 2  # A wins on GD (+6 vs +2)


def test_goals_scored_breaks_equal_points_and_gd():
    # A and B both 7 pts and GD +2, but A scored more goals overall.
    table = compute_group_table(
        _matches(
            [
                ("A", "B", 1, 1),
                ("A", "C", 2, 1),
                ("A", "D", 2, 1),
                ("B", "C", 1, 0),
                ("B", "D", 1, 0),
                ("C", "D", 0, 0),
            ]
        )
    )
    rows = {r.team_id: r for r in table.itertuples(index=False)}
    assert rows["A"].points == rows["B"].points == 7
    assert rows["A"].gd == rows["B"].gd == 2
    assert rows["A"].gf == 5 and rows["B"].gf == 3
    assert rows["A"].rank == 1 and rows["B"].rank == 2  # goals scored breaks it


def test_head_to_head_breaks_equal_points_gd_and_goals():
    # A and B end identical on points(4), GD(0), GF(1); A beat B 1-0 head-to-head.
    table = compute_group_table(
        _matches(
            [
                ("A", "B", 1, 0),
                ("A", "C", 0, 0),
                ("D", "A", 1, 0),
                ("B", "C", 1, 0),
                ("B", "D", 0, 0),
                ("D", "C", 1, 0),
            ]
        )
    )
    rows = {r.team_id: r for r in table.itertuples(index=False)}
    assert rows["A"].points == rows["B"].points == 4
    assert rows["A"].gd == rows["B"].gd == 0
    assert rows["A"].gf == rows["B"].gf == 1
    # D wins the group (7 pts); A above B strictly on head-to-head.
    assert rows["D"].rank == 1
    assert rows["A"].rank == 2 and rows["B"].rank == 3
    assert rows["C"].rank == 4


def test_full_three_way_tie_is_deterministic_by_team_id():
    # Rock-paper-scissors among A,B,C (all draw D): identical on every metric
    # and head-to-head cycle -> deterministic fallback by team_id ascending.
    table = compute_group_table(
        _matches(
            [
                ("A", "B", 1, 0),
                ("B", "C", 1, 0),
                ("C", "A", 1, 0),
                ("A", "D", 0, 0),
                ("B", "D", 0, 0),
                ("C", "D", 0, 0),
            ]
        )
    )
    rows = {r.team_id: r for r in table.itertuples(index=False)}
    assert rows["A"].points == rows["B"].points == rows["C"].points == 4
    assert rows["A"].gd == rows["B"].gd == rows["C"].gd == 0
    # Stable, documented fallback: team_id ascending among the tied three.
    assert rows["A"].rank == 1 and rows["B"].rank == 2 and rows["C"].rank == 3
    assert rows["D"].rank == 4

    # Determinism: identical input (even reordered) yields identical ranking.
    shuffled = compute_group_table(
        _matches(
            [
                ("C", "A", 1, 0),
                ("B", "D", 0, 0),
                ("A", "B", 1, 0),
                ("C", "D", 0, 0),
                ("B", "C", 1, 0),
                ("A", "D", 0, 0),
            ]
        )
    )
    assert list(shuffled["team_id"]) == list(table["team_id"])
