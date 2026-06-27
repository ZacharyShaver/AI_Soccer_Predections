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
from typing import Any

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.forecast_live import (
    AS_OF,
    ForecastRow,
    load_silver_data,
    run_live_forecast,
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
    reports_dir: str | Path,
) -> OverlayResult:
    import tempfile

    from wc_predictor.data.ingest_polymarket import parse_world_cup_match_events

    matches, fixtures, teams = load_silver_data()
    # The overlay only consumes Elo forecast rows; it must not write the immutable
    # production prediction ledger. Route run_live_forecast's ledger writes to a
    # throwaway directory so this stays a read-only consumer of the Elo forecast.
    scratch_runs = tempfile.mkdtemp(prefix="overlay_elo_")
    # Also route the Elo report to scratch: the overlay must not overwrite the
    # committed live_forecast report; it writes its own overlay report below.
    live = run_live_forecast(
        matches_df=matches,
        fixtures_df=fixtures,
        teams_df=teams,
        as_of=as_of,
        runs_dir=scratch_runs,
        reports_dir=scratch_runs,
    )
    market_rows, _ = parse_world_cup_match_events(events)
    rows, summary = overlay_forecasts(live.forecast_rows, market_rows)
    report_path = write_overlay_report(
        as_of=as_of, rows=rows, summary=summary, reports_dir=reports_dir
    )
    return OverlayResult(
        as_of=as_of,
        rows=rows,
        forecast_count=summary["forecast_count"],
        market_covered_count=summary["market_covered_count"],
        elo_fallback_count=summary["elo_fallback_count"],
        report_path=report_path,
    )


def run_from_raw(
    raw_path: str | Path,
    *,
    as_of: str = AS_OF,
    reports_dir: str | Path = settings.REPORTS_DIR,
) -> OverlayResult:
    """Produce the overlay from a saved Gamma snapshot (no network)."""

    return _build(
        events=events_from_raw_snapshot(raw_path), as_of=as_of, reports_dir=reports_dir
    )


def run(
    *,
    as_of: str = AS_OF,
    reports_dir: str | Path = settings.REPORTS_DIR,
) -> OverlayResult:
    """Fetch live Polymarket markets and produce the overlay forecast."""

    from wc_predictor.data.ingest_polymarket import fetch_world_cup_markets

    _, events = fetch_world_cup_markets()
    return _build(events=events, as_of=as_of, reports_dir=reports_dir)


def main() -> None:
    result = run()
    print(
        "[forecast_overlay] "
        f"as_of={result.as_of} fixtures={result.forecast_count} "
        f"market={result.market_covered_count} elo={result.elo_fallback_count} "
        f"report={result.report_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
