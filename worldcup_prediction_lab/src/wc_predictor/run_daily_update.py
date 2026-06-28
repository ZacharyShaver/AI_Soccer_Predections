"""Daily live refresh orchestration for as-of forecasts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.forecast_live import load_silver_data, run_live_forecast


@dataclass(frozen=True)
class DailyUpdateSummary:
    as_of: str
    training_cutoff: str
    forecast_count: int
    ledger_path: Path
    report_path: Path
    dashboard_path: Path
    pages_path: Path
    refreshed_results: bool
    refreshed_odds: bool


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _derive_training_cutoff(matches_df: pd.DataFrame, *, as_of: str) -> str:
    if {"date", "home_score", "away_score"} - set(matches_df.columns):
        missing = {"date", "home_score", "away_score"} - set(matches_df.columns)
        raise ValueError(f"matches_df missing required columns: {sorted(missing)}")

    matches = matches_df.copy()
    matches["date"] = pd.to_datetime(matches["date"], errors="coerce")
    as_of_ts = pd.Timestamp(as_of)
    completed = matches["home_score"].notna() & matches["away_score"].notna()
    eligible_dates = matches.loc[
        completed & matches["date"].notna() & (matches["date"] <= as_of_ts),
        "date",
    ]
    if eligible_dates.empty:
        return (as_of_ts - timedelta(days=1)).strftime("%Y-%m-%d")
    return pd.Timestamp(eligible_dates.max()).strftime("%Y-%m-%d")


def refresh_compiled_reports() -> tuple[Path, Path]:
    """Refresh all derived research reports after data/predictions are compiled."""

    from wc_predictor.lab.backtest import run_backtest
    from wc_predictor.lab.dashboard import PAGES_OUT_PATH, build_dashboard
    from wc_predictor.lab.leaderboard import refresh

    refresh()
    run_backtest()
    dashboard_path = build_dashboard()
    return dashboard_path, PAGES_OUT_PATH


def run_daily_update(
    as_of: str | None = None,
    *,
    training_cutoff: str | None = None,
    silver_dir: str | Path = settings.SILVER_DIR,
    runs_dir: str | Path = settings.RUNS_DIR,
    reports_dir: str | Path = settings.REPORTS_DIR,
    refresh_results: bool = True,
    refresh_odds: bool = True,
    refresh_reports: bool = True,
    refresh_overlay: bool = False,
    n_sims: int = 20000,
    seed: int = 0,
) -> DailyUpdateSummary:
    as_of_date = as_of or _today_utc()
    generated_at_utc = f"{as_of_date}T00:00:00Z"

    if refresh_results:
        from wc_predictor.data import ingest_international_results

        ingest_international_results.ingest(silver_dir=silver_dir)

        # Resolve knockout bracket placeholders (group winners/runners-up and
        # match-winner propagation) into real team ids from the freshly ingested
        # results, so the now-determined knockout games become forecastable.
        from wc_predictor.bracket_resolver import resolve_and_persist_fixtures

        resolve_and_persist_fixtures(silver_dir=silver_dir)

    matches_df, fixtures_df, teams_df = load_silver_data(silver_dir)
    effective_training_cutoff = training_cutoff or _derive_training_cutoff(
        matches_df,
        as_of=as_of_date,
    )
    live_summary = run_live_forecast(
        matches_df=matches_df,
        fixtures_df=fixtures_df,
        teams_df=teams_df,
        runs_dir=runs_dir,
        reports_dir=reports_dir,
        as_of=as_of_date,
        training_cutoff=effective_training_cutoff,
        generated_at_utc=generated_at_utc,
    )

    if refresh_odds:
        from wc_predictor.simulate import run_championship_odds

        run_championship_odds.run(
            as_of=as_of_date,
            training_cutoff=effective_training_cutoff,
            n_sims=n_sims,
            seed=seed,
        )

    if refresh_overlay:
        # Market overlay needs a live Polymarket fetch; never let a network or
        # parsing failure break the daily Elo pipeline. Predictions are immutable,
        # so the overlay ledger accumulates and is scored as results resolve.
        try:
            from wc_predictor import forecast_overlay

            forecast_overlay.run(
                as_of=as_of_date,
                training_cutoff=effective_training_cutoff,
                generated_at_utc=generated_at_utc,
                reports_dir=reports_dir,
            )
            forecast_overlay.score(as_of=as_of_date, reports_dir=reports_dir)
        except Exception as error:  # noqa: BLE001 - resilience over strictness here
            print(f"[run_daily_update] overlay skipped: {error}", flush=True)

    if refresh_reports:
        dashboard_path, pages_path = refresh_compiled_reports()
    else:
        dashboard_path, pages_path = Path(), Path()

    return DailyUpdateSummary(
        as_of=as_of_date,
        training_cutoff=effective_training_cutoff,
        forecast_count=live_summary.forecast_count,
        ledger_path=live_summary.ledger_path,
        report_path=live_summary.report_path,
        dashboard_path=dashboard_path,
        pages_path=pages_path,
        refreshed_results=refresh_results,
        refreshed_odds=refresh_odds,
    )


def _summary_payload(summary: DailyUpdateSummary) -> dict[str, Any]:
    payload = asdict(summary)
    # Stringify every Path field so the summary is JSON-serializable. asdict()
    # leaves Path values intact (e.g. dashboard_path/pages_path), which json
    # cannot encode.
    for key, value in payload.items():
        if isinstance(value, Path):
            payload[key] = str(value)
    return payload


def main() -> None:
    summary = run_daily_update()
    print(json.dumps(_summary_payload(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
