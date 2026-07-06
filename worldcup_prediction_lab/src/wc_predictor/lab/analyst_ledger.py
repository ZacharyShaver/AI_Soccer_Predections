"""Append-only ledger + scorer for the Match-Analyst agent's own forecasts.

This is the agent's memory of its past guesses (requirement #3). Every forecast it
makes — deterministic baseline or live ``agent`` mode — is written once, at first
sighting, with the H/D/A it committed to, the chosen winner, and the Elo/market
probabilities at the time (so we can score it *paired against* those baselines).
Once a match resolves we attach the outcome, whether the pick hit, and RPS.

``track_record`` splits by mode so the live agent's forward record is visible
separately from the deterministic floor. ``calibration_summary`` fits a leak-free
temperature on the agent's OWN resolved forecasts so it can sharpen/soften future
calls from its history rather than from cosmetic knobs.

Recording is idempotent by ``fixture_id``: re-running the dashboard never moves a
committed forecast or double-counts it.
"""

from __future__ import annotations

import json
from pathlib import Path

from wc_predictor.config import settings
from wc_predictor.evaluation.metrics import ranked_probability_score
from wc_predictor.lab.analyst import AnalystForecast

LEDGER_PATH = settings.EXPERIMENTS_DIR.parent / "analyst" / "ledger.jsonl"

_OUTCOMES = ("home", "draw", "away")

_PERSIST_FIELDS = (
    "fixture_id", "as_of", "match_date", "home_team_name", "away_team_name",
    "p_home", "p_draw", "p_away", "pick", "pick_team", "confidence",
    "rationale", "sources", "mode",
)


def _outcome(home_score: int, away_score: int) -> str:
    return "home" if home_score > away_score else "away" if away_score > home_score else "draw"


def load_ledger(ledger_path: str | Path = LEDGER_PATH) -> list[dict]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_forecast(
    forecasts: list[AnalystForecast],
    *,
    as_of: str,
    elo_probs: dict[str, tuple[float, float, float]] | None = None,
    market_probs: dict[str, tuple[float, float, float]] | None = None,
    ledger_path: str | Path = LEDGER_PATH,
) -> int:
    """Append forecasts not already in the ledger. Returns how many were new.

    ``elo_probs``/``market_probs`` (keyed by fixture_id) are frozen alongside each
    forecast so it can later be scored paired against those baselines.
    """

    path = Path(ledger_path)
    # Idempotent per (fixture_id, mode): the deterministic floor and the live agent
    # each record their own row for a fixture without one blocking the other, while
    # re-running the same mode stays a no-op.
    seen = {(str(r["fixture_id"]), str(r.get("mode", ""))) for r in load_ledger(path)}
    path.parent.mkdir(parents=True, exist_ok=True)
    added = 0
    with path.open("a", encoding="utf-8") as fh:
        for f in forecasts:
            fid = str(f.fixture_id)
            key = (fid, str(f.mode))
            if key in seen:
                continue
            seen.add(key)
            rec = {"snapshot_date": as_of, **{k: getattr(f, k) for k in _PERSIST_FIELDS}}
            if elo_probs and fid in elo_probs:
                rec["elo_probs"] = list(elo_probs[fid])
            if market_probs and fid in market_probs:
                rec["market_probs"] = list(market_probs[fid])
            fh.write(json.dumps(rec) + "\n")
            added += 1
    return added


def resolve_forecasts(ledger: list[dict], results: dict[str, tuple[int, int]]) -> list[dict]:
    """Attach outcome, pick-correctness and RPS (and paired baseline RPS) per row."""

    out: list[dict] = []
    for r in ledger:
        row = dict(r)
        res = results.get(str(r["fixture_id"]))
        if res is None:
            row.update(resolved=False, actual=None, correct=None, rps=None,
                       elo_rps=None, market_rps=None)
            out.append(row)
            continue
        actual = _outcome(int(res[0]), int(res[1]))
        probs = (float(r["p_home"]), float(r["p_draw"]), float(r["p_away"]))
        row.update(
            resolved=True,
            actual=actual,
            correct=(r["pick"] == actual),
            rps=ranked_probability_score(probs, actual),
            elo_rps=(ranked_probability_score(tuple(r["elo_probs"]), actual)
                     if r.get("elo_probs") else None),
            market_rps=(ranked_probability_score(tuple(r["market_probs"]), actual)
                        if r.get("market_probs") else None),
        )
        out.append(row)
    return out


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def track_record(resolved: list[dict]) -> dict:
    """Aggregate accuracy + RPS (and paired diffs vs Elo/market) by mode."""

    summary: dict = {}
    modes = sorted({str(r.get("mode", "deterministic")) for r in resolved}) or ["deterministic"]
    for mode in modes:
        rows = [x for x in resolved if x["resolved"] and str(x.get("mode")) == mode]
        n = len(rows)
        rps = [x["rps"] for x in rows if x["rps"] is not None]
        vs_elo = [x["rps"] - x["elo_rps"] for x in rows if x.get("elo_rps") is not None]
        vs_mkt = [x["rps"] - x["market_rps"] for x in rows if x.get("market_rps") is not None]
        summary[mode] = {
            "n": n,
            "hits": sum(1 for x in rows if x["correct"]),
            "accuracy": (sum(1 for x in rows if x["correct"]) / n) if n else None,
            "mean_rps": _mean(rps),
            "vs_elo": _mean(vs_elo),      # negative = analyst better than Elo
            "vs_market": _mean(vs_mkt),   # negative = analyst better than market
            "pending": sum(
                1 for x in resolved
                if not x["resolved"] and str(x.get("mode")) == mode
            ),
        }
    return summary


RECORD_CAUTION = (
    "Small sample: treat this record as anecdote, not license. It informs how you SIZE "
    "deviations; it never justifies deviating more than your rules allow."
)


def agent_record_summary(resolved: list[dict], *, mode: str = "agent", max_rows: int = 10) -> dict:
    """The agent's own resolved record, packaged for the context packet.

    Leak-free by construction (resolved rows only). Each past deviation from the
    frozen market anchor is classified helped/hurt/neutral by paired RPS so the
    live agent can see whether its news-based shifts have been earning their keep.
    """

    rows = [r for r in resolved if r["resolved"] and str(r.get("mode")) == mode]
    deviations: list[dict] = []
    for r in rows[-max_rows:]:
        mkt = r.get("market_probs")
        if not mkt or r.get("market_rps") is None:
            continue
        probs = (float(r["p_home"]), float(r["p_draw"]), float(r["p_away"]))
        # Total-variation distance from the anchor, in percentage points.
        size_pts = 50.0 * sum(abs(p - m) for p, m in zip(probs, mkt))
        toward = _OUTCOMES[max(range(3), key=lambda i: probs[i] - mkt[i])]
        edge = r["market_rps"] - r["rps"]  # positive = beat the market
        outcome = (
            "neutral" if size_pts < 0.25 or abs(edge) < 1e-4
            else "helped" if edge > 0 else "hurt"
        )
        deviations.append({
            "fixture": f"{r['home_team_name']} v {r['away_team_name']}",
            "match_date": r.get("match_date"),
            "size_pts": round(size_pts, 2),
            "toward": toward,
            "outcome": outcome,
            "pick_correct": bool(r["correct"]),
        })
    return {
        "mode": mode,
        "n_resolved": len(rows),
        "hits": sum(1 for r in rows if r["correct"]),
        "mean_rps": _mean([r["rps"] for r in rows]),
        "vs_market": _mean([
            r["rps"] - r["market_rps"] for r in rows if r.get("market_rps") is not None
        ]),  # negative = agent better than the frozen market anchor
        "deviations": deviations,
        "caution": RECORD_CAUTION,
    }


def paired_mode_comparison(
    resolved: list[dict], *, mode_a: str = "agent", mode_b: str = "agent_late"
) -> dict:
    """Paired RPS comparison of two modes on fixtures where BOTH resolved.

    This is the timing experiment's readout: mode_a = morning research,
    mode_b = T-75 lineup check. mean_diff = mean(rps_b - rps_a); negative
    means the late pass was more accurate. ci95 stays None below n=10.
    """

    a = {str(r["fixture_id"]): r for r in resolved
         if r["resolved"] and str(r.get("mode")) == mode_a}
    b = {str(r["fixture_id"]): r for r in resolved
         if r["resolved"] and str(r.get("mode")) == mode_b}
    fids = sorted(set(a) & set(b))
    diffs = [b[f]["rps"] - a[f]["rps"] for f in fids]
    ci95 = None
    if len(diffs) >= 10:
        from wc_predictor.evaluation.metrics import bootstrap_ci

        _, lo, hi, _ = bootstrap_ci(diffs, n_boot=2000, seed=11)
        ci95 = [lo, hi]
    return {
        "mode_a": mode_a,
        "mode_b": mode_b,
        "n": len(fids),
        "mean_rps_a": _mean([a[f]["rps"] for f in fids]),
        "mean_rps_b": _mean([b[f]["rps"] for f in fids]),
        "mean_diff": _mean(diffs),
        "ci95": ci95,
        "fixtures": fids,
    }


def calibration_summary(resolved: list[dict], *, mode: str | None = None) -> dict:
    """Leak-free temperature fit on the agent's OWN resolved forecasts.

    Grid-searches a single temperature minimizing mean RPS over the resolved rows.
    temp > 1 softens (model was overconfident), < 1 sharpens. Returns the fitted
    temp + the RPS it achieves so future ``deterministic_analyst`` calls can use it.
    """

    rows = [x for x in resolved if x["resolved"]
            and (mode is None or str(x.get("mode")) == mode)]
    if len(rows) < 10:  # too little history to trust a recalibration
        return {"temp": 1.0, "n": len(rows), "mean_rps": None, "fitted": False}

    def _rps_at(temp: float) -> float:
        total = 0.0
        for x in rows:
            p = [max(1e-9, v) ** (1.0 / temp) for v in (x["p_home"], x["p_draw"], x["p_away"])]
            s = sum(p)
            total += ranked_probability_score(tuple(v / s for v in p), x["actual"])
        return total / len(rows)

    grid = [0.6 + 0.05 * i for i in range(0, 17)]  # 0.60 .. 1.40
    best_temp = min(grid, key=_rps_at)
    return {"temp": best_temp, "n": len(rows), "mean_rps": _rps_at(best_temp), "fitted": True}
