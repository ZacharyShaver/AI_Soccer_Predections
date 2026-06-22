"""Knockout bracket resolution for the 48-team 2026 World Cup.

The 2026 format sends the top 2 of each of the 12 groups (24 teams) plus the
**8 best third-placed teams** into a Round of 32. The third-placed teams are
allocated to specific R32 slots subject to candidate-group constraints encoded
in the openfootball fixture slots (e.g. ``3A/B/C/D/F`` accepts a third-placed
team from groups A, B, C, D, or F).

FIFA publishes a fixed lookup table mapping each of the C(12, 8) = 495 possible
sets of qualifying third-place groups to a slot assignment. Rather than embed
that 495-row table, we solve the equivalent **constraint-satisfaction matching**
directly against the candidate lists the fixtures already carry: assign each
qualifying third-placed team to a slot whose candidate-group list contains its
group, each slot filled exactly once. FIFA designed the candidate lists so a
valid assignment exists for every combination; a deterministic backtracking
search (fixed slot/candidate ordering) returns one. Where multiple valid
assignments exist this may differ from FIFA's published row, but it always
respects the official constraints — a documented approximation whose effect on
championship odds is negligible (it only nudges which R32 tie the weakest
qualifiers land in). This choice is restated in the S4 report.
"""

from __future__ import annotations

import pandas as pd

THIRD_PREFIX = "3"


def parse_third_place_slots(fixtures: pd.DataFrame) -> list[tuple[str, frozenset[str]]]:
    """Return third-place R32 slots as ``(slot_token, candidate_groups)``.

    Ordered by ``match_number`` for deterministic allocation. A third-place slot
    is any knockout slot beginning with ``3`` and containing group letters, e.g.
    ``3A/B/C/D/F`` -> ("3A/B/C/D/F", {A, B, C, D, F}).
    """

    r32 = fixtures[fixtures["stage"] == "round_of_32"].sort_values("match_number")
    slots: list[tuple[str, frozenset[str]]] = []
    seen: set[str] = set()
    for row in r32.itertuples(index=False):
        for token in (row.home_slot, row.away_slot):
            if not isinstance(token, str) or not token.startswith(THIRD_PREFIX):
                continue
            letters = frozenset(c for c in token[1:] if c.isalpha())
            if len(letters) <= 1:
                continue  # "3" with a single letter would be a fixed group slot
            if token not in seen:
                seen.add(token)
                slots.append((token, letters))
    return slots


def rank_third_placed(group_tables: dict[str, pd.DataFrame]) -> list[tuple[str, str]]:
    """Rank the third-placed teams across groups, best first.

    Criteria: points -> goal difference -> goals scored -> (group letter, team_id)
    as a deterministic fallback (FIFA's fair-play / drawing-of-lots steps are not
    modellable). Returns ``[(group_letter, team_id), ...]``.
    """

    thirds: list[tuple[int, int, int, str, str]] = []
    for group, table in group_tables.items():
        third = table[table["rank"] == 3]
        if third.empty:
            continue
        r = third.iloc[0]
        # negate metrics so ascending sort = best first; group/team ascending tiebreak
        thirds.append((-int(r["points"]), -int(r["gd"]), -int(r["gf"]), group, str(r["team_id"])))
    thirds.sort()
    return [(group, team_id) for *_, group, team_id in thirds]


def allocate_thirds(
    qualifying_groups: set[str],
    slots: list[tuple[str, frozenset[str]]],
) -> dict[str, str]:
    """Match qualifying third-place groups to slots respecting candidate lists.

    Returns ``{slot_token: group_letter}``. Deterministic (slots in given order,
    candidate groups tried alphabetically). Raises ``ValueError`` if no valid
    assignment exists (should not happen with official candidate lists).
    """

    if len(qualifying_groups) != len(slots):
        raise ValueError(
            f"need exactly {len(slots)} qualifying groups, got {len(qualifying_groups)}"
        )

    assignment: dict[str, str] = {}
    used: set[str] = set()

    def backtrack(i: int) -> bool:
        if i == len(slots):
            return True
        token, candidates = slots[i]
        for group in sorted(candidates):
            if group in qualifying_groups and group not in used:
                used.add(group)
                assignment[token] = group
                if backtrack(i + 1):
                    return True
                used.remove(group)
                del assignment[token]
        return False

    if not backtrack(0):
        raise ValueError(
            f"no valid third-place allocation for groups {sorted(qualifying_groups)}"
        )
    return dict(assignment)


def _resolve_group_slot(
    token: str,
    group_tables: dict[str, pd.DataFrame],
    third_slot_team: dict[str, str],
) -> str | None:
    """Resolve a group-based slot (1X / 2X / third-slot) to a team id.

    Returns ``None`` for winner/loser slots (``W##`` / ``L##``) which are only
    known once earlier knockout matches are simulated.
    """

    if not isinstance(token, str) or not token:
        return None
    if token in third_slot_team:
        return third_slot_team[token]
    head = token[0]
    rest = token[1:]
    if head in {"1", "2"} and rest.isalpha() and len(rest) == 1:
        table = group_tables[rest]
        rank = 1 if head == "1" else 2
        return str(table[table["rank"] == rank].iloc[0]["team_id"])
    return None  # W##/L## resolved during simulation


def resolve_round_of_32(
    fixtures: pd.DataFrame, group_tables: dict[str, pd.DataFrame]
) -> dict[int, tuple[str, str]]:
    """Resolve every Round-of-32 tie to concrete ``(home_team_id, away_team_id)``."""

    slots = parse_third_place_slots(fixtures)
    ranked = rank_third_placed(group_tables)
    qualifying = ranked[: len(slots)]
    qualifying_groups = {g for g, _ in qualifying}
    team_by_group = {g: t for g, t in qualifying}

    slot_to_group = allocate_thirds(qualifying_groups, slots)
    third_slot_team = {token: team_by_group[group] for token, group in slot_to_group.items()}

    r32 = fixtures[fixtures["stage"] == "round_of_32"].sort_values("match_number")
    pairings: dict[int, tuple[str, str]] = {}
    for row in r32.itertuples(index=False):
        home = _resolve_group_slot(row.home_slot, group_tables, third_slot_team)
        away = _resolve_group_slot(row.away_slot, group_tables, third_slot_team)
        pairings[int(row.match_number)] = (home, away)
    return pairings
