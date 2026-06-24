"""Generate predictions for every registered variant at an as_of, then rank.

One command for the daily loop's "produce today's candidate predictions" step:
loads silver, derives the training cutoff (latest completed result <= as_of),
writes each variant's immutable prediction file, and refreshes the leaderboard.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from wc_predictor.forecast_live import load_silver_data
from wc_predictor.lab import registry
from wc_predictor.lab.experiment import generate_variant_predictions
from wc_predictor.lab.leaderboard import refresh
from wc_predictor.run_daily_update import _derive_training_cutoff


def run(as_of: str | None = None, *, training_cutoff: str | None = None) -> dict:
    as_of_date = as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    matches_df, fixtures_df, teams_df = load_silver_data()
    cutoff = training_cutoff or _derive_training_cutoff(matches_df, as_of=as_of_date)

    generated: list[str] = []
    for info in registry.list_variants():
        generate_variant_predictions(
            info.variant_id,
            matches_df=matches_df,
            fixtures_df=fixtures_df,
            teams_df=teams_df,
            as_of=as_of_date,
            training_cutoff=cutoff,
        )
        generated.append(info.variant_id)

    standings = refresh()
    from wc_predictor.lab.backtest import run_backtest
    from wc_predictor.lab.dashboard import build_dashboard

    run_backtest()  # refresh the walk-forward backtest cache before rendering
    build_dashboard()
    return {
        "as_of": as_of_date,
        "training_cutoff": cutoff,
        "variants": generated,
        "scored": sum(s.n_scored for s in standings),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate variant predictions + leaderboard.")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--training-cutoff", default=None, help="YYYY-MM-DD (default: latest completed)")
    args = parser.parse_args()
    summary = run(args.as_of, training_cutoff=args.training_cutoff)
    print(
        f"[experiments] as_of={summary['as_of']} cutoff={summary['training_cutoff']} "
        f"variants={len(summary['variants'])} scored={summary['scored']}"
    )
    for variant_id in summary["variants"]:
        print(f"  generated {variant_id}")


if __name__ == "__main__":
    main()
