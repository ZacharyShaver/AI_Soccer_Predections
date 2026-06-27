"""Live forecast overlay: market-where-available, Elo-everywhere-else.

The market-blend and distillation backtests settled the architecture: the
de-vigged market significantly beats Elo on matches that have tradeable odds,
but you cannot distill that edge into Elo's parameters, and a linear blend just
picks the market (lambda=1). So the right live predictor is an OVERLAY -- take
the Elo forecast for every remaining fixture (Elo is the only thing that covers
every matchup) and, wherever a de-vigged Polymarket match-result market exists
for that fixture, replace the Elo probabilities with the market's.

This module is deliberately model-agnostic: ``overlay_forecasts`` is a pure
function of Elo ``ForecastRow``s and a de-vigged market table, so it is fully
unit-testable offline. ``run`` wires it to the live pipeline (Elo via
``run_live_forecast``, market via the Polymarket Gamma parser), and
``run_from_raw`` replays a saved Gamma snapshot so the overlay can be produced
without network access.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.forecast_live import (
    AS_OF,
    GENERATED_AT_UTC,
    TRAINING_CUTOFF,
    ForecastRow,
    load_silver_data,
    run_live_forecast,
)
from wc_predictor.models.elo import elo_model

OVERLAY_MODEL_ID = "elo_market_overlay_v1"
OVERLAY_MODEL_VERSION = "overlay_v1"
# Dedicated ledger subtree so the overlay scorecard never mixes with the Elo ledger.
OVERLAY_RUNS_DIR = settings.RUNS_DIR / "overlay"

# Recalibrated Elo (the elo_recalibrated variant) is the fallback for fixtures
# without a market: faster K, recalibrated draw mass, flat tournament weights.
_FLAT_TOURNAMENT_WEIGHTS = {
    "Friendly": 1.0,
    "FIFA World Cup": 1.0,
    "FIFA World Cup qualification": 1.0,
    "UEFA Euro": 1.0,
    "Copa America": 1.0,
    "CONCACAF Championship": 1.0,
    "CONCACAF Nations League": 1.0,
    "UEFA Nations League": 1.0,
    "African Cup of Nations": 1.0,
    "AFC Asian Cup": 1.0,
}


def recalibrated_elo_model_factory(*, generated_at_utc: str, host_advantage_fn):
    """Build the tuned `elo_recalibrated` model used as the overlay's fallback."""

    return elo_model(
        generated_at_utc=generated_at_utc,
        host_advantage_fn=host_advantage_fn,
        k_factor=30.0,
        home_advantage=75.0,
        draw_base_probability=0.33,
        draw_rating_scale=600.0,
        tournament_weights=_FLAT_TOURNAMENT_WEIGHTS,
        default_tournament_weight=1.0,
    )


@dataclass(frozen=True)
class OverlayRow:
    fixture_id: str
    group: str
    match_date: str
    venue: str
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    # Final overlaid probabilities (market where available, else Elo).
    prob_home: float
    prob_draw: float
    prob_away: float
    source: str  # "market" or "elo"
    # Kept for transparency / scoring provenance.
    elo_prob_home: float
    elo_prob_draw: float
    elo_prob_away: float
    market_prob_home: float | None
    market_prob_draw: float | None
    market_prob_away: float | None
    market_event_title: str | None


@dataclass(frozen=True)
class OverlayResult:
    as_of: str
    rows: list[OverlayRow]
    forecast_count: int
    market_covered_count: int
    elo_fallback_count: int
    report_path: Path
    ledger_path: Path | None = None


def _resolved_market_index(
    market_rows: pd.DataFrame,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Index resolved market rows by (home_team_id, away_team_id)."""

    index: dict[tuple[str, str], dict[str, Any]] = {}
    if market_rows is None or market_rows.empty:
        return index
    for row in market_rows.itertuples(index=False):
        home_id = getattr(row, "home_team_id", None)
        away_id = getattr(row, "away_team_id", None)
        if home_id is None or away_id is None:
            continue
        if pd.isna(home_id) or pd.isna(away_id):
            continue
        key = (str(home_id), str(away_id))
        # First write wins (market_rows is pre-sorted deterministically upstream).
        index.setdefault(
            key,
            {
                "prob_home": float(row.prob_home),
                "prob_draw": float(row.prob_draw),
                "prob_away": float(row.prob_away),
                "event_title": str(getattr(row, "event_title", "") or ""),
            },
        )
    return index


def _lookup_market(
    index: dict[tuple[str, str], dict[str, Any]],
    home_id: str,
    away_id: str,
) -> tuple[dict[str, Any], bool] | None:
    """Return (market, reversed) for a fixture, handling swapped orientation."""

    direct = index.get((home_id, away_id))
    if direct is not None:
        return direct, False
    flipped = index.get((away_id, home_id))
    if flipped is not None:
        return flipped, True
    return None


def overlay_forecasts(
    forecast_rows: list[ForecastRow],
    market_rows: pd.DataFrame,
) -> tuple[list[OverlayRow], dict[str, int]]:
    """Overlay de-vigged market probabilities onto Elo forecasts.

    For each Elo fixture, if a resolved three-way market exists for that team
    pair (in either orientation) its de-vigged probabilities replace Elo's;
    otherwise the Elo probabilities are kept. Pure and offline-testable.
    """

    index = _resolved_market_index(market_rows)
    overlay_rows: list[OverlayRow] = []
    market_covered = 0
    for row in forecast_rows:
        home_id = str(row.home_team_id)
        away_id = str(row.away_team_id)
        match = _lookup_market(index, home_id, away_id)
        if match is None:
            overlay_rows.append(
                OverlayRow(
                    fixture_id=row.fixture_id,
                    group=row.group,
                    match_date=row.match_date,
                    venue=row.venue,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    home_team_name=row.home_team_name,
                    away_team_name=row.away_team_name,
                    prob_home=row.prob_home,
                    prob_draw=row.prob_draw,
                    prob_away=row.prob_away,
                    source="elo",
                    elo_prob_home=row.prob_home,
                    elo_prob_draw=row.prob_draw,
                    elo_prob_away=row.prob_away,
                    market_prob_home=None,
                    market_prob_draw=None,
                    market_prob_away=None,
                    market_event_title=None,
                )
            )
            continue

        market, is_reversed = match
        if is_reversed:
            m_home, m_draw, m_away = (
                market["prob_away"],
                market["prob_draw"],
                market["prob_home"],
            )
        else:
            m_home, m_draw, m_away = (
                market["prob_home"],
                market["prob_draw"],
                market["prob_away"],
            )
        market_covered += 1
        overlay_rows.append(
            OverlayRow(
                fixture_id=row.fixture_id,
                group=row.group,
                match_date=row.match_date,
                venue=row.venue,
                home_team_id=home_id,
                away_team_id=away_id,
                home_team_name=row.home_team_name,
                away_team_name=row.away_team_name,
                prob_home=m_home,
                prob_draw=m_draw,
                prob_away=m_away,
                source="market",
                elo_prob_home=row.prob_home,
                elo_prob_draw=row.prob_draw,
                elo_prob_away=row.prob_away,
                market_prob_home=m_home,
                market_prob_draw=m_draw,
                market_prob_away=m_away,
                market_event_title=market["event_title"],
            )
        )

    summary = {
        "forecast_count": len(forecast_rows),
        "market_covered_count": market_covered,
        "elo_fallback_count": len(forecast_rows) - market_covered,
    }
    return overlay_rows, summary


def _pct(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def write_overlay_report(
    *,
    as_of: str,
    rows: list[OverlayRow],
    summary: dict[str, int],
    reports_dir: str | Path = settings.REPORTS_DIR,
) -> Path:
    report_path = (
        Path(reports_dir) / "backtests" / f"live_forecast_overlay_{as_of}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Live World Cup forecast (market overlay) as of {as_of}",
        "",
        "Market-where-available, Elo-everywhere-else. For each remaining fixture the",
        "probabilities are the de-vigged Polymarket match-result market when one exists",
        "for that team pair, otherwise the `elo_poisson_v1` forecast. Backtests show the",
        "de-vigged market significantly beats Elo where odds exist (paired RPS CI excludes",
        "0); Elo remains the always-available backbone for fixtures without a market.",
        "",
        "## Counts",
        "",
        f"- Forecast fixtures: {summary['forecast_count']}",
        f"- Using market probabilities: {summary['market_covered_count']}",
        f"- Using Elo fallback: {summary['elo_fallback_count']}",
        "",
    ]

    for group in sorted({row.group for row in rows}):
        group_rows = [row for row in rows if row.group == group]
        lines.extend([f"## Group {group}", ""])
        lines.extend(
            [
                "| Date | Match | Source | Home | Draw | Away | Elo H/D/A |",
                "| --- | --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for row in group_rows:
            elo_cell = (
                f"{_pct(row.elo_prob_home)} / {_pct(row.elo_prob_draw)} / "
                f"{_pct(row.elo_prob_away)}"
            )
            lines.append(
                "| "
                f"{row.match_date} | {row.home_team_name} vs {row.away_team_name} | "
                f"{row.source} | {_pct(row.prob_home)} | {_pct(row.prob_draw)} | "
                f"{_pct(row.prob_away)} | {elo_cell} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Caveats",
            "",
            "- Market prices are a live snapshot and move with news, lineups, and liquidity.",
            "- Only three-way match-result markets are used; props/spreads/totals/group/outright are excluded.",
            "- A fixture only takes the market when its team pair resolves to canonical ids in the alias table; otherwise it keeps the Elo forecast.",
            "- Knockout fixtures with unresolved brackets are not forecast here (null team ids upstream).",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def overlay_prediction_payloads(
    rows: list[OverlayRow],
    *,
    as_of: str,
    training_cutoff: str,
    generated_at_utc: str,
) -> list[dict[str, Any]]:
    """Immutable ledger rows for the overlaid forecasts.

    Stored as plain dicts (not MatchPrediction) so each row can carry the
    canonical team ids and date the scorer needs to join to results -- live
    fixture ids do not match martj42 result match_ids, but the team ids do.
    """

    payloads: list[dict[str, Any]] = []
    for row in rows:
        probs = [row.prob_home, row.prob_draw, row.prob_away]
        total = sum(probs) or 1.0
        prob_home, prob_draw, prob_away = (value / total for value in probs)
        payloads.append(
            {
                "prediction_id": f"{OVERLAY_MODEL_ID}:{row.fixture_id}:as_of={as_of}",
                "match_id": row.fixture_id,
                "model_id": OVERLAY_MODEL_ID,
                "model_version": OVERLAY_MODEL_VERSION,
                "generated_at_utc": generated_at_utc,
                "training_cutoff": training_cutoff,
                "as_of": as_of,
                "prob_home": float(prob_home),
                "prob_draw": float(prob_draw),
                "prob_away": float(prob_away),
                "source": row.source,
                "match_date": row.match_date,
                "home_team_id": row.home_team_id,
                "away_team_id": row.away_team_id,
                "home_team_name": row.home_team_name,
                "away_team_name": row.away_team_name,
            }
        )
    return payloads


def write_overlay_predictions(
    rows: list[OverlayRow],
    *,
    as_of: str,
    training_cutoff: str,
    generated_at_utc: str,
    runs_dir: str | Path = OVERLAY_RUNS_DIR,
) -> Path | None:
    """Append overlaid forecasts to the immutable overlay ledger (idempotent)."""

    from wc_predictor.evaluation.ledger import write_prediction

    ledger_path: Path | None = None
    for payload in overlay_prediction_payloads(
        rows,
        as_of=as_of,
        training_cutoff=training_cutoff,
        generated_at_utc=generated_at_utc,
    ):
        ledger_path = write_prediction(payload, runs_dir=runs_dir)
    return ledger_path


def _outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if home_score < away_score:
        return "away"
    return "draw"


def score_overlay(
    predictions: list[Mapping[str, Any]] | str | Path,
    results_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Score overlay predictions against results, joining on (date, team ids).

    Live fixture ids do not match result match_ids, so we join each prediction
    to a completed result with the same calendar date and the same team pair in
    either orientation (flipping the actual outcome when the result lists the
    teams reversed). Returns the per-match evaluation and an aggregate that also
    splits RPS by source (market vs Elo) -- the live test of whether the market
    overlay actually beats Elo on resolved fixtures.
    """

    from wc_predictor.evaluation.score_ledger import _load_predictions
    from wc_predictor.evaluation.metrics import (
        brier_score,
        home_draw_away_log_loss,
        ranked_probability_score,
    )

    rows = _load_predictions(predictions)
    results = results_df.copy()
    date_col = "match_date" if "match_date" in results.columns else "date"
    results[date_col] = pd.to_datetime(results[date_col], errors="coerce")
    completed = results.dropna(subset=[date_col, "home_score", "away_score"])
    # Index results by (date, frozenset of team ids).
    result_index: dict[tuple[str, frozenset[str]], dict[str, Any]] = {}
    for r in completed.itertuples(index=False):
        rd = r._asdict()
        key = (
            pd.Timestamp(rd[date_col]).strftime("%Y-%m-%d"),
            frozenset({str(rd["home_team_id"]), str(rd["away_team_id"])}),
        )
        result_index.setdefault(
            key,
            {
                "home_team_id": str(rd["home_team_id"]),
                "home_score": int(rd["home_score"]),
                "away_score": int(rd["away_score"]),
            },
        )

    eval_rows: list[dict[str, Any]] = []
    for row in rows:
        home_id, away_id = str(row["home_team_id"]), str(row["away_team_id"])
        key = (str(row["match_date"])[:10], frozenset({home_id, away_id}))
        result = result_index.get(key)
        if result is None or home_id == away_id:
            continue
        if result["home_team_id"] == home_id:
            actual = _outcome(result["home_score"], result["away_score"])
        else:  # result lists the pair reversed -> flip to the prediction orientation
            actual = _outcome(result["away_score"], result["home_score"])
        probs = [float(row["prob_home"]), float(row["prob_draw"]), float(row["prob_away"])]
        tot = sum(probs) or 1.0
        probs = [p / tot for p in probs]
        eval_rows.append(
            {
                "home_team_id": home_id,
                "away_team_id": away_id,
                "source": row.get("source", "unknown"),
                "actual_outcome": actual,
                "rps": ranked_probability_score(probs, actual),
                "log_loss": home_draw_away_log_loss(probs, actual),
                "brier": brier_score(probs, actual),
                "called_it": ["home", "draw", "away"][probs.index(max(probs))] == actual,
            }
        )

    evaluation = pd.DataFrame(eval_rows)
    n = len(evaluation)

    def _mean(col: str, frame: pd.DataFrame) -> float | None:
        vals = [v for v in frame[col] if pd.notna(v) and v != float("inf")]
        return sum(vals) / len(vals) if vals else None

    by_source: dict[str, dict[str, Any]] = {}
    if n:
        for src, grp in evaluation.groupby("source"):
            by_source[str(src)] = {
                "n": int(len(grp)),
                "mean_rps": _mean("rps", grp),
                "accuracy": float(grp["called_it"].mean()),
            }
    aggregate = {
        "n_total": len(rows),
        "n_scored": n,
        "mean_rps": _mean("rps", evaluation) if n else None,
        "mean_log_loss": _mean("log_loss", evaluation) if n else None,
        "mean_brier": _mean("brier", evaluation) if n else None,
        "accuracy": float(evaluation["called_it"].mean()) if n else None,
        "by_source": by_source,
    }
    return evaluation, aggregate


def write_overlay_scorecard_report(
    aggregate: dict[str, Any],
    *,
    as_of: str,
    reports_dir: str | Path = settings.REPORTS_DIR,
) -> Path:
    report_path = Path(reports_dir) / "backtests" / "overlay_scorecard.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def _fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.4f}"

    lines = [
        "# Overlay scorecard (market-where-available vs results)",
        "",
        f"As of: {as_of}. Overlay predictions are scored against completed results by",
        "joining on match date and canonical team pair (live fixture ids do not match",
        "result ids, but team ids do). Lower RPS/log loss/Brier is better.",
        "",
        "## Aggregate",
        "",
        f"- Ledger predictions: {aggregate['n_total']}",
        f"- Scored (resolved): {aggregate['n_scored']}",
        f"- Mean RPS: {_fmt(aggregate['mean_rps'])}",
        f"- Mean log loss: {_fmt(aggregate['mean_log_loss'])}",
        f"- Mean Brier: {_fmt(aggregate['mean_brier'])}",
        f"- Accuracy: {_fmt(aggregate['accuracy'])}",
        "",
        "## By source",
        "",
        "| Source | n | Mean RPS | Accuracy |",
        "| --- | ---: | ---: | ---: |",
    ]
    for source, stats in sorted(aggregate.get("by_source", {}).items()):
        lines.append(
            f"| {source} | {stats['n']} | {_fmt(stats['mean_rps'])} | {_fmt(stats['accuracy'])} |"
        )
    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- Small samples early in the tournament; treat single-digit n as indicative only.",
            "- `market` rows used the de-vigged Polymarket price at snapshot time; `elo` rows used the recalibrated Elo fallback.",
            "- Predictions are immutable ledger labels; scoring never mutates them.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def events_from_raw_snapshot(path: str | Path) -> list[dict[str, Any]]:
    """Load the ``events`` list from a saved Gamma raw snapshot JSON."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(events, list):
        raise ValueError(f"{path}: no events list in snapshot payload")
    return events


def _build(
    *,
    events: list[dict[str, Any]],
    as_of: str,
    training_cutoff: str,
    generated_at_utc: str,
    reports_dir: str | Path,
    write_ledger: bool,
    overlay_runs_dir: str | Path,
) -> OverlayResult:
    import tempfile

    from wc_predictor.data.ingest_polymarket import parse_world_cup_match_events

    matches, fixtures, teams = load_silver_data()
    # The overlay only consumes Elo forecast rows; it must not write the immutable
    # production prediction ledger or overwrite the committed live_forecast report.
    # Route run_live_forecast's ledger+report writes to a throwaway directory, and
    # use the recalibrated Elo as the fallback for fixtures without a market.
    scratch_runs = tempfile.mkdtemp(prefix="overlay_elo_")
    live = run_live_forecast(
        matches_df=matches,
        fixtures_df=fixtures,
        teams_df=teams,
        as_of=as_of,
        training_cutoff=training_cutoff,
        generated_at_utc=generated_at_utc,
        runs_dir=scratch_runs,
        reports_dir=scratch_runs,
        model_factory=recalibrated_elo_model_factory,
    )
    market_rows, _ = parse_world_cup_match_events(events)
    rows, summary = overlay_forecasts(live.forecast_rows, market_rows)
    report_path = write_overlay_report(
        as_of=as_of, rows=rows, summary=summary, reports_dir=reports_dir
    )
    ledger_path: Path | None = None
    if write_ledger:
        ledger_path = write_overlay_predictions(
            rows,
            as_of=as_of,
            training_cutoff=training_cutoff,
            generated_at_utc=generated_at_utc,
            runs_dir=overlay_runs_dir,
        )
    return OverlayResult(
        as_of=as_of,
        rows=rows,
        forecast_count=summary["forecast_count"],
        market_covered_count=summary["market_covered_count"],
        elo_fallback_count=summary["elo_fallback_count"],
        report_path=report_path,
        ledger_path=ledger_path,
    )


def run_from_raw(
    raw_path: str | Path,
    *,
    as_of: str = AS_OF,
    training_cutoff: str = TRAINING_CUTOFF,
    generated_at_utc: str = GENERATED_AT_UTC,
    reports_dir: str | Path = settings.REPORTS_DIR,
    write_ledger: bool = True,
    overlay_runs_dir: str | Path = OVERLAY_RUNS_DIR,
) -> OverlayResult:
    """Produce the overlay from a saved Gamma snapshot (no network)."""

    return _build(
        events=events_from_raw_snapshot(raw_path),
        as_of=as_of,
        training_cutoff=training_cutoff,
        generated_at_utc=generated_at_utc,
        reports_dir=reports_dir,
        write_ledger=write_ledger,
        overlay_runs_dir=overlay_runs_dir,
    )


def run(
    *,
    as_of: str = AS_OF,
    training_cutoff: str = TRAINING_CUTOFF,
    generated_at_utc: str = GENERATED_AT_UTC,
    reports_dir: str | Path = settings.REPORTS_DIR,
    write_ledger: bool = True,
    overlay_runs_dir: str | Path = OVERLAY_RUNS_DIR,
) -> OverlayResult:
    """Fetch live Polymarket markets and produce the overlay forecast."""

    from wc_predictor.data.ingest_polymarket import fetch_world_cup_markets

    _, events = fetch_world_cup_markets()
    return _build(
        events=events,
        as_of=as_of,
        training_cutoff=training_cutoff,
        generated_at_utc=generated_at_utc,
        reports_dir=reports_dir,
        write_ledger=write_ledger,
        overlay_runs_dir=overlay_runs_dir,
    )


def score(
    *,
    as_of: str = AS_OF,
    overlay_runs_dir: str | Path = OVERLAY_RUNS_DIR,
    reports_dir: str | Path = settings.REPORTS_DIR,
) -> dict[str, Any]:
    """Score the accumulated overlay ledger against current results."""

    from wc_predictor.evaluation.scorecard import _read_parquet

    predictions_dir = Path(overlay_runs_dir) / "predictions"
    matches_path = settings.SILVER_DIR / "martj42_matches.parquet"
    results = (
        _read_parquet(matches_path)
        if Path(matches_path).exists()
        else pd.DataFrame(columns=["date", "home_team_id", "away_team_id", "home_score", "away_score"])
    )
    if not predictions_dir.exists() or not any(predictions_dir.rglob("*.jsonl")):
        _, aggregate = score_overlay([], results)
    else:
        _, aggregate = score_overlay(predictions_dir, results)
    write_overlay_scorecard_report(aggregate, as_of=as_of, reports_dir=reports_dir)
    return aggregate


def main() -> None:
    result = run()
    aggregate = score(as_of=result.as_of)
    print(
        "[forecast_overlay] "
        f"as_of={result.as_of} fixtures={result.forecast_count} "
        f"market={result.market_covered_count} elo={result.elo_fallback_count} "
        f"scored={aggregate['n_scored']} mean_rps={aggregate['mean_rps']} "
        f"report={result.report_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
