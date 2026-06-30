"""Live championship-odds artifact for the dashboard 'tournament standings' section.

The Monte Carlo tournament sim (~3 min at 20k sims) is far too slow to run on every
dashboard build, so we decouple: ``refresh`` runs the sim and writes a small JSON;
the dashboard ``_standings_section`` just reads it (instant). The daily job (and an
on-demand CLI) regenerate the JSON, so the standings stay current as knockouts
resolve without slowing interactive builds.

Reuses the P4 engine via ``simulate.run_championship_odds.run`` (host-aware Elo,
played results held fixed, FIFA tiebreakers, bracket allocation).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from wc_predictor.config import settings

ODDS_PATH = settings.RUNS_DIR / "standings" / "championship_odds.json"


def refresh(
    as_of: str,
    *,
    training_cutoff: str | None = None,
    n_sims: int = 20000,
    seed: int = 0,
    out_path: str | Path = ODDS_PATH,
) -> dict:
    """Run the tournament sim as-of `as_of` and write the odds JSON. Returns it."""

    from wc_predictor.simulate.run_championship_odds import run

    training_cutoff = training_cutoff or as_of
    _model, table = run(as_of=as_of, training_cutoff=training_cutoff, n_sims=n_sims, seed=seed)
    table = table.sort_values("p_win", ascending=False)
    teams = [
        {
            "team": str(r.team), "group": str(r.group), "elo": float(r.elo),
            "p_advance": float(r.p_advance), "p_r16": float(r.p_r16), "p_qf": float(r.p_qf),
            "p_sf": float(r.p_sf), "p_final": float(r.p_final), "p_win": float(r.p_win),
        }
        for r in table.itertuples(index=False)
    ]
    payload = {
        "as_of": str(as_of),
        "training_cutoff": str(training_cutoff),
        "n_sims": int(n_sims),
        "seed": int(seed),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "teams": teams,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load(out_path: str | Path = ODDS_PATH) -> dict | None:
    p = Path(out_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Refresh the championship-odds JSON")
    ap.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    ap.add_argument("--training-cutoff", default=None, help="defaults to --as-of")
    ap.add_argument("--n-sims", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    payload = refresh(a.as_of, training_cutoff=a.training_cutoff, n_sims=a.n_sims, seed=a.seed)
    print(f"wrote {ODDS_PATH} ({len(payload['teams'])} teams, {a.n_sims} sims, as of {a.as_of})")
    for t in payload["teams"][:8]:
        print(f"  {t['team']:<24} P(win) {t['p_win']*100:5.1f}%  P(final) {t['p_final']*100:5.1f}%")


if __name__ == "__main__":
    main()
