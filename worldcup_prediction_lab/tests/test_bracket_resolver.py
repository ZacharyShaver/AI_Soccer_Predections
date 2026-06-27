"""Tests for the knockout bracket resolver."""

from __future__ import annotations

import pandas as pd

from wc_predictor.bracket_resolver import (
    _result_index,
    group_standings,
    resolve_bracket,
)


def _results(rows):
    return pd.DataFrame(
        rows, columns=["date", "home_team_id", "away_team_id", "home_score", "away_score"]
    )


def _group_fixture(group, home, away, date, num):
    return {
        "fixture_id": f"g{num}",
        "stage": "group",
        "group": group,
        "home_team_id": home,
        "away_team_id": away,
        "home_slot": pd.NA,
        "away_slot": pd.NA,
        "match_date": date,
        "venue": "X",
        "match_number": pd.NA,
    }


def _ko(num, stage, home_slot, away_slot, date):
    return {
        "fixture_id": f"k{num}",
        "stage": stage,
        "group": pd.NA,
        "home_team_id": pd.NA,
        "away_team_id": pd.NA,
        "home_slot": home_slot,
        "away_slot": away_slot,
        "match_date": date,
        "venue": "X",
        "match_number": num,
    }


# A complete 4-team round robin for one group with a clean, unambiguous order.
def _round_robin(group, teams, scores, base="2026-06-2"):
    # scores: dict (i,j)->(gi,gj) for i<j meaning teams[i] vs teams[j]
    fx, res = [], []
    n = 1
    for (i, j), (gi, gj) in scores.items():
        date = f"{base}{n}"  # distinct dates 2026-06-21..
        fx.append(_group_fixture(group, teams[i], teams[j], date, f"{group}{n}"))
        res.append((date, teams[i], teams[j], gi, gj))
        n += 1
    return fx, res


def test_group_standings_orders_by_points_then_gd_then_gf():
    teams = ["T1", "T2", "T3", "T4"]
    # T1 wins all; T2 beats T3,T4; T3 beats T4.
    scores = {
        (0, 1): (1, 0), (0, 2): (2, 0), (0, 3): (3, 0),
        (1, 2): (1, 0), (1, 3): (2, 0),
        (2, 3): (1, 0),
    }
    fx, res = _round_robin("A", teams, scores)
    gf = pd.DataFrame(fx)
    gf["match_date"] = pd.to_datetime(gf["match_date"])
    standings = group_standings(gf, _result_index(_results(res)))
    assert [r.team_id for r in standings["A"]] == ["T1", "T2", "T3", "T4"]


def test_incomplete_group_is_not_ranked():
    teams = ["T1", "T2", "T3", "T4"]
    scores = {
        (0, 1): (1, 0), (0, 2): (2, 0), (0, 3): (3, 0),
        (1, 2): (1, 0), (1, 3): (2, 0), (2, 3): (1, 0),
    }
    fx, res = _round_robin("A", teams, scores)
    gf = pd.DataFrame(fx)
    gf["match_date"] = pd.to_datetime(gf["match_date"])
    # All six fixtures exist, but only four have been played -> group incomplete.
    standings = group_standings(gf, _result_index(_results(res[:4])))
    assert "A" not in standings


def test_resolve_group_slots_and_winner_propagation():
    # Two complete groups A and B.
    ta = ["A1", "A2", "A3", "A4"]
    tb = ["B1", "B2", "B3", "B4"]
    sc = {
        (0, 1): (1, 0), (0, 2): (1, 0), (0, 3): (1, 0),
        (1, 2): (1, 0), (1, 3): (1, 0), (2, 3): (1, 0),
    }
    fxa, resa = _round_robin("A", ta, sc, base="2026-06-2")
    fxb, resb = _round_robin("B", tb, sc, base="2026-06-1")
    # R32: 1A v 2B (match 73); R16: winner of 73 plays nobody here, but test L/W.
    ko1 = _ko(73, "round_of_32", "1A", "2B", "2026-06-28")
    ko2 = _ko(74, "round_of_32", "2A", "1B", "2026-06-28")
    ko3 = _ko(89, "round_of_16", "W73", "L74", "2026-07-01")
    fixtures = pd.DataFrame(fxa + fxb + [ko1, ko2, ko3])
    results = _results(resa + resb)

    resolved, summary = resolve_bracket(fixtures, results)
    by_num = {int(r.match_number): r for r in resolved.itertuples() if pd.notna(r.match_number)}

    # 1A = A1 (group A winner), 2B = B2 (group B runner-up).
    assert by_num[73].home_team_id == "A1"
    assert by_num[73].away_team_id == "B2"
    # 2A = A2, 1B = B1.
    assert by_num[74].home_team_id == "A2"
    assert by_num[74].away_team_id == "B1"
    assert summary["complete_groups"] == 2

    # Propagation needs match 73/74 to be played; add those results and re-resolve.
    played = _results(
        resa + resb + [
            ("2026-06-28", "A1", "B2", 2, 0),  # W73 = A1
            ("2026-06-28", "A2", "B1", 0, 1),  # L74 = A2 (B1 won)
        ]
    )
    resolved2, _ = resolve_bracket(fixtures, played)
    by_num2 = {int(r.match_number): r for r in resolved2.itertuples() if pd.notna(r.match_number)}
    assert by_num2[89].home_team_id == "A1"  # W73
    assert by_num2[89].away_team_id == "A2"  # L74


def test_resolve_is_noop_without_knockout_rows():
    teams = ["T1", "T2", "T3", "T4"]
    sc = {
        (0, 1): (1, 0), (0, 2): (1, 0), (0, 3): (1, 0),
        (1, 2): (1, 0), (1, 3): (1, 0), (2, 3): (1, 0),
    }
    fx, res = _round_robin("A", teams, sc)
    fixtures = pd.DataFrame(fx)
    resolved, summary = resolve_bracket(fixtures, _results(res))
    assert summary["knockout_total"] == 0
    assert len(resolved) == len(fixtures)
