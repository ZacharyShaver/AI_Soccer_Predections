"""Running scorecard for immutable live forecasts vs results and market odds."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.elo_vs_market import align_matches_with_market
from wc_predictor.evaluation.metrics import (
    OUTCOME_ORDER,
    brier_score,
    bootstrap_ci,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.evaluation.score_ledger import PredictionInput, score_ledger


CI_FLOOR = 30
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 0
MATCHES_FILE = "martj42_matches.parquet"
MARKET_ODDS_FILE = "footballdata_market_odds.parquet"


@dataclass(frozen=True)
class ConfidenceInterval:
    point: float
    lo: float
    hi: float
    n: int


@dataclass(frozen=True)
class MetricEstimate:
    point: float | None
    n: int
    ci: ConfidenceInterval | None
    ci_omitted_reason: str | None


@dataclass(frozen=True)
class MarketComparison:
    paired_n: int
    metrics: dict[str, dict[str, MetricEstimate]]
    message: str


@dataclass(frozen=True)
class ScorecardReport:
    aggregate: dict[str, float | int | None]
    our_metrics: dict[str, MetricEstimate]
    market_comparison: MarketComparison
    notable_hits: list[dict[str, Any]]
    notable_misses: list[dict[str, Any]]
    messages: list[str]
    ci_floor: int


def _read_parquet(path: str | Path) -> pd.DataFrame:
    # DuckDB-only parquet read: this lab declares duckdb but not pyarrow/fastparquet.
    import duckdb

    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(f"SELECT * FROM read_parquet('{escaped_path}')").df()


def _ensure_result_columns(results_df: pd.DataFrame) -> pd.DataFrame:
    if {"match_id", "home_score", "away_score"}.issubset(results_df.columns):
        return results_df
    return pd.DataFrame(columns=["match_id", "home_score", "away_score"])


def _finite(values: Iterable[Any]) -> list[float]:
    finite: list[float] = []
    for value in values:
        if value is None or pd.isna(value):
            continue
        numeric = float(value)
        if math.isfinite(numeric):
            finite.append(numeric)
    return finite


def _metric_estimate(values: Iterable[Any], *, ci_floor: int) -> MetricEstimate:
    finite = _finite(values)
    n = len(finite)
    if n == 0:
        return MetricEstimate(
            point=None,
            n=0,
            ci=None,
            ci_omitted_reason="no finite values",
        )

    point = sum(finite) / n
    if n < ci_floor:
        return MetricEstimate(
            point=point,
            n=n,
            ci=None,
            ci_omitted_reason=f"n={n} < ci_floor={ci_floor}",
        )

    ci_point, lo, hi, ci_n = bootstrap_ci(
        finite,
        n_boot=BOOTSTRAP_N,
        alpha=0.05,
        seed=BOOTSTRAP_SEED,
    )
    return MetricEstimate(
        point=point,
        n=n,
        ci=ConfidenceInterval(point=ci_point, lo=lo, hi=hi, n=ci_n),
        ci_omitted_reason=None,
    )


def _argmax_outcome(row: Mapping[str, Any]) -> str:
    probs = [float(row["prob_home"]), float(row["prob_draw"]), float(row["prob_away"])]
    return OUTCOME_ORDER[max(range(len(probs)), key=lambda index: probs[index])]


def _normalize_market(
    market_df: pd.DataFrame | None,
    results_df: pd.DataFrame,
) -> pd.DataFrame:
    columns = ["match_id", "market_prob_home", "market_prob_draw", "market_prob_away"]
    if market_df is None or market_df.empty:
        return pd.DataFrame(columns=columns)

    market = market_df.copy()
    if set(columns).issubset(market.columns):
        normalized = market.loc[:, columns].copy()
    elif {"match_id", "prob_home", "prob_draw", "prob_away"}.issubset(market.columns):
        normalized = market.loc[
            :, ["match_id", "prob_home", "prob_draw", "prob_away"]
        ].rename(
            columns={
                "prob_home": "market_prob_home",
                "prob_draw": "market_prob_draw",
                "prob_away": "market_prob_away",
            }
        )
    else:
        aligned, _summary = align_matches_with_market(results_df, market)
        if aligned.empty:
            return pd.DataFrame(columns=columns)
        normalized = aligned.loc[:, columns].copy()

    normalized = normalized.dropna(subset=columns)
    if normalized.empty:
        return pd.DataFrame(columns=columns)

    # Keep one market probability vector per match for the live scorecard.
    return (
        normalized.assign(match_id=normalized["match_id"].astype(str))
        .groupby("match_id", as_index=False)[
            ["market_prob_home", "market_prob_draw", "market_prob_away"]
        ]
        .mean()
        .sort_values("match_id", kind="mergesort")
        .reset_index(drop=True)
    )


def _score_market_pairs(paired: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in paired.iterrows():
        outcome = str(row["actual_outcome"])
        our_probs = [
            float(row["prob_home"]),
            float(row["prob_draw"]),
            float(row["prob_away"]),
        ]
        market_probs = [
            float(row["market_prob_home"]),
            float(row["market_prob_draw"]),
            float(row["market_prob_away"]),
        ]
        our_log_loss = home_draw_away_log_loss(our_probs, outcome)
        our_brier = brier_score(our_probs, outcome)
        our_rps = ranked_probability_score(our_probs, outcome)
        market_log_loss = home_draw_away_log_loss(market_probs, outcome)
        market_brier = brier_score(market_probs, outcome)
        market_rps = ranked_probability_score(market_probs, outcome)
        rows.append(
            {
                "match_id": row["match_id"],
                "our_log_loss": our_log_loss,
                "our_brier": our_brier,
                "our_rps": our_rps,
                "market_log_loss": market_log_loss,
                "market_brier": market_brier,
                "market_rps": market_rps,
                "diff_log_loss": market_log_loss - our_log_loss,
                "diff_brier": market_brier - our_brier,
                "diff_rps": market_rps - our_rps,
            }
        )
    return pd.DataFrame(rows)


def _market_comparison(
    evaluation: pd.DataFrame,
    market_df: pd.DataFrame | None,
    results_df: pd.DataFrame,
    *,
    ci_floor: int,
) -> MarketComparison:
    if evaluation.empty:
        return MarketComparison(
            paired_n=0,
            metrics={},
            message="No scored ledger forecasts are available for market comparison.",
        )

    market = _normalize_market(market_df, results_df)
    if market.empty:
        return MarketComparison(
            paired_n=0,
            metrics={},
            message="No overlapping market data for scored ledger forecasts.",
        )

    paired = evaluation.merge(market, on="match_id", how="inner")
    if paired.empty:
        return MarketComparison(
            paired_n=0,
            metrics={},
            message="No overlapping market data for scored ledger forecasts.",
        )

    paired_scores = _score_market_pairs(paired)
    metrics = {
        "rps": {
            "ours": _metric_estimate(paired_scores["our_rps"], ci_floor=ci_floor),
            "market": _metric_estimate(paired_scores["market_rps"], ci_floor=ci_floor),
            "diff_market_minus_ours": _metric_estimate(
                paired_scores["diff_rps"], ci_floor=ci_floor
            ),
        },
        "log_loss": {
            "ours": _metric_estimate(paired_scores["our_log_loss"], ci_floor=ci_floor),
            "market": _metric_estimate(
                paired_scores["market_log_loss"], ci_floor=ci_floor
            ),
            "diff_market_minus_ours": _metric_estimate(
                paired_scores["diff_log_loss"], ci_floor=ci_floor
            ),
        },
        "brier": {
            "ours": _metric_estimate(paired_scores["our_brier"], ci_floor=ci_floor),
            "market": _metric_estimate(paired_scores["market_brier"], ci_floor=ci_floor),
            "diff_market_minus_ours": _metric_estimate(
                paired_scores["diff_brier"], ci_floor=ci_floor
            ),
        },
    }
    return MarketComparison(
        paired_n=int(len(paired_scores)),
        metrics=metrics,
        message="Market comparison uses only matches present in both scored ledger and market data.",
    )


def _notables(evaluation: pd.DataFrame, *, called_it: bool, limit: int = 5) -> list[dict[str, Any]]:
    if evaluation.empty or "called_it" not in evaluation.columns:
        return []

    subset = evaluation.loc[evaluation["called_it"].astype(bool) == called_it].copy()
    if subset.empty:
        return []

    subset = subset.assign(predicted_outcome=subset.apply(_argmax_outcome, axis=1))
    subset = subset.sort_values(
        ["rps", "log_loss", "match_id"],
        ascending=[called_it, called_it, True],
        kind="mergesort",
    )
    notables: list[dict[str, Any]] = []
    for row in subset.head(limit).to_dict(orient="records"):
        notables.append(
            {
                "match_id": row["match_id"],
                "prediction_id": row.get("prediction_id"),
                "actual_outcome": row["actual_outcome"],
                "predicted_outcome": row["predicted_outcome"],
                "rps": round(float(row["rps"]), 6),
                "log_loss": (
                    round(float(row["log_loss"]), 6)
                    if math.isfinite(float(row["log_loss"]))
                    else math.inf
                ),
            }
        )
    return notables


def build_scorecard(
    predictions: PredictionInput,
    results_df: pd.DataFrame,
    *,
    market_df: pd.DataFrame | None = None,
    ci_floor: int = CI_FLOOR,
) -> ScorecardReport:
    """Build a deterministic running scorecard for ledger predictions."""

    results = _ensure_result_columns(results_df)
    try:
        evaluation, aggregate = score_ledger(predictions, results)
    except FileNotFoundError:
        evaluation, aggregate = score_ledger([], results)

    our_metrics = {
        "rps": _metric_estimate(
            evaluation["rps"] if "rps" in evaluation.columns else [], ci_floor=ci_floor
        ),
        "log_loss": _metric_estimate(
            evaluation["log_loss"] if "log_loss" in evaluation.columns else [],
            ci_floor=ci_floor,
        ),
        "brier": _metric_estimate(
            evaluation["brier"] if "brier" in evaluation.columns else [],
            ci_floor=ci_floor,
        ),
    }
    market_comparison = _market_comparison(
        evaluation,
        market_df,
        results,
        ci_floor=ci_floor,
    )

    messages: list[str] = []
    if aggregate["n_scored"] == 0:
        messages.append("No ledger forecasts have resolved yet.")
    if aggregate["n_scored"] and int(aggregate["n_scored"]) < ci_floor:
        messages.append(
            f"Ledger sample is small: n_scored={aggregate['n_scored']} < ci_floor={ci_floor}."
        )
    if market_comparison.paired_n and market_comparison.paired_n < ci_floor:
        messages.append(
            "Market paired sample is small: "
            f"paired_n={market_comparison.paired_n} < ci_floor={ci_floor}."
        )

    return ScorecardReport(
        aggregate=aggregate,
        our_metrics=our_metrics,
        market_comparison=market_comparison,
        notable_hits=_notables(evaluation, called_it=True),
        notable_misses=_notables(evaluation, called_it=False),
        messages=messages,
        ci_floor=ci_floor,
    )


def _fmt_metric(metric: MetricEstimate) -> str:
    if metric.point is None:
        return "n/a"
    if metric.ci is None:
        reason = metric.ci_omitted_reason or "CI omitted"
        return f"{metric.point:.4f} (CI omitted: {reason})"
    return f"{metric.point:.4f} [{metric.ci.lo:.4f}, {metric.ci.hi:.4f}]"


def _fmt_diff(metric: MetricEstimate) -> str:
    if metric.point is None:
        return "n/a"
    if metric.ci is None:
        reason = metric.ci_omitted_reason or "CI omitted"
        return f"{metric.point:+.5f} (CI omitted: {reason})"
    return f"{metric.point:+.5f} [{metric.ci.lo:+.5f}, {metric.ci.hi:+.5f}]"


def _notable_lines(notables: list[dict[str, Any]]) -> list[str]:
    if not notables:
        return ["- None yet."]
    return [
        "- "
        f"{row['match_id']}: predicted {row['predicted_outcome']}, "
        f"actual {row['actual_outcome']}, RPS {row['rps']:.4f}, "
        f"log loss {row['log_loss']:.4f}"
        for row in notables
    ]


def format_scorecard_report(report: ScorecardReport) -> str:
    aggregate = report.aggregate
    lines = [
        "# Running Forecast Scorecard",
        "",
        "Lower is better for RPS, home/draw/away log loss, and Brier score.",
        "Market differences are `market - ours`, so negative means market scored better",
        "on the paired subset and positive means our ledger forecasts scored better.",
        "",
        "## Ledger Coverage",
        "",
        f"- Ledger predictions: {aggregate['n_total']:,}",
        f"- Scored predictions: {aggregate['n_scored']:,}",
        f"- Pending predictions: {aggregate['n_pending']:,}",
    ]
    if report.messages:
        lines.extend(["", "## Current Status", ""])
        lines.extend(f"- {message}" for message in report.messages)

    lines.extend(
        [
            "",
            "## Our Running Metrics",
            "",
            f"Bootstrap 95% CIs are reported once the metric has at least {report.ci_floor} finite observations.",
            "",
            "| Metric | n | Mean |",
            "| --- | ---: | --- |",
            f"| RPS | {report.our_metrics['rps'].n:,} | {_fmt_metric(report.our_metrics['rps'])} |",
            f"| H/D/A log loss | {report.our_metrics['log_loss'].n:,} | {_fmt_metric(report.our_metrics['log_loss'])} |",
            f"| Brier | {report.our_metrics['brier'].n:,} | {_fmt_metric(report.our_metrics['brier'])} |",
            "",
            "## Market Comparison",
            "",
            report.market_comparison.message,
            "",
            f"- Paired scored matches: {report.market_comparison.paired_n:,}",
        ]
    )

    if report.market_comparison.metrics:
        lines.extend(
            [
                "",
                "| Metric | Ours | Market | Market - ours |",
                "| --- | --- | --- | --- |",
            ]
        )
        for metric_name, label in (
            ("rps", "RPS"),
            ("log_loss", "H/D/A log loss"),
            ("brier", "Brier"),
        ):
            metrics = report.market_comparison.metrics[metric_name]
            lines.append(
                f"| {label} | {_fmt_metric(metrics['ours'])} | "
                f"{_fmt_metric(metrics['market'])} | "
                f"{_fmt_diff(metrics['diff_market_minus_ours'])} |"
            )

    lines.extend(
        [
            "",
            "## Notable Hits",
            "",
            *_notable_lines(report.notable_hits),
            "",
            "## Notable Misses",
            "",
            *_notable_lines(report.notable_misses),
            "",
            "## Caveats",
            "",
            "- Early in the tournament, resolved ledger forecasts may be zero or too few to support CIs.",
            "- Market comparison only uses matches with both a resolved ledger forecast and market probabilities.",
            "- Polymarket live snapshots are optional and are not assumed to join completed matches here.",
            "",
        ]
    )
    return "\n".join(lines)


def write_scorecard_report(report: ScorecardReport, report_path: str | Path) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_scorecard_report(report), encoding="utf-8")
    return path


def _prediction_input(predictions_dir: Path) -> Path | list[dict[str, Any]]:
    if predictions_dir.exists() and any(predictions_dir.rglob("*.jsonl")):
        return predictions_dir
    return []


def run(
    *,
    predictions_dir: str | Path = settings.RUNS_DIR / "predictions",
    matches_path: str | Path = settings.SILVER_DIR / MATCHES_FILE,
    market_odds_path: str | Path = settings.SILVER_DIR / MARKET_ODDS_FILE,
    report_path: str | Path = settings.REPORTS_DIR / "backtests" / "forecast_scorecard.md",
    ci_floor: int = CI_FLOOR,
) -> ScorecardReport:
    predictions = _prediction_input(Path(predictions_dir))
    matches = (
        _read_parquet(matches_path)
        if Path(matches_path).exists()
        else pd.DataFrame(columns=["match_id", "home_score", "away_score"])
    )
    market = _read_parquet(market_odds_path) if Path(market_odds_path).exists() else None
    report = build_scorecard(predictions, matches, market_df=market, ci_floor=ci_floor)
    write_scorecard_report(report, report_path)
    return report


def main() -> None:
    report_path = settings.REPORTS_DIR / "backtests" / "forecast_scorecard.md"
    report = run(report_path=report_path)
    print(
        "[scorecard] "
        f"n_total={report.aggregate['n_total']} "
        f"n_scored={report.aggregate['n_scored']} "
        f"paired_market_n={report.market_comparison.paired_n} "
        f"report={report_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
