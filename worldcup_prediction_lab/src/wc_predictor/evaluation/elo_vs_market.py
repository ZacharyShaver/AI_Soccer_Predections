"""Historical Elo-vs-Football-Data market benchmark."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.metrics import (
    bootstrap_ci,
    brier_score,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.models.elo import EloModel


BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20260622
MIN_USABLE_SAMPLE = 150
MARKET_ODDS_FILE = "footballdata_market_odds.parquet"
MATCHES_FILE = "martj42_matches.parquet"


def _read_parquet(path) -> pd.DataFrame:
    # DuckDB-only parquet read: this lab declares duckdb but not pyarrow/fastparquet.
    import duckdb

    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(
            f"SELECT * FROM read_parquet('{escaped_path}')"
        ).df()


@dataclass(frozen=True)
class AlignmentSummary:
    total_odds_rows: int
    odds_rows_with_both_team_ids: int
    usable_joined_rows: int
    exact_joined_rows: int
    reversed_joined_rows: int
    top_unmatched_footballdata_names: list[tuple[str, int]]


@dataclass(frozen=True)
class MetricInterval:
    point: float
    low: float
    high: float
    n: int


@dataclass(frozen=True)
class EloVsMarketResult:
    alignment: AlignmentSummary
    scored: pd.DataFrame
    metrics: dict[str, dict[str, MetricInterval]]
    verdict: str
    report_path: Path


def _normalize_dates(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.normalize()
    return normalized


def _has_value(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype("string").str.strip() != "")


def _top_unmatched_names(
    market_odds: pd.DataFrame, *, limit: int = 20
) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for id_column, name_column in (
        ("home_team_id", "home_team_name"),
        ("away_team_id", "away_team_name"),
    ):
        if id_column not in market_odds.columns or name_column not in market_odds.columns:
            continue
        missing = market_odds[market_odds[id_column].isna()]
        for name in missing[name_column].dropna().astype(str):
            clean_name = name.strip()
            if clean_name:
                counts[clean_name] = counts.get(clean_name, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _result_columns(matches: pd.DataFrame) -> list[str]:
    preferred = [
        "match_id",
        "date",
        "home_team_id",
        "away_team_id",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "tournament",
        "city",
        "country",
        "neutral",
        "source",
        "occurrence_index",
    ]
    return [column for column in preferred if column in matches.columns]


def _finish_join(merged: pd.DataFrame, *, orientation: str) -> pd.DataFrame:
    result_columns = [
        column
        for column in _result_columns(merged)
        if column in merged.columns and not column.endswith("_market")
    ]
    joined = merged.loc[:, result_columns].copy()
    joined["market_row_id"] = merged["market_row_id"].astype(int)
    joined["market_orientation"] = orientation
    joined["bookmaker"] = merged["bookmaker"].astype(str)
    joined["source_sheet"] = merged["source_sheet"].astype(str)
    if orientation == "as_listed":
        joined["market_home_team_name"] = merged["home_team_name"].astype(str)
        joined["market_away_team_name"] = merged["away_team_name"].astype(str)
        joined["market_prob_home"] = merged["prob_home"].astype(float)
        joined["market_prob_draw"] = merged["prob_draw"].astype(float)
        joined["market_prob_away"] = merged["prob_away"].astype(float)
    else:
        joined["market_home_team_name"] = merged["away_team_name"].astype(str)
        joined["market_away_team_name"] = merged["home_team_name"].astype(str)
        joined["market_prob_home"] = merged["prob_away"].astype(float)
        joined["market_prob_draw"] = merged["prob_draw"].astype(float)
        joined["market_prob_away"] = merged["prob_home"].astype(float)
    return joined


def align_matches_with_market(
    matches: pd.DataFrame, market_odds: pd.DataFrame
) -> tuple[pd.DataFrame, AlignmentSummary]:
    """Return result rows aligned to Football-Data odds in result orientation."""

    results = _normalize_dates(matches)
    odds = _normalize_dates(market_odds)
    odds = odds.reset_index(drop=True).copy()
    odds["market_row_id"] = odds.index

    result_mask = (
        _has_value(results["home_team_id"])
        & _has_value(results["away_team_id"])
        & results["home_score"].notna()
        & results["away_score"].notna()
    )
    odds_mask = _has_value(odds["home_team_id"]) & _has_value(odds["away_team_id"])
    results = results.loc[result_mask].copy()
    odds_with_ids = odds.loc[odds_mask].copy()

    exact = results.merge(
        odds_with_ids,
        on=["date", "home_team_id", "away_team_id"],
        how="inner",
        suffixes=("", "_market"),
    )
    reversed_odds = odds_with_ids.rename(
        columns={"home_team_id": "away_team_id", "away_team_id": "home_team_id"}
    )
    reversed_join = results.merge(
        reversed_odds,
        on=["date", "home_team_id", "away_team_id"],
        how="inner",
        suffixes=("", "_market"),
    )

    aligned = pd.concat(
        [
            _finish_join(exact, orientation="as_listed"),
            _finish_join(reversed_join, orientation="reversed"),
        ],
        ignore_index=True,
    )
    if not aligned.empty:
        aligned = (
            aligned.sort_values(
                ["date", "match_id", "market_row_id", "market_orientation"],
                kind="mergesort",
            )
            .drop_duplicates(["match_id", "market_row_id"], keep="first")
            .reset_index(drop=True)
        )

    summary = AlignmentSummary(
        total_odds_rows=int(len(odds)),
        odds_rows_with_both_team_ids=int(len(odds_with_ids)),
        usable_joined_rows=int(len(aligned)),
        exact_joined_rows=int(len(exact)),
        reversed_joined_rows=int(len(reversed_join)),
        top_unmatched_footballdata_names=_top_unmatched_names(odds),
    )
    return aligned, summary


def add_elo_predictions(
    aligned: pd.DataFrame,
    matches: pd.DataFrame,
    *,
    model_factory: Callable[[], EloModel] = EloModel,
) -> pd.DataFrame:
    """Add leak-free Elo probabilities using only matches before each match date."""

    evaluation = _normalize_dates(aligned)
    train_matches = _normalize_dates(matches)
    train_matches = train_matches[
        _has_value(train_matches["home_team_id"])
        & _has_value(train_matches["away_team_id"])
        & train_matches["home_score"].notna()
        & train_matches["away_score"].notna()
    ].copy()
    sort_columns = ["date"]
    if "occurrence_index" in train_matches.columns:
        sort_columns.append("occurrence_index")
    if "match_id" in train_matches.columns:
        sort_columns.append("match_id")
    train_matches = train_matches.sort_values(sort_columns, kind="mergesort").reset_index(
        drop=True
    )
    evaluation = evaluation.sort_values(
        ["date", "match_id", "market_row_id"], kind="mergesort"
    ).reset_index(drop=True)

    model = model_factory()
    train_index = 0
    predictions: list[dict[str, float]] = []
    for match_date, date_matches in evaluation.groupby("date", sort=True):
        while (
            train_index < len(train_matches)
            and train_matches.iloc[train_index]["date"] < match_date
        ):
            # Same update path as EloModel.fit, but grouped by date so no result
            # from the prediction date can leak into any same-day prediction.
            model._update_from_match(train_matches.iloc[train_index])
            train_index += 1

        for _, row in date_matches.iterrows():
            prediction = model.predict_match(row)
            predictions.append(
                {
                    "elo_prob_home": prediction.prob_home,
                    "elo_prob_draw": prediction.prob_draw,
                    "elo_prob_away": prediction.prob_away,
                    "elo_home_rating": prediction.pre_match_home_rating,
                    "elo_away_rating": prediction.pre_match_away_rating,
                    "elo_home_advantage": prediction.home_advantage_elo,
                }
            )

    return pd.concat([evaluation, pd.DataFrame(predictions)], axis=1)


def _actual_outcome(row: pd.Series) -> str:
    if int(row["home_score"]) > int(row["away_score"]):
        return "home"
    if int(row["home_score"]) == int(row["away_score"]):
        return "draw"
    return "away"


def _probs(row: pd.Series, prefix: str) -> list[float]:
    return [
        float(row[f"{prefix}_prob_home"]),
        float(row[f"{prefix}_prob_draw"]),
        float(row[f"{prefix}_prob_away"]),
    ]


def score_predictions(evaluation: pd.DataFrame) -> pd.DataFrame:
    scored = evaluation.copy()
    outcomes: list[str] = []
    market_log_loss: list[float] = []
    market_brier: list[float] = []
    market_rps: list[float] = []
    elo_log_loss: list[float] = []
    elo_brier: list[float] = []
    elo_rps: list[float] = []

    for _, row in scored.iterrows():
        outcome = _actual_outcome(row)
        outcomes.append(outcome)
        market_probs = _probs(row, "market")
        elo_probs = _probs(row, "elo")
        market_log_loss.append(home_draw_away_log_loss(market_probs, outcome))
        market_brier.append(brier_score(market_probs, outcome))
        market_rps.append(ranked_probability_score(market_probs, outcome))
        elo_log_loss.append(home_draw_away_log_loss(elo_probs, outcome))
        elo_brier.append(brier_score(elo_probs, outcome))
        elo_rps.append(ranked_probability_score(elo_probs, outcome))

    scored["actual_outcome"] = outcomes
    scored["market_log_loss"] = market_log_loss
    scored["market_brier"] = market_brier
    scored["market_rps"] = market_rps
    scored["elo_log_loss"] = elo_log_loss
    scored["elo_brier"] = elo_brier
    scored["elo_rps"] = elo_rps
    scored["diff_log_loss_market_minus_elo"] = (
        scored["market_log_loss"] - scored["elo_log_loss"]
    )
    scored["diff_brier_market_minus_elo"] = scored["market_brier"] - scored["elo_brier"]
    scored["diff_rps_market_minus_elo"] = scored["market_rps"] - scored["elo_rps"]
    return scored


def _ci(values: pd.Series | list[float], *, n_boot: int, seed: int) -> MetricInterval:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return MetricInterval(point=math.nan, low=math.nan, high=math.nan, n=0)
    point, low, high, n = bootstrap_ci(
        finite,
        n_boot=n_boot,
        alpha=0.05,
        seed=seed,
    )
    return MetricInterval(point=point, low=low, high=high, n=n)


def summarize_scores(
    scored: pd.DataFrame,
    *,
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, dict[str, MetricInterval]]:
    return {
        "market": {
            "rps": _ci(scored["market_rps"], n_boot=n_boot, seed=seed),
            "log_loss": _ci(scored["market_log_loss"], n_boot=n_boot, seed=seed),
            "brier": _ci(scored["market_brier"], n_boot=n_boot, seed=seed),
        },
        "elo": {
            "rps": _ci(scored["elo_rps"], n_boot=n_boot, seed=seed),
            "log_loss": _ci(scored["elo_log_loss"], n_boot=n_boot, seed=seed),
            "brier": _ci(scored["elo_brier"], n_boot=n_boot, seed=seed),
        },
        "paired_diff_market_minus_elo": {
            "rps": _ci(
                scored["diff_rps_market_minus_elo"], n_boot=n_boot, seed=seed
            ),
            "log_loss": _ci(
                scored["diff_log_loss_market_minus_elo"], n_boot=n_boot, seed=seed
            ),
            "brier": _ci(
                scored["diff_brier_market_minus_elo"], n_boot=n_boot, seed=seed
            ),
        },
    }


def _format_ci(interval: MetricInterval) -> str:
    if interval.n == 0:
        return "n/a"
    return f"{interval.point:.4f} [{interval.low:.4f}, {interval.high:.4f}]"


def _format_diff(interval: MetricInterval) -> str:
    if interval.n == 0:
        return "n/a"
    return f"{interval.point:+.5f} [{interval.low:+.5f}, {interval.high:+.5f}]"


def verdict_from_metrics(metrics: dict[str, dict[str, MetricInterval]]) -> str:
    rps_diff = metrics["paired_diff_market_minus_elo"]["rps"]
    if rps_diff.n == 0:
        return "No verdict: no finite paired RPS values."
    if rps_diff.high < 0.0:
        return (
            "Elo trails the Football-Data market on RPS: the paired CI is below 0, "
            "so market probabilities scored lower on the same matches."
        )
    if rps_diff.low > 0.0:
        return (
            "Elo beats the Football-Data market on RPS: the paired CI is above 0, "
            "so Elo scored lower on the same matches."
        )
    if rps_diff.point < 0.0:
        return (
            "Elo roughly matches the Football-Data market, with the market slightly "
            "ahead on point estimate but the paired RPS CI spans 0."
        )
    if rps_diff.point > 0.0:
        return (
            "Elo roughly matches the Football-Data market, with Elo slightly ahead "
            "on point estimate but the paired RPS CI spans 0."
        )
    return "Elo matches the Football-Data market on paired RPS within bootstrap noise."


def format_report(
    *,
    result: EloVsMarketResult | None = None,
    alignment: AlignmentSummary | None = None,
    scored: pd.DataFrame | None = None,
    metrics: dict[str, dict[str, MetricInterval]] | None = None,
    verdict: str | None = None,
) -> str:
    if result is not None:
        alignment = result.alignment
        scored = result.scored
        metrics = result.metrics
        verdict = result.verdict
    if alignment is None or scored is None or metrics is None or verdict is None:
        raise ValueError("format_report requires a result or all report components")

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if scored.empty:
        date_range = "n/a"
    else:
        date_min = pd.to_datetime(scored["date"]).min().strftime("%Y-%m-%d")
        date_max = pd.to_datetime(scored["date"]).max().strftime("%Y-%m-%d")
        date_range = f"{date_min} to {date_max}"

    unmatched = alignment.top_unmatched_footballdata_names
    unmatched_lines = (
        [f"- {name}: {count}" for name, count in unmatched]
        if unmatched
        else ["- None among Football-Data odds rows."]
    )

    lines = [
        "# Historical Elo vs Football-Data market backtest",
        "",
        f"Generated: `{generated}`",
        "",
        "Lower is better for all metrics. The paired difference is `market - Elo`, so",
        "negative means the market scored better and positive means Elo scored better.",
        "",
        "## Evaluation set",
        "",
        f"- Total Football-Data odds rows: {alignment.total_odds_rows:,}",
        f"- Odds rows with both canonical team ids: {alignment.odds_rows_with_both_team_ids:,}",
        f"- Usable joined result/market rows: {alignment.usable_joined_rows:,}",
        f"- Date range: {date_range}",
        f"- As-listed joins: {alignment.exact_joined_rows:,}",
        f"- Reversed-orientation joins: {alignment.reversed_joined_rows:,}",
        "",
        "Top unmatched Football-Data names from null canonical ids:",
        "",
        *unmatched_lines,
        "",
        "## Metrics",
        "",
        f"Bootstrap 95% CIs use {BOOTSTRAP_N:,} resamples with seed {BOOTSTRAP_SEED}.",
        "Non-finite log-loss rows are excluded from log-loss CIs only.",
        "",
        "| Model | n | RPS [95% CI] | H/D/A log loss [95% CI] | Brier [95% CI] |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for model_name in ("market", "elo"):
        model_label = "Football-Data market" if model_name == "market" else "Elo"
        model_metrics = metrics[model_name]
        lines.append(
            f"| {model_label} | {model_metrics['rps'].n:,} | "
            f"{_format_ci(model_metrics['rps'])} | "
            f"{_format_ci(model_metrics['log_loss'])} | "
            f"{_format_ci(model_metrics['brier'])} |"
        )

    diffs = metrics["paired_diff_market_minus_elo"]
    lines.extend(
        [
            "",
            "## Paired differences: market minus Elo",
            "",
            "| Metric | mean diff [95% CI] | Interpretation |",
            "| --- | --- | --- |",
            f"| RPS | {_format_diff(diffs['rps'])} | negative = market better; positive = Elo better |",
            f"| H/D/A log loss | {_format_diff(diffs['log_loss'])} | negative = market better; positive = Elo better |",
            f"| Brier | {_format_diff(diffs['brier'])} | negative = market better; positive = Elo better |",
            "",
            "## Verdict",
            "",
            verdict,
            "",
            "## Honesty caveats",
            "",
            "- The market benchmark only covers Football-Data rows that resolve to canonical teams and join to martj42 results.",
            "- Football-Data odds include information Elo does not use, including injuries, lineups, venue context, and broad market wisdom.",
            "- The Elo predictions are point-in-time by match date, not kickoff timestamp; all same-date results are withheld to avoid leakage.",
            "- Alias gaps in qualifier teams can change the sample if Claude extends the alias table.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    *,
    matches_path: str | Path = settings.SILVER_DIR / MATCHES_FILE,
    market_odds_path: str | Path = settings.SILVER_DIR / MARKET_ODDS_FILE,
    report_path: str | Path = settings.REPORTS_DIR / "backtests" / "elo_vs_market.md",
) -> EloVsMarketResult:
    matches = _read_parquet(matches_path)
    market_odds = _read_parquet(market_odds_path)

    aligned, alignment = align_matches_with_market(matches, market_odds)
    if alignment.usable_joined_rows < MIN_USABLE_SAMPLE:
        raise RuntimeError(
            "usable joined sample is too small for a Q2 verdict: "
            f"{alignment.usable_joined_rows} < {MIN_USABLE_SAMPLE}"
        )

    evaluation = add_elo_predictions(aligned, matches)
    scored = score_predictions(evaluation)
    metrics = summarize_scores(scored)
    verdict = verdict_from_metrics(metrics)
    result = EloVsMarketResult(
        alignment=alignment,
        scored=scored,
        metrics=metrics,
        verdict=verdict,
        report_path=Path(report_path),
    )
    report = format_report(result=result)
    result.report_path.parent.mkdir(parents=True, exist_ok=True)
    result.report_path.write_text(report, encoding="utf-8")
    return result


def main() -> None:
    result = run()
    market = result.metrics["market"]
    elo = result.metrics["elo"]
    diff = result.metrics["paired_diff_market_minus_elo"]
    date_min = pd.to_datetime(result.scored["date"]).min().strftime("%Y-%m-%d")
    date_max = pd.to_datetime(result.scored["date"]).max().strftime("%Y-%m-%d")
    print(
        "[elo_vs_market] "
        f"usable_n={result.alignment.usable_joined_rows} "
        f"date_range={date_min}..{date_max} "
        f"market_rps={market['rps'].point:.4f} "
        f"elo_rps={elo['rps'].point:.4f} "
        f"diff_market_minus_elo={diff['rps'].point:+.5f} "
        f"report={result.report_path}",
        flush=True,
    )
    print(f"[elo_vs_market] verdict: {result.verdict}", flush=True)


if __name__ == "__main__":
    main()
