"""Monte Carlo tournament simulation for championship odds (P4 / S3).

Each simulation: hold already-played group results fixed, simulate the remaining
group games, compute the 12 group tables (S0), resolve the Round of 32 incl the
8-best-thirds allocation (S1), then play out the knockout bracket (S2) to a
champion. Repeating thousands of times yields each team's probability of
advancing from the group and reaching each knockout round.

Team Elo ratings are static during a single as-of run, so per-matchup scoreline
grids and knockout advance probabilities are memoized — a large speedup that lets
20k+ simulations run quickly. Randomness flows through one seeded
``numpy.random.Generator`` for full reproducibility.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from wc_predictor.simulate.bracket import resolve_round_of_32
from wc_predictor.simulate.match_sim import home_advance_probability, sample_scoreline
from wc_predictor.simulate.standings import compute_group_table

_ROUND_BOUNDS = {
    "r16": range(73, 89),       # winners of R32
    "qf": range(89, 97),        # winners of R16
    "sf": range(97, 101),       # winners of QF
    "final": range(101, 103),   # winners of SF
}
_FINAL_MATCH = 104


def played_group_results(
    matches: pd.DataFrame, fixtures: pd.DataFrame, as_of: str | None = None
) -> dict[frozenset, dict[str, int]]:
    """Map already-played WC group matchups to ``{team_id: goals}``.

    Keyed by the unordered team pair so martj42/openfootball home-away ordering
    disagreements do not matter. Honors the ``as_of`` cutoff.
    """

    group_fx = fixtures[fixtures["stage"] == "group"]
    group_pairs = {
        frozenset((str(r.home_team_id), str(r.away_team_id)))
        for r in group_fx.itertuples(index=False)
    }
    wc = matches[matches["tournament"] == "FIFA World Cup"].copy()
    if as_of is not None:
        wc = wc[pd.to_datetime(wc["date"]) <= pd.Timestamp(as_of)]

    played: dict[frozenset, dict[str, int]] = {}
    for r in wc.itertuples(index=False):
        home, away = str(r.home_team_id), str(r.away_team_id)
        pair = frozenset((home, away))
        if pair in group_pairs:
            played[pair] = {home: int(r.home_score), away: int(r.away_score)}
    return played


class TournamentSimulator:
    def __init__(
        self,
        model,
        fixtures: pd.DataFrame,
        matches: pd.DataFrame | None = None,
        as_of: str | None = None,
    ) -> None:
        self.model = model
        self.fixtures = fixtures
        self.as_of = as_of

        group_fx = fixtures[fixtures["stage"] == "group"]
        self.groups: dict[str, list[tuple[str, str, str]]] = {}
        self.all_teams: set[str] = set()
        for r in group_fx.itertuples(index=False):
            home, away = str(r.home_team_id), str(r.away_team_id)
            venue = str(getattr(r, "venue", "") or "")
            self.groups.setdefault(str(r.group), []).append((home, away, venue))
            self.all_teams.update((home, away))

        knock = fixtures[fixtures["stage"] != "group"].sort_values("match_number")
        self.knockout = [
            (int(r.match_number), str(r.home_slot), str(r.away_slot), str(getattr(r, "venue", "") or ""))
            for r in knock.itertuples(index=False)
        ]

        self.played = (
            played_group_results(matches, fixtures, as_of) if matches is not None else {}
        )

        self._scoreline_cache: dict[tuple, tuple[list, float]] = {}
        self._advance_cache: dict[tuple, float] = {}

    # --- cached per-matchup predictions (ratings are static within a run) ---
    def _scoreline(self, home: str, away: str, venue: str, rng: np.random.Generator):
        key = (home, away, venue)
        if key not in self._scoreline_cache:
            row = pd.Series(
                {"home_team_id": home, "away_team_id": away, "neutral": True, "venue": venue, "match_id": ""}
            )
            # reuse match_sim's sampler structure by caching the distribution items
            dist = self.model.predict_scoreline(row)
            items = sorted(dist.probabilities.items())
            total = sum(p for _, p in items)
            self._scoreline_cache[key] = (items, total)
        items, total = self._scoreline_cache[key]
        if total <= 0.0:
            return (0, 0)
        threshold = rng.random() * total
        cumulative = 0.0
        chosen = items[-1][0]
        for k, p in items:
            cumulative += p
            if threshold <= cumulative:
                chosen = k
                break
        h, a = chosen.split("-")
        return (int(h), int(a))

    def _advance_prob(self, home: str, away: str, venue: str) -> float:
        key = (home, away, venue)
        if key not in self._advance_cache:
            row = pd.Series(
                {"home_team_id": home, "away_team_id": away, "neutral": True, "venue": venue}
            )
            self._advance_cache[key] = home_advance_probability(self.model, row)
        return self._advance_cache[key]

    def _simulate_once(self, rng: np.random.Generator):
        # 1) group tables (played fixed, remaining simulated)
        group_tables: dict[str, pd.DataFrame] = {}
        for group, fixtures_list in self.groups.items():
            rows = []
            for home, away, venue in fixtures_list:
                pair = frozenset((home, away))
                if pair in self.played:
                    res = self.played[pair]
                    hg, ag = res[home], res[away]
                else:
                    hg, ag = self._scoreline(home, away, venue, rng)
                rows.append((home, away, hg, ag))
            df = pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_score", "away_score"])
            group_tables[group] = compute_group_table(df)

        # 2) Round of 32 (incl best-thirds allocation)
        pairings = resolve_round_of_32(self.fixtures, group_tables)
        advanced = set()
        for home, away in pairings.values():
            advanced.update((home, away))

        # 3) knockouts
        winners: dict[int, str] = {}
        losers: dict[int, str] = {}
        for match_number, home_slot, away_slot, venue in self.knockout:
            if match_number in pairings:
                home, away = pairings[match_number]
            else:
                home = self._resolve_slot(home_slot, winners, losers)
                away = self._resolve_slot(away_slot, winners, losers)
            p_home = self._advance_prob(home, away, venue)
            if rng.random() < p_home:
                winners[match_number], losers[match_number] = home, away
            else:
                winners[match_number], losers[match_number] = away, home

        reached = {
            level: {winners[n] for n in bounds if n in winners}
            for level, bounds in _ROUND_BOUNDS.items()
        }
        champion = winners.get(_FINAL_MATCH)
        return advanced, reached, champion

    @staticmethod
    def _resolve_slot(slot: str, winners: dict[int, str], losers: dict[int, str]) -> str:
        kind, num = slot[0], int(slot[1:])
        return winners[num] if kind == "W" else losers[num]

    def run(self, n_sims: int, seed: int = 0) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        counts = {
            t: {"advance": 0, "r16": 0, "qf": 0, "sf": 0, "final": 0, "win": 0}
            for t in self.all_teams
        }
        for _ in range(n_sims):
            advanced, reached, champion = self._simulate_once(rng)
            for t in advanced:
                counts[t]["advance"] += 1
            for level in ("r16", "qf", "sf", "final"):
                for t in reached[level]:
                    counts[t][level] += 1
            if champion is not None:
                counts[champion]["win"] += 1

        records = []
        for team, c in counts.items():
            records.append(
                {
                    "team_id": team,
                    "p_advance": c["advance"] / n_sims,
                    "p_r16": c["r16"] / n_sims,
                    "p_qf": c["qf"] / n_sims,
                    "p_sf": c["sf"] / n_sims,
                    "p_final": c["final"] / n_sims,
                    "p_win": c["win"] / n_sims,
                    "n_sims": n_sims,
                }
            )
        table = pd.DataFrame.from_records(records)
        return table.sort_values(["p_win", "p_final", "p_advance", "team_id"], ascending=[False, False, False, True]).reset_index(drop=True)


def run_tournament_simulation(
    model,
    matches: pd.DataFrame,
    fixtures: pd.DataFrame,
    n_sims: int = 20000,
    seed: int = 0,
    as_of: str | None = None,
) -> pd.DataFrame:
    """Convenience wrapper: build a simulator and run ``n_sims`` simulations."""

    return TournamentSimulator(model, fixtures, matches=matches, as_of=as_of).run(n_sims, seed)
