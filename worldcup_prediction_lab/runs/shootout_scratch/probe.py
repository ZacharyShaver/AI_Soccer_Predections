"""Scratch (not committed): are penalty shootouts coin flips? Sim realism probe.

The Monte-Carlo knockout resolution (simulate/match_sim.simulate_knockout)
advances the stronger side with prob_home/(prob_home+prob_away) when
regulation ends drawn. martj42 scores INCLUDE extra time but NOT penalties,
so a drawn knockout row + a shootouts.csv entry = the match went to pens.
If real shootouts are ~50/50 regardless of team strength, the sim inflates
favorites' championship odds at every knockout round.

Method (leak-free): one online walk of the recalibrated Elo over the full
silver history; when a match row matches a shootouts.csv entry (canonical
team pair + date), record both sides' CURRENT pre-match ratings + the
shootout winner. Then compare the stronger side's actual shootout win rate
vs the rate the sim would have assumed on those same matches.
"""

from __future__ import annotations

import io
import json
import urllib.request

import pandas as pd

from wc_predictor.data.team_aliases import TeamAliasResolver
from wc_predictor.lab import eval_harness as eh

SHOOTOUTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"
)


def _binomial_ci(k: int, n: int) -> tuple[float, float]:
    """Wilson 95% interval."""

    if n == 0:
        return (0.0, 1.0)
    z = 1.96
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (center - half, center + half)


def main() -> None:
    raw = urllib.request.urlopen(SHOOTOUTS_URL, timeout=60).read().decode("utf-8")
    shootouts = pd.read_csv(io.StringIO(raw))
    print(f"shootouts.csv rows: {len(shootouts)}", flush=True)

    resolver = TeamAliasResolver.from_csv()

    def rid(name: str) -> str | None:
        try:
            return resolver.resolve(str(name), source="martj42").canonical_team_id
        except KeyError:
            return None

    lookup: dict[tuple[str, frozenset], str] = {}
    unresolved = 0
    for row in shootouts.itertuples(index=False):
        home, away, winner = rid(row.home_team), rid(row.away_team), rid(row.winner)
        if home is None or away is None or winner is None:
            unresolved += 1
            continue
        lookup[(str(row.date), frozenset((home, away)))] = winner
    print(f"resolved shootouts: {len(lookup)} (unresolved rows: {unresolved})", flush=True)

    matches = eh.load_history_matches()
    model = eh.recalibrated_elo()
    hits: list[dict] = []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        home_id, away_id = str(record["home_team_id"]), str(record["away_team_id"])
        key = (str(pd.Timestamp(record["date"]).date()), frozenset((home_id, away_id)))
        winner = lookup.get(key)
        if winner is not None and record["home_score"] == record["away_score"]:
            prediction = model.predict_match(series)
            hits.append(
                {
                    "date": key[0],
                    "home_rating": model.get_rating(home_id),
                    "away_rating": model.get_rating(away_id),
                    "prob_home": prediction.prob_home,
                    "prob_away": prediction.prob_away,
                    "stronger": home_id
                    if model.get_rating(home_id) >= model.get_rating(away_id)
                    else away_id,
                    "winner": winner,
                    "home_id": home_id,
                }
            )
        model._update_from_match(series)

    n = len(hits)
    stronger_won = sum(1 for h in hits if h["winner"] == h["stronger"])
    lo, hi = _binomial_ci(stronger_won, n)

    # What the sim assumes on these exact matches: stronger side advances at
    # max(ph,pa)/(ph+pa).
    sim_rates = [max(h["prob_home"], h["prob_away"]) / (h["prob_home"] + h["prob_away"]) for h in hits]

    # Split by rating gap to see if big favorites do any better.
    big = [h for h in hits if abs(h["home_rating"] - h["away_rating"]) >= 100]
    big_won = sum(1 for h in big if h["winner"] == h["stronger"])

    out = {
        "joined_shootouts_with_prematch_ratings": n,
        "stronger_side_won": stronger_won,
        "stronger_side_win_rate": stronger_won / n if n else None,
        "wilson_ci95": [lo, hi],
        "sim_assumed_stronger_advance_rate_mean": sum(sim_rates) / n if n else None,
        "gap_ge_100_elo": {
            "n": len(big),
            "stronger_won": big_won,
            "rate": big_won / len(big) if big else None,
            "wilson_ci95": list(_binomial_ci(big_won, len(big))),
        },
    }
    print(json.dumps(out, indent=1), flush=True)
    with open("runs/shootout_scratch/probe.json", "w", encoding="utf-8") as f:
        json.dump({**out, "hits": hits}, f, indent=2, default=str)


if __name__ == "__main__":
    main()
