"""Scratch (not committed): does Transfermarkt squad value add signal over Elo?

Protocol (mirrors the dc-elo fusion lane):
1. ONE recalibrated-Elo history walk-forward stores per-match pre-match
   ratings + base home-advantage. The squad-value delta only shifts the
   prediction-time rating difference, so every (coef, cap) config can be
   re-scored OFFLINE from the stored walk (no per-config refit). The
   rating-update feedback of a bounded delta is second-order; the frozen
   winner is verified with a TRUE in-walk run at the end.
2. Config selection is 6-block time-ordered walk-forward: block k is scored
   with the (coef, cap) chosen only on blocks < k — out-of-fold.
3. Paired CIs vs coef=0 (= elo_recalibrated) on the same matches: full
   sample AND the covered subsample (both teams had a squad value).

Delta definition: clip(coef * ln(V_home / V_away), -cap, +cap), applied on
top of the base home advantage (neutral venues keep the delta: it is a
strength differential, not a venue effect). V = monthly squad value with
month_end STRICTLY BEFORE the match date; both teams need
>= MIN_VALUED_PLAYERS valued players, else delta = 0.
"""

from __future__ import annotations

import json
from bisect import bisect_left
from math import log

import pandas as pd

from wc_predictor.data.ingest_transfermarkt import load_squad_values
from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.lab import eval_harness as eh

COEF_GRID = [0.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0]
CAP_GRID = [80.0, 160.0]
MIN_VALUED_PLAYERS = 5
N_BLOCKS = 6
SEED = 20260702


def build_lookup() -> dict[str, tuple[list[pd.Timestamp], list[float]]]:
    squad = load_squad_values()
    squad = squad[squad["valued_players"] >= MIN_VALUED_PLAYERS]
    lookup: dict[str, tuple[list[pd.Timestamp], list[float]]] = {}
    for team_id, group in squad.groupby("team_id"):
        group = group.sort_values("date")
        lookup[str(team_id)] = (list(group["date"]), list(group["squad_value_eur"]))
    return lookup


def value_before(
    lookup: dict[str, tuple[list[pd.Timestamp], list[float]]],
    team_id: str,
    date: pd.Timestamp,
) -> float | None:
    series = lookup.get(str(team_id))
    if series is None:
        return None
    dates, values = series
    index = bisect_left(dates, date)  # strictly before: dates[index-1] < date
    if index == 0:
        return None
    return values[index - 1]


def collect_walk() -> list[dict]:
    """One recalibrated walk; store what offline re-scoring needs."""

    matches = eh.load_history_matches()
    start = pd.Timestamp(eh.HISTORY_EVAL_START)
    model = eh.recalibrated_elo()
    lookup = build_lookup()

    rows: list[dict] = []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            home_id = str(record["home_team_id"])
            away_id = str(record["away_team_id"])
            home_value = value_before(lookup, home_id, record["date"])
            away_value = value_before(lookup, away_id, record["date"])
            log_ratio = (
                log(home_value / away_value)
                if home_value is not None and away_value is not None
                else None
            )
            rows.append(
                {
                    "actual": (
                        "home"
                        if record["home_score"] > record["away_score"]
                        else "away"
                        if record["away_score"] > record["home_score"]
                        else "draw"
                    ),
                    "home_rating": model.get_rating(home_id),
                    "away_rating": model.get_rating(away_id),
                    "base_adv": model._home_advantage_elo(series, home_id, away_id),
                    "log_ratio": log_ratio,
                }
            )
        model._update_from_match(series)
    return rows


def rps_for_config(rows: list[dict], prob_model, coef: float, cap: float) -> list[float]:
    out: list[float] = []
    for r in rows:
        delta = 0.0
        if r["log_ratio"] is not None and coef != 0.0:
            delta = max(-cap, min(cap, coef * r["log_ratio"]))
        probs = prob_model._outcome_probabilities(
            r["home_rating"], r["away_rating"], r["base_adv"] + delta
        )
        out.append(ranked_probability_score(eh._normalize(probs), r["actual"]))
    return out


def _paired(diffs: list[float]) -> dict:
    point, low, high, _ = bootstrap_ci(diffs, n_boot=1000, alpha=0.05, seed=SEED)
    return {
        "n": len(diffs),
        "mean_diff": point,
        "ci95": [low, high],
        "excludes_0": (low > 0.0) or (high < 0.0),
    }


def main() -> None:
    rows = collect_walk()
    prob_model = eh.recalibrated_elo()
    n = len(rows)
    covered = [i for i, r in enumerate(rows) if r["log_ratio"] is not None]
    print(
        f"walk: n={n}, covered={len(covered)} ({len(covered) / n:.1%})",
        flush=True,
    )

    configs = [(c, cap) for c in COEF_GRID for cap in CAP_GRID if not (c == 0.0 and cap != CAP_GRID[0])]
    grid = {
        (coef, cap): rps_for_config(rows, prob_model, coef, cap) for coef, cap in configs
    }
    base = grid[(0.0, CAP_GRID[0])]

    full_table = sorted(
        (
            {"coef": coef, "cap": cap, "rps": sum(r) / n}
            for (coef, cap), r in grid.items()
        ),
        key=lambda item: item["rps"],
    )
    print(json.dumps({"full_sample_grid_in_sample": full_table}, indent=1), flush=True)

    # Out-of-fold blocked walk-forward config selection.
    bounds = [round(i * n / N_BLOCKS) for i in range(N_BLOCKS + 1)]
    oof, oof_base = [], []
    config_path = []
    for k in range(1, N_BLOCKS):
        prior, block = slice(bounds[0], bounds[k]), slice(bounds[k], bounds[k + 1])
        best = min(configs, key=lambda cfg: sum(grid[cfg][prior]))
        config_path.append({"coef": best[0], "cap": best[1]})
        oof.extend(grid[best][block])
        oof_base.extend(base[block])

    out = {
        "coverage": {"n": n, "covered": len(covered), "share": len(covered) / n},
        "config_path": config_path,
        "oof": {
            "rps": sum(oof) / len(oof),
            "base_rps_same_matches": sum(oof_base) / len(oof_base),
            "vs_base_paired": _paired([a - b for a, b in zip(oof, oof_base)]),
        },
        "full_argmin": full_table[0],
    }

    # Covered-subsample paired check for the full-argmin config (secondary,
    # in-sample coef — reported for effect-size context, not promotion).
    best_cfg = (full_table[0]["coef"], full_table[0]["cap"])
    diffs_covered = [grid[best_cfg][i] - base[i] for i in covered]
    out["covered_subsample_full_argmin_vs_base"] = _paired(diffs_covered)

    print(json.dumps(out, indent=1), flush=True)
    with open("runs/squad_value_scratch/evaluate.json", "w", encoding="utf-8") as f:
        json.dump({"grid": full_table, **out}, f, indent=2)


if __name__ == "__main__":
    main()
