"""Resolve World Cup knockout bracket placeholders into real team ids.

Openfootball stores the 32 knockout fixtures as bracket slots with null team
ids -- group positions (``1A`` = Group A winner, ``2B`` = Group B runner-up,
``3A/B/C/D/F`` = a best third-placed team) and match-winner references (``W74``
= winner of match 74, ``L101`` = loser of match 101). Nothing downstream could
forecast them because the teams were unknown.

This resolver fills in the teams it can *prove*, and leaves the rest TBD -- it
never invents a matchup:

* ``1X`` / ``2X``: resolved from the final standings of a COMPLETE group
  (all six games played). Order: points, goal difference, goals for, then
  head-to-head among tied teams, then a stable team-id tiebreak.
* ``W<n>`` / ``L<n>``: resolved from a played knockout match once both its own
  teams are resolved and a result exists for that pairing.
* ``3X/Y/Z``: the eight best third-placed teams are ranked once all twelve
  groups are complete, but FIFA's official slot-assignment table is not encoded
  here, so a third-place slot is filled only when the candidate constraints
  force a unique assignment; otherwise it stays TBD.

Resolution is iterative (R16 depends on R32 results, etc.), so calling it
repeatedly as results land progressively fills the bracket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings

FIXTURES_FILE = "openfootball_worldcup_2026_fixtures.parquet"
MATCHES_FILE = "martj42_matches.parquet"

# match_number -> candidate groups for the eight best-third slots (openfootball).
THIRD_SLOT_CANDIDATES: dict[int, frozenset[str]] = {
    74: frozenset("ABCDF"),
    77: frozenset("CDFGH"),
    79: frozenset("CEFHI"),
    80: frozenset("EHIJK"),
    81: frozenset("BEFIJ"),
    82: frozenset("AEHIJ"),
    85: frozenset("EFGIJ"),
    87: frozenset("DEIJL"),
}


@dataclass(frozen=True)
class TeamRecord:
    team_id: str
    played: int
    points: int
    goals_for: int
    goals_against: int

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against


def _result_index(results_df: pd.DataFrame) -> dict[tuple[str, frozenset[str]], dict]:
    """Index completed results by (date, team pair) for orientation-agnostic lookup."""

    index: dict[tuple[str, frozenset[str]], dict] = {}
    if results_df is None or results_df.empty:
        return index
    df = results_df.copy()
    date_col = "match_date" if "match_date" in df.columns else "date"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, "home_team_id", "away_team_id", "home_score", "away_score"])
    for r in df.itertuples(index=False):
        rd = r._asdict()
        key = (
            pd.Timestamp(rd[date_col]).strftime("%Y-%m-%d"),
            frozenset({str(rd["home_team_id"]), str(rd["away_team_id"])}),
        )
        index.setdefault(
            key,
            {
                "home_team_id": str(rd["home_team_id"]),
                "home_score": int(rd["home_score"]),
                "away_score": int(rd["away_score"]),
            },
        )
    return index


def _scored_pair(result_index, date: str, a: str, b: str) -> tuple[int, int] | None:
    """Return (a_score, b_score) for the a-vs-b match on ``date``, or None."""

    if a == b:
        return None
    res = result_index.get((date, frozenset({a, b})))
    if res is None:
        return None
    if res["home_team_id"] == a:
        return res["home_score"], res["away_score"]
    return res["away_score"], res["home_score"]


def _points(gf: int, ga: int) -> int:
    return 3 if gf > ga else (1 if gf == ga else 0)


def group_standings(
    group_fixtures: pd.DataFrame,
    result_index: dict,
) -> dict[str, list[TeamRecord]]:
    """Return ordered standings per COMPLETE group (all games played)."""

    standings: dict[str, list[TeamRecord]] = {}
    for group, fixtures in group_fixtures.groupby("group"):
        teams = sorted(
            {str(t) for t in fixtures["home_team_id"]}
            | {str(t) for t in fixtures["away_team_id"]}
        )
        agg = {t: {"played": 0, "points": 0, "gf": 0, "ga": 0} for t in teams}
        pair_scores: dict[frozenset[str], tuple[str, int, int]] = {}
        complete = True
        for fx in fixtures.itertuples(index=False):
            home, away = str(fx.home_team_id), str(fx.away_team_id)
            date = pd.Timestamp(fx.match_date).strftime("%Y-%m-%d")
            sc = _scored_pair(result_index, date, home, away)
            if sc is None:
                complete = False
                continue
            hs, as_ = sc
            agg[home]["played"] += 1
            agg[away]["played"] += 1
            agg[home]["gf"] += hs
            agg[home]["ga"] += as_
            agg[away]["gf"] += as_
            agg[away]["ga"] += hs
            agg[home]["points"] += _points(hs, as_)
            agg[away]["points"] += _points(as_, hs)
            pair_scores[frozenset({home, away})] = (home, hs, as_)
        if not complete:
            continue
        records = {
            t: TeamRecord(t, agg[t]["played"], agg[t]["points"], agg[t]["gf"], agg[t]["ga"])
            for t in teams
        }
        standings[str(group)] = _order_group(records, pair_scores)
    return standings


def _head_to_head_key(team: str, tied: list[str], pair_scores: dict) -> tuple[int, int, int]:
    pts = gf = ga = 0
    for other in tied:
        if other == team:
            continue
        entry = pair_scores.get(frozenset({team, other}))
        if entry is None:
            continue
        home, hs, as_ = entry
        ts, os_ = (hs, as_) if home == team else (as_, hs)
        gf += ts
        ga += os_
        pts += _points(ts, os_)
    return (pts, gf - ga, gf)


def _order_group(records: dict[str, TeamRecord], pair_scores: dict) -> list[TeamRecord]:
    # Primary: points, GD, GF. Then head-to-head among still-tied, then team id.
    ordered = sorted(
        records.values(),
        key=lambda r: (-r.points, -r.goal_diff, -r.goals_for, r.team_id),
    )
    result: list[TeamRecord] = []
    i = 0
    while i < len(ordered):
        j = i
        while (
            j + 1 < len(ordered)
            and (ordered[j + 1].points, ordered[j + 1].goal_diff, ordered[j + 1].goals_for)
            == (ordered[i].points, ordered[i].goal_diff, ordered[i].goals_for)
        ):
            j += 1
        block = ordered[i : j + 1]
        if len(block) > 1:
            tied_ids = [r.team_id for r in block]
            block = sorted(
                block,
                key=lambda r: (
                    tuple(-v for v in _head_to_head_key(r.team_id, tied_ids, pair_scores)),
                    r.team_id,
                ),
            )
        result.extend(block)
        i = j + 1
    return result


def rank_third_placed(standings: dict[str, list[TeamRecord]]) -> list[tuple[str, str]]:
    """Ranked (group, team_id) for third-placed teams; needs all 12 groups complete."""

    if len(standings) < 12:
        return []
    thirds = []
    for group, table in standings.items():
        if len(table) >= 3:
            thirds.append((group, table[2]))
    thirds.sort(key=lambda gt: (-gt[1].points, -gt[1].goal_diff, -gt[1].goals_for, gt[0]))
    return [(g, rec.team_id) for g, rec in thirds]


def _assign_thirds(
    qualified: list[tuple[str, str]],
) -> dict[int, str]:
    """Assign the 8 qualified thirds to slots iff the candidate constraints force
    a unique perfect matching; otherwise return only the forced ones (or none)."""

    if len(qualified) != 8:
        return {}
    groups = [g for g, _ in qualified]
    team_by_group = {g: t for g, t in qualified}
    slots = list(THIRD_SLOT_CANDIDATES)
    valid: list[dict[int, str]] = []
    for perm in permutations(groups):
        ok = all(perm[i] in THIRD_SLOT_CANDIDATES[slots[i]] for i in range(8))
        if ok:
            valid.append({slots[i]: perm[i] for i in range(8)})
            if len(valid) > 1:
                return {}  # ambiguous -> resolve nothing rather than guess
    if len(valid) != 1:
        return {}
    return {slot: team_by_group[g] for slot, g in valid[0].items()}


_SLOT_RE = re.compile(r"^([12])([A-L])$")
_WL_RE = re.compile(r"^([WL])(\d+)$")


def _winner_loser(match_row, results_index) -> tuple[str | None, str | None]:
    home, away = str(match_row["home_team_id"]), str(match_row["away_team_id"])
    if home in ("", "nan", "None") or away in ("", "nan", "None"):
        return None, None
    date = str(match_row["match_date"])[:10]
    sc = _scored_pair(results_index, date, home, away)
    if sc is None:
        return None, None
    hs, as_ = sc
    if hs == as_:
        return None, None  # knockout draws are decided on penalties; needs richer data
    return (home, away) if hs > as_ else (away, home)


def resolve_bracket(
    fixtures: pd.DataFrame,
    results_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Return fixtures with knockout team ids resolved where provable, plus a summary."""

    fixtures = fixtures.copy()
    fixtures["match_date"] = pd.to_datetime(fixtures["match_date"], errors="coerce")
    result_index = _result_index(results_df)

    group_fixtures = fixtures[fixtures["stage"] == "group"]
    standings = group_standings(group_fixtures, result_index)
    thirds_assignment = _assign_thirds(rank_third_placed(standings))

    def _slot_team(slot) -> str | None:
        if slot is None or (isinstance(slot, float) and pd.isna(slot)):
            return None
        slot = str(slot).strip()
        m = _SLOT_RE.match(slot)
        if m:
            pos, group = int(m.group(1)), m.group(2)
            table = standings.get(group)
            if table and len(table) >= pos:
                return table[pos - 1].team_id
            return None
        return None  # 3X/Y/Z handled via match_number; W/L handled iteratively

    # Resolve group-position slots first.
    for idx, row in fixtures.iterrows():
        if row["stage"] == "group":
            continue
        if _has_id(row["home_team_id"]) and _has_id(row["away_team_id"]):
            continue
        home = _slot_team(row["home_slot"]) if not _has_id(row["home_team_id"]) else row["home_team_id"]
        away = _slot_team(row["away_slot"]) if not _has_id(row["away_team_id"]) else row["away_team_id"]
        mn = int(row["match_number"]) if not pd.isna(row["match_number"]) else None
        if mn in thirds_assignment:
            if str(row["home_slot"]).startswith("3"):
                home = thirds_assignment[mn]
            elif str(row["away_slot"]).startswith("3"):
                away = thirds_assignment[mn]
        if _has_id(home):
            fixtures.at[idx, "home_team_id"] = home
        if _has_id(away):
            fixtures.at[idx, "away_team_id"] = away

    # Iteratively resolve W/L propagation as earlier matches resolve + are played.
    by_number = {int(r["match_number"]): i for i, r in fixtures.iterrows() if not pd.isna(r["match_number"])}
    for _ in range(6):  # depth of the bracket
        changed = False
        for idx, row in fixtures.iterrows():
            if row["stage"] == "group":
                continue
            for side, slot_col, id_col in (
                ("home", "home_slot", "home_team_id"),
                ("away", "away_slot", "away_team_id"),
            ):
                if _has_id(row[id_col]):
                    continue
                m = _WL_RE.match(str(row[slot_col]).strip())
                if not m:
                    continue
                want_winner = m.group(1) == "W"
                ref = int(m.group(2))
                ref_idx = by_number.get(ref)
                if ref_idx is None:
                    continue
                winner, loser = _winner_loser(fixtures.loc[ref_idx], result_index)
                team = winner if want_winner else loser
                if _has_id(team):
                    fixtures.at[idx, id_col] = team
                    row = fixtures.loc[idx]
                    changed = True
        if not changed:
            break

    ko = fixtures[fixtures["stage"] != "group"]
    resolved = sum(
        1
        for r in ko.itertuples(index=False)
        if _has_id(r.home_team_id) and _has_id(r.away_team_id)
    )
    summary = {
        "complete_groups": len(standings),
        "knockout_total": int(len(ko)),
        "knockout_resolved": resolved,
        "thirds_assigned": len(thirds_assignment),
    }
    return fixtures, summary


def _has_id(value) -> bool:
    return pd.notna(value) and str(value).strip() not in ("", "nan", "None")


def _read_parquet(path: Path) -> pd.DataFrame:
    import duckdb

    escaped = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as con:
        return con.execute(f"SELECT * FROM read_parquet('{escaped}')").fetchdf()


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as con:
        con.register("df_to_write", df)
        con.execute(f"COPY df_to_write TO '{escaped}' (FORMAT PARQUET)")


def resolve_and_persist_fixtures(silver_dir: str | Path = settings.SILVER_DIR) -> dict:
    """Resolve the bracket against current results and write resolved team ids
    back into the fixtures parquet so every downstream reader forecasts the
    knockout games that are now determined. Idempotent and self-healing: a later
    openfootball re-ingest resets slots to null and the next call re-fills them.
    """

    silver = Path(silver_dir)
    fixtures_path = silver / FIXTURES_FILE
    matches_path = silver / MATCHES_FILE
    if not fixtures_path.exists() or not matches_path.exists():
        return {"complete_groups": 0, "knockout_total": 0, "knockout_resolved": 0, "thirds_assigned": 0}

    fixtures = _read_parquet(fixtures_path)
    matches = _read_parquet(matches_path)
    resolved, summary = resolve_bracket(fixtures, matches)
    # Normalize null ids to None and keep the original column order for a clean write.
    resolved = resolved.loc[:, list(fixtures.columns)].copy()
    for col in ("home_team_id", "away_team_id"):
        resolved[col] = resolved[col].map(lambda v: v if _has_id(v) else None).astype("object")
    _write_parquet(resolved, fixtures_path)
    return summary
