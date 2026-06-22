"""Tests for third-place allocation + bracket resolution (P4 / S1)."""

import pandas as pd
import pytest

from wc_predictor.simulate.bracket import (
    allocate_thirds,
    parse_third_place_slots,
    rank_third_placed,
    resolve_round_of_32,
)

# The real 2026 Round-of-32 slots (from openfootball silver fixtures).
R32_ROWS = [
    (73, "2A", "2B"),
    (74, "1E", "3A/B/C/D/F"),
    (75, "1F", "2C"),
    (76, "1C", "2F"),
    (77, "1I", "3C/D/F/G/H"),
    (78, "2E", "2I"),
    (79, "1A", "3C/E/F/H/I"),
    (80, "1L", "3E/H/I/J/K"),
    (81, "1D", "3B/E/F/I/J"),
    (82, "1G", "3A/E/H/I/J"),
    (83, "2K", "2L"),
    (84, "1H", "2J"),
    (85, "1B", "3E/F/G/I/J"),
    (86, "1J", "2H"),
    (87, "1K", "3D/E/I/J/L"),
    (88, "2D", "2G"),
]

REAL_SLOTS = [
    ("3A/B/C/D/F", frozenset("ABCDF")),
    ("3C/D/F/G/H", frozenset("CDFGH")),
    ("3C/E/F/H/I", frozenset("CEFHI")),
    ("3E/H/I/J/K", frozenset("EHIJK")),
    ("3B/E/F/I/J", frozenset("BEFIJ")),
    ("3A/E/H/I/J", frozenset("AEHIJ")),
    ("3E/F/G/I/J", frozenset("EFGIJ")),
    ("3D/E/I/J/L", frozenset("DEIJL")),
]


def _r32_fixtures():
    return pd.DataFrame(
        [
            {"stage": "round_of_32", "match_number": n, "home_slot": h, "away_slot": a}
            for n, h, a in R32_ROWS
        ]
    )


def _group_table(letter: str, third_points: int) -> pd.DataFrame:
    rows = [
        (f"{letter}1", 9, 6, 3),
        (f"{letter}2", 6, 4, 1),
        (f"{letter}3", third_points, 2, 0),
        (f"{letter}4", 0, 0, -4),
    ]
    return pd.DataFrame(
        [
            {"team_id": t, "played": 3, "points": p, "gf": gf, "ga": gf - gd, "gd": gd, "rank": i + 1}
            for i, (t, p, gf, gd) in enumerate(rows)
        ]
    )


def _twelve_group_tables(qualifying_letters: str) -> dict[str, pd.DataFrame]:
    # Groups in qualifying_letters get a strong third (4 pts); the rest weak (1 pt).
    tables = {}
    for letter in "ABCDEFGHIJKL":
        tables[letter] = _group_table(letter, 4 if letter in qualifying_letters else 1)
    return tables


def test_parse_third_place_slots_matches_official_candidates():
    slots = parse_third_place_slots(_r32_fixtures())
    assert slots == REAL_SLOTS  # 8 slots, correct candidate groups, in match order


def test_rank_third_placed_orders_by_points_then_gd_gf():
    tables = {}
    # Distinct third-place points L(11) down to A(0) -> ranking should be by points desc.
    for i, letter in enumerate("ABCDEFGHIJKL"):
        tables[letter] = _group_table(letter, third_points=i)  # A=0 ... L=11
    ranked = rank_third_placed(tables)
    assert [g for g, _ in ranked] == list("LKJIHGFEDCBA")
    assert ranked[0] == ("L", "L3")


def test_allocate_thirds_respects_constraints_and_is_deterministic():
    for qualifying in ["ABCDEFGH", "EFGHIJKL", "ABCDEFGL"]:
        groups = set(qualifying)
        result = allocate_thirds(groups, REAL_SLOTS)
        candidates = dict(REAL_SLOTS)
        # every slot filled exactly once, each group used once, constraints respected
        assert set(result.keys()) == {tok for tok, _ in REAL_SLOTS}
        assert set(result.values()) == groups
        for token, group in result.items():
            assert group in candidates[token]
        # deterministic
        assert allocate_thirds(groups, REAL_SLOTS) == result


def test_allocate_thirds_raises_on_count_mismatch():
    with pytest.raises(ValueError):
        allocate_thirds(set("ABC"), REAL_SLOTS)  # 3 groups, 8 slots


def test_resolve_round_of_32_maps_slots_to_concrete_teams():
    tables = _twelve_group_tables("ABCDEFGH")  # thirds of A-H qualify
    pairings = resolve_round_of_32(_r32_fixtures(), tables)

    assert len(pairings) == 16
    # group-position slots resolve to the right rank
    assert pairings[73] == ("A2", "B2")  # 2A v 2B
    assert pairings[88] == ("D2", "G2")  # 2D v 2G
    assert pairings[79][0] == "A1"       # 1A v 3-slot -> home is group A winner
    assert pairings[84] == ("H1", "J2")  # 1H v 2J

    # every R32 tie is fully resolved (no Nones at this stage)
    for home, away in pairings.values():
        assert home is not None and away is not None

    # the eight third-place slots resolve to exactly the eight qualifying thirds
    qualifying_thirds = {f"{g}3" for g in "ABCDEFGH"}
    resolved_thirds = {
        team
        for n, (home, away) in pairings.items()
        for slot, team in ((dict(R32_ROWS_BY_NUM)[n][0], home), (dict(R32_ROWS_BY_NUM)[n][1], away))
        if slot.startswith("3") and len(slot) > 2
    }
    assert resolved_thirds == qualifying_thirds


R32_ROWS_BY_NUM = {n: (h, a) for n, h, a in R32_ROWS}
