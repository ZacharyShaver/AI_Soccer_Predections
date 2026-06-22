"""Run the live tournament Monte Carlo and write the championship-odds report.

Trains Elo through the training cutoff (host-aware), holds already-played group
results fixed, simulates the rest of the 2026 World Cup ``n_sims`` times, and
writes a committed report sorted by championship probability.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.forecast_live import build_world_cup_host_advantage_fn
from wc_predictor.models.elo import EloModel
from wc_predictor.simulate.montecarlo import TournamentSimulator, run_tournament_simulation

AS_OF = "2026-06-21"
TRAINING_CUTOFF = "2026-06-20"
DEFAULT_N_SIMS = 20000
DEFAULT_SEED = 0


def _read_parquet(path) -> pd.DataFrame:
    # DuckDB-only parquet read: this lab declares duckdb but not pyarrow/fastparquet.
    import duckdb

    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(
            f"SELECT * FROM read_parquet('{escaped_path}')"
        ).df()


def _load():
    matches = _read_parquet(settings.SILVER_DIR / "martj42_matches.parquet")
    fixtures = _read_parquet(settings.SILVER_DIR / "openfootball_worldcup_2026_fixtures.parquet")
    teams = _read_parquet(settings.SILVER_DIR / "martj42_teams.parquet")
    matches["date"] = pd.to_datetime(matches["date"])
    return matches, fixtures, teams


def _team_group_map(fixtures: pd.DataFrame) -> dict[str, str]:
    group_fx = fixtures[fixtures["stage"] == "group"]
    mapping: dict[str, str] = {}
    for r in group_fx.itertuples(index=False):
        mapping[str(r.home_team_id)] = str(r.group)
        mapping[str(r.away_team_id)] = str(r.group)
    return mapping


def run(as_of=AS_OF, training_cutoff=TRAINING_CUTOFF, n_sims=DEFAULT_N_SIMS, seed=DEFAULT_SEED):
    matches, fixtures, teams = _load()
    name = dict(zip(teams["canonical_team_id"].astype(str), teams["canonical_name"]))
    group_of = _team_group_map(fixtures)

    train = matches[matches["date"] <= pd.Timestamp(training_cutoff)]
    model = EloModel(host_advantage_fn=build_world_cup_host_advantage_fn()).fit(train)

    table = run_tournament_simulation(model, matches, fixtures, n_sims=n_sims, seed=seed, as_of=as_of)
    table["team"] = table["team_id"].map(lambda t: name.get(t, t))
    table["group"] = table["team_id"].map(lambda t: group_of.get(t, "?"))
    table["elo"] = table["team_id"].map(model.get_rating)
    return model, table


def _format_report(table: pd.DataFrame, as_of: str, training_cutoff: str, n_sims: int, seed: int, determinism_ok: bool) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pct = lambda x: f"{x * 100:.1f}%"
    lines = [
        f"# World Cup 2026 championship odds (as of {as_of})",
        "",
        "Monte Carlo simulation from `elo_poisson_v1` — the model bar proven in M6 (Elo beats",
        "climatology on a 15,817-match walk-forward backtest). These are **Elo-only** odds: no",
        "market prices, injuries, lineups, or travel. Tournament variance is large; even strong",
        "favourites rarely exceed ~20-25% to win the whole thing.",
        "",
        "## Method",
        "",
        f"- Trained on completed international results through `{training_cutoff}` (host-aware Elo).",
        f"- Already-played 2026 group results are held FIXED; remaining matches simulated.",
        f"- Simulations: {n_sims:,}, seed {seed}. Group tiebreakers per FIFA; 8 best third-placed",
        "  teams allocated to the Round of 32 by constraint-matching the official candidate lists",
        "  (documented approximation). Knockout draws resolved as conditional-on-not-draw.",
        f"- Host advantage applied to USA/Canada/Mexico when playing in their own country.",
        f"- Determinism check (two seeded runs identical): {'PASS' if determinism_ok else 'FAIL'}.",
        f"- Report generated {generated}.",
        "",
        "## Championship odds (sorted by P(Win))",
        "",
        "| # | Team | Grp | Elo | P(Adv) | P(R16) | P(QF) | P(SF) | P(Final) | P(Win) |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for i, r in enumerate(table.itertuples(index=False), start=1):
        lines.append(
            f"| {i} | {r.team} | {r.group} | {r.elo:.0f} | {pct(r.p_advance)} | {pct(r.p_r16)} | "
            f"{pct(r.p_qf)} | {pct(r.p_sf)} | {pct(r.p_final)} | **{pct(r.p_win)}** |"
        )
    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- Elo-only; a market-calibrated comparison comes in P6.",
            "- Knockout bracket third-place allocation is a constraint-satisfying approximation of",
            "  FIFA's official table (always respects the candidate-group constraints).",
            "- Probabilities are nested by construction: P(Win) <= P(Final) <= ... <= P(Adv).",
            "",
        ]
    )
    return "\n".join(lines)


def main(n_sims: int = DEFAULT_N_SIMS, seed: int = DEFAULT_SEED) -> pd.DataFrame:
    model, table = run(n_sims=n_sims, seed=seed)

    # determinism check on a small N (two identical seeded runs)
    matches, fixtures, _ = _load()
    sim = TournamentSimulator(model, fixtures, matches=matches, as_of=AS_OF)
    determinism_ok = sim.run(200, seed=99).equals(sim.run(200, seed=99))

    report = _format_report(table, AS_OF, TRAINING_CUTOFF, n_sims, seed, determinism_ok)
    out_path = settings.REPORTS_DIR / "backtests" / f"championship_odds_{AS_OF}.md"
    out_path.write_text(report, encoding="utf-8")

    top = table.head(12)
    print(f"n_sims={n_sims} seed={seed} determinism={'PASS' if determinism_ok else 'FAIL'}")
    print(f"wrote {out_path}")
    for r in top.itertuples(index=False):
        print(f"  {r.team:<26} grp {r.group}  Elo {r.elo:6.0f}  P(win) {r.p_win*100:5.1f}%  P(adv) {r.p_advance*100:5.1f}%")
    return table


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N_SIMS
    main(n_sims=n)
