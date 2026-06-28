"""Append-only ledger + scorer for the betting disagreement tool.

Keeps a durable tab of every signal the tool has flagged (BET and WATCH), the
price we'd have taken at first sighting, and — once the match resolves — whether
it won and the realized P&L. The WATCH track record is itself a live test of
market efficiency: if WATCH bets are net-negative, the honesty gate is right to
keep them out of BET.

Recording is idempotent: a (fixture_id, outcome) pair is written once, at its
first sighting, so re-running the dashboard never double-counts or moves the
"placed" price.
"""

from __future__ import annotations

import json
from pathlib import Path

from wc_predictor.config import settings
from wc_predictor.lab.betting import BetSignal

LEDGER_PATH = settings.EXPERIMENTS_DIR.parent / "betting" / "ledger.jsonl"

_PERSIST_FIELDS = (
    "fixture_id", "match_date", "venue", "home_team_name", "away_team_name",
    "outcome", "selection", "our_prob", "market_prob", "offered_price",
    "edge", "ev", "kelly_stake", "altitude_delta_elo", "structural", "recommendation",
)


def _outcome(home_score: int, away_score: int) -> str:
    return "home" if home_score > away_score else "away" if away_score > home_score else "draw"


def load_ledger(ledger_path: str | Path = LEDGER_PATH) -> list[dict]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_signals(
    signals: list[BetSignal], *, as_of: str, ledger_path: str | Path = LEDGER_PATH
) -> int:
    """Append signals not already in the ledger. Returns how many were new."""
    path = Path(ledger_path)
    seen = {(r["fixture_id"], r["outcome"]) for r in load_ledger(path)}
    path.parent.mkdir(parents=True, exist_ok=True)
    added = 0
    with path.open("a", encoding="utf-8") as fh:
        for s in signals:
            key = (s.fixture_id, s.outcome)
            if key in seen:
                continue
            seen.add(key)
            rec = {"snapshot_date": as_of, **{f: getattr(s, f) for f in _PERSIST_FIELDS}}
            fh.write(json.dumps(rec) + "\n")
            added += 1
    return added


def resolve_signals(ledger: list[dict], results: dict[str, tuple[int, int]]) -> list[dict]:
    """Attach resolution + P&L to each ledger row. Flat = 1 unit; Kelly = staked fraction."""
    out: list[dict] = []
    for r in ledger:
        row = dict(r)
        res = results.get(str(r["fixture_id"]))
        price = float(r["offered_price"])
        if res is None or not (0.0 < price < 1.0):
            row.update(resolved=False, actual=None, won=None, pnl_flat=0.0, pnl_kelly=0.0)
        else:
            actual = _outcome(int(res[0]), int(res[1]))
            won = r["outcome"] == actual
            ks = float(r.get("kelly_stake", 0.0))
            row.update(
                resolved=True,
                actual=actual,
                won=won,
                pnl_flat=(1.0 / price - 1.0) if won else -1.0,
                pnl_kelly=(ks * (1.0 / price - 1.0)) if won else -ks,
            )
        out.append(row)
    return out


def track_record(resolved: list[dict]) -> dict:
    """Aggregate hit rate + P&L/ROI by recommendation; count pending."""
    summary: dict = {}
    for group in ("BET", "WATCH"):
        rows = [x for x in resolved if x["resolved"] and x["recommendation"] == group]
        n = len(rows)
        hits = sum(1 for x in rows if x["won"])
        pnl_flat = sum(x["pnl_flat"] for x in rows)
        pnl_kelly = sum(x["pnl_kelly"] for x in rows)
        summary[group] = {
            "n": n,
            "hits": hits,
            "hit_rate": hits / n if n else None,
            "pnl_flat": pnl_flat,
            "roi_flat": pnl_flat / n if n else None,
            "pnl_kelly": pnl_kelly,
            "pending": sum(
                1 for x in resolved if not x["resolved"] and x["recommendation"] == group
            ),
        }
    return summary
