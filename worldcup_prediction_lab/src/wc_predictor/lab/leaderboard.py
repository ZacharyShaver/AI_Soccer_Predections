"""Score every variant's recorded predictions against results and rank them.

For each (variant, match) we keep the most-informed prediction (latest as_of,
which is still strictly before kickoff by construction), score the resolved ones
via the L0 score_ledger, and rank variants by mean RPS. The baseline variant is
the bar: each challenger's edge is reported as (baseline RPS - variant RPS).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.score_ledger import score_ledger
from wc_predictor.lab import registry
from wc_predictor.lab.experiment import read_variant_predictions

BASELINE_VARIANT = "elo_baseline"
MATCHES_FILE = "martj42_matches.parquet"


def _read_parquet(path) -> pd.DataFrame:
    # DuckDB-only parquet read (this lab declares duckdb, not pyarrow).
    import duckdb

    escaped = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(f"SELECT * FROM read_parquet('{escaped}')").df()


def load_results(matches_path: str | Path | None = None) -> pd.DataFrame:
    path = Path(matches_path) if matches_path else settings.SILVER_DIR / MATCHES_FILE
    if not path.exists():
        return pd.DataFrame(columns=["match_id", "home_score", "away_score"])
    return _read_parquet(path)


def collect_predictions(experiments_root: str | Path = settings.EXPERIMENTS_DIR) -> pd.DataFrame:
    """One row per (variant_id, match_id): the latest-as_of recorded prediction."""

    root = Path(experiments_root)
    records: list[dict] = []
    if root.exists():
        for date_dir in sorted(root.glob("date=*")):
            as_of = date_dir.name.split("=", 1)[1]
            for variant_file in sorted(date_dir.glob("*.jsonl")):
                for row in read_variant_predictions(variant_file):
                    row = dict(row)
                    row["variant_id"] = variant_file.stem
                    row["as_of_partition"] = as_of
                    records.append(row)
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records)
    frame = frame.sort_values(["variant_id", "match_id", "as_of_partition"], kind="mergesort")
    return frame.drop_duplicates(["variant_id", "match_id"], keep="last").reset_index(drop=True)


@dataclass(frozen=True)
class VariantStanding:
    variant_id: str
    n_scored: int
    mean_rps: float | None
    mean_log_loss: float | None
    mean_brier: float | None
    decisive_accuracy: float | None
    edge_vs_baseline_rps: float | None  # baseline_rps - variant_rps (positive = better)


def build_standings(
    *,
    experiments_root: str | Path = settings.EXPERIMENTS_DIR,
    results_df: pd.DataFrame | None = None,
) -> list[VariantStanding]:
    predictions = collect_predictions(experiments_root)
    results = load_results() if results_df is None else results_df

    standings: dict[str, VariantStanding] = {}
    baseline_rps: float | None = None

    variant_ids = sorted(predictions["variant_id"].unique()) if not predictions.empty else []
    # Always show registered variants even before they have scored matches.
    for info in registry.list_variants():
        if info.variant_id not in variant_ids:
            variant_ids.append(info.variant_id)

    per_variant_agg: dict[str, dict] = {}
    for variant_id in variant_ids:
        rows = (
            predictions.loc[predictions["variant_id"] == variant_id].to_dict("records")
            if not predictions.empty
            else []
        )
        _eval, agg = score_ledger(rows, results)
        per_variant_agg[variant_id] = agg
        if variant_id == BASELINE_VARIANT:
            baseline_rps = agg["mean_rps"]

    for variant_id in variant_ids:
        agg = per_variant_agg[variant_id]
        edge = None
        if baseline_rps is not None and agg["mean_rps"] is not None:
            edge = round(baseline_rps - agg["mean_rps"], 6)
        standings[variant_id] = VariantStanding(
            variant_id=variant_id,
            n_scored=int(agg["n_scored"]),
            mean_rps=agg["mean_rps"],
            mean_log_loss=agg["mean_log_loss"],
            mean_brier=agg["mean_brier"],
            decisive_accuracy=agg["decisive_accuracy"],
            edge_vs_baseline_rps=edge,
        )

    # Rank: scored variants by mean RPS (asc); unscored variants last.
    def sort_key(s: VariantStanding):
        return (s.mean_rps is None, s.mean_rps if s.mean_rps is not None else 0.0)

    return sorted(standings.values(), key=sort_key)


def _fmt(value: float | None, digits: int = 4) -> str:
    return f"{value:.{digits}f}" if value is not None else "n/a"


def _fmt_signed(value: float | None) -> str:
    return f"{value:+.4f}" if value is not None else "n/a"


def format_leaderboard(standings: list[VariantStanding]) -> str:
    descriptions = {i.variant_id: i for i in registry.list_variants()}
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_scored = sum(s.n_scored for s in standings)

    lines = [
        "# Daily Model-Research Leaderboard",
        "",
        f"Generated: `{generated}`",
        "",
        "Each variant is scored on its most-informed pre-kickoff prediction per match "
        "(latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS "
        "(positive = beats the baseline). Every challenger must beat **elo_baseline**.",
        "",
        f"- Total scored predictions across variants: {total_scored}",
        f"- Registered variants: {len(standings)}",
        "",
        "| Rank | Variant | n | RPS | log loss | Brier | Decisive acc | Edge vs baseline |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, s in enumerate(standings, start=1):
        tag = " (baseline)" if s.variant_id == BASELINE_VARIANT else ""
        lines.append(
            f"| {rank} | `{s.variant_id}`{tag} | {s.n_scored} | {_fmt(s.mean_rps)} | "
            f"{_fmt(s.mean_log_loss)} | {_fmt(s.mean_brier)} | "
            f"{_fmt(s.decisive_accuracy, 3)} | {_fmt_signed(s.edge_vs_baseline_rps)} |"
        )

    lines += ["", "## Variants", ""]
    for s in standings:
        info = descriptions.get(s.variant_id)
        if info:
            lines.append(f"- `{s.variant_id}` — {info.description}  \n  feature: {info.feature_idea}")
        else:
            lines.append(f"- `{s.variant_id}` — (module not currently registered)")

    if total_scored == 0:
        lines += [
            "",
            "## Status",
            "",
            "- No predictions have resolved yet. Standings populate once the forecast "
            "matches are played and ingested (next daily run).",
        ]

    lines += [
        "",
        "## Caveats",
        "",
        "- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.",
        "- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.",
        "",
    ]
    return "\n".join(lines)


def refresh(
    *,
    experiments_root: str | Path = settings.EXPERIMENTS_DIR,
    results_df: pd.DataFrame | None = None,
    out_path: str | Path | None = None,
) -> list[VariantStanding]:
    standings = build_standings(experiments_root=experiments_root, results_df=results_df)
    target = Path(out_path) if out_path else settings.RESEARCH_DIR / "LEADERBOARD.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_leaderboard(standings), encoding="utf-8")
    return standings


def main() -> None:
    standings = refresh()
    print(f"[leaderboard] variants={len(standings)} scored={sum(s.n_scored for s in standings)}")
    for s in standings:
        print(f"  {s.variant_id}: n={s.n_scored} rps={_fmt(s.mean_rps)} edge={_fmt_signed(s.edge_vs_baseline_rps)}")


if __name__ == "__main__":
    main()
