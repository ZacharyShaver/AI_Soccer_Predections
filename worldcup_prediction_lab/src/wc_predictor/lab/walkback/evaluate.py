"""Evaluation: accuracy ladder, paired bootstrap CIs, calibration analysis.

Every lane (model x condition) is compared PAIRED against elo and market on
exactly the matches that lane predicted — same protocol as the fusion ledger.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score

from wc_predictor.lab.walkback.universe import CUTOFF_DEFAULT


def climatology_probs(frame: pd.DataFrame, cutoff: str = CUTOFF_DEFAULT) -> tuple[float, float, float]:
    pre = frame[pd.to_datetime(frame["date"]) < pd.Timestamp(cutoff)]
    counts = pre["outcome"].value_counts()
    total = int(counts.sum())
    if total == 0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return tuple(float(counts.get(k, 0)) / total for k in ("home", "draw", "away"))


def _rps_series(probs_list, outcomes) -> list[float]:
    return [ranked_probability_score(p, o) for p, o in zip(probs_list, outcomes)]


def _paired(diffs: list[float]) -> dict:
    point, lo, hi, _ = bootstrap_ci(diffs, n_boot=2000, alpha=0.05, seed=0)
    return {"point": point, "lo": lo, "hi": hi}


def _apply_temp(p: tuple[float, float, float], temp: float) -> tuple[float, float, float]:
    powered = [max(1e-9, x) ** (1.0 / temp) for x in p]
    total = sum(powered)
    return tuple(x / total for x in powered)


def fit_temperature(probs_list, outcomes, grid=None) -> float:
    grid = grid or [round(0.5 + 0.05 * i, 2) for i in range(51)]  # 0.5 .. 3.0
    best_t, best_rps = 1.0, float("inf")
    for t in grid:
        rps = sum(_rps_series([_apply_temp(p, t) for p in probs_list], outcomes))
        if rps < best_rps:
            best_t, best_rps = t, rps
    return best_t


def _calibration(probs_list, outcomes) -> dict:
    fit_p = probs_list[0::2]
    fit_o = outcomes[0::2]
    hold_p = probs_list[1::2]
    hold_o = outcomes[1::2]
    temp = fit_temperature(fit_p, fit_o) if len(fit_p) >= 10 else 1.0
    rps_raw = sum(_rps_series(hold_p, hold_o)) / max(1, len(hold_p))
    rps_temp = sum(
        _rps_series([_apply_temp(p, temp) for p in hold_p], hold_o)
    ) / max(1, len(hold_p))
    clump = Counter(tuple(round(x, 2) for x in p) for p in probs_list)
    return {"temp": temp, "rps_raw": rps_raw, "rps_temp": rps_temp,
            "clump_top10": clump.most_common(10)}


def evaluate(universe: pd.DataFrame, preds: list[dict]) -> dict:
    uni = universe.copy()
    uni["match_id"] = uni["match_id"].astype(str)
    uni = uni.set_index("match_id", drop=False)
    clim = climatology_probs(universe)

    lanes: dict[str, dict] = {}
    ladder: dict[str, dict] = {}
    by_lane: dict[str, list[dict]] = {}
    for p in preds:
        by_lane.setdefault(f"{p['model']}/{p['condition']}", []).append(p)

    for lane_key, rows in sorted(by_lane.items()):
        rows = [r for r in rows if str(r["match_id"]) in uni.index]
        rows.sort(key=lambda r: str(uni.loc[str(r["match_id"]), "date"]))
        outcomes = [str(uni.loc[str(r["match_id"]), "outcome"]) for r in rows]
        model_p = [(r["p_home"], r["p_draw"], r["p_away"]) for r in rows]
        elo_p = [tuple(uni.loc[str(r["match_id"]), ["elo_prob_home", "elo_prob_draw", "elo_prob_away"]])
                 for r in rows]
        mkt_p = [tuple(uni.loc[str(r["match_id"]), ["market_prob_home", "market_prob_draw", "market_prob_away"]])
                 for r in rows]
        model_rps = _rps_series(model_p, outcomes)
        elo_rps = _rps_series(elo_p, outcomes)
        mkt_rps = _rps_series(mkt_p, outcomes)
        clim_rps = _rps_series([clim] * len(rows), outcomes)
        n = len(rows)
        lanes[lane_key] = {
            "n": n,
            "rps": sum(model_rps) / max(1, n),
            "vs_elo": _paired([m - e for m, e in zip(model_rps, elo_rps)]),
            "vs_market": _paired([m - k for m, k in zip(model_rps, mkt_rps)]),
            "calibration": _calibration(model_p, outcomes),
        }
        ladder[lane_key] = {"n": n, "rps": lanes[lane_key]["rps"]}
        ladder.setdefault("climatology", {"n": n, "rps": sum(clim_rps) / max(1, n)})
        ladder.setdefault("elo", {"n": n, "rps": sum(elo_rps) / max(1, n)})
        ladder.setdefault("market", {"n": n, "rps": sum(mkt_rps) / max(1, n)})

    return {"lanes": lanes, "ladder": ladder}


def write_report(results: dict, path: Path) -> None:
    lines = ["# Local-model match-analyst walk-back", ""]
    lines += ["## Accuracy ladder (lower RPS = better)", "",
              "| Lane | n | RPS |", "| --- | ---: | ---: |"]
    for name, row in sorted(results["ladder"].items(), key=lambda kv: kv[1]["rps"]):
        lines.append(f"| {name} | {row['n']} | {row['rps']:.5f} |")
    lines += ["", "## Paired comparisons (RPS diff, negative = lane better)", ""]
    for lane_key, lane in results["lanes"].items():
        ve, vm = lane["vs_elo"], lane["vs_market"]
        cal = lane["calibration"]
        lines += [
            f"### {lane_key} (n={lane['n']})",
            f"- vs elo: {ve['point']:+.5f} CI [{ve['lo']:+.5f}, {ve['hi']:+.5f}]",
            f"- vs market: {vm['point']:+.5f} CI [{vm['lo']:+.5f}, {vm['hi']:+.5f}]",
            f"- calibration: temp {cal['temp']:.2f}, holdout RPS raw {cal['rps_raw']:.5f} "
            f"-> temp-scaled {cal['rps_temp']:.5f}",
            f"- clumping (top triples): {cal['clump_top10'][:3]}",
            "",
        ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
