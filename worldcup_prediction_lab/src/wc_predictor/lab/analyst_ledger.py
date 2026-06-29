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
    seen = {str(r["fixture_id"]) for r in load_ledger(path)}
    path.parent.mkdir(parents=True, exist_ok=True)
    added = 0
    with path.open("a", encoding="utf-8") as fh:
        for f in forecasts:
            fid = str(f.fixture_id)
            if fid in seen:
                continue
            seen.add(fid)
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
