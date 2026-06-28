"""Betting disagreement tool: our model vs the live Polymarket market.

Key honesty principle (earned the hard way on 2026-06-28): the de-vigged market
out-predicts our Elo on average — proven three ways. So a disagreement is NOT a
bet by default; it usually means *we're* wrong. A disagreement is only promoted
to a recommended BET when there is a validated STRUCTURAL reason to think the
market is missing something. Today that reason is altitude acclimatization (the
one unpriced edge we found). Everything else is shown as WATCH — informational,
market-probably-right.

EV uses the real *offered* price (with vig), so the numbers are honest betting
EV, not fair-odds fantasy. Stakes are fractional-Kelly and capped.

Outputs a markdown report; pure functions are unit-tested offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.lab.altitude import home_advantage_delta_elo, team_altitude_baselines

_OUTCOMES = ("home", "draw", "away")
MIN_STRUCTURAL_ELO = 20.0  # altitude delta must be at least this to back a bet
KELLY_CAP = 0.05           # never suggest staking more than 5% of bankroll


@dataclass(frozen=True)
class BetSignal:
    fixture_id: str
    match_date: str
    venue: str
    home_team_name: str
    away_team_name: str
    outcome: str            # "home" | "draw" | "away"
    selection: str          # team name or "Draw"
    our_prob: float         # the probability we're acting on (alt-adjusted if structural)
    market_prob: float      # de-vigged market (fair value)
    offered_price: float    # raw vigged implied prob; decimal odds = 1/price
    edge: float             # our_prob - market_prob (vs fair value)
    ev: float               # expected value per 1 unit staked at the offered price
    kelly_stake: float      # fractional-Kelly fraction of bankroll (capped)
    altitude_delta_elo: float
    structural: str | None  # "altitude" or None
    recommendation: str     # "BET" | "WATCH"


def kelly_fraction(prob: float, price: float, fraction: float) -> float:
    """Fractional Kelly for a binary bet at offered implied price `price`."""
    if not (0.0 < price < 1.0):
        return 0.0
    full = (prob - price) / (1.0 - price)
    return max(0.0, min(KELLY_CAP, full * fraction))


def evaluate_fixture(
    meta: dict[str, Any],
    base_probs: tuple[float, float, float],
    alt_probs: tuple[float, float, float],
    market_devig: tuple[float, float, float],
    offered_prices: tuple[float, float, float],
    altitude_delta_elo: float,
    *,
    edge_threshold: float = 0.04,
    kelly_frac: float = 0.25,
    min_structural_elo: float = MIN_STRUCTURAL_ELO,
) -> list[BetSignal]:
    """Return positive-EV disagreement signals for one fixture (pure)."""

    signals: list[BetSignal] = []
    for i, outcome in enumerate(_OUTCOMES):
        price = offered_prices[i]
        if not (0.0 < price < 1.0):
            continue
        # Altitude can only back a home or away win, and only in its direction.
        alt_supports = (
            (outcome == "home" and altitude_delta_elo >= min_structural_elo)
            or (outcome == "away" and altitude_delta_elo <= -min_structural_elo)
        )
        our_prob = alt_probs[i] if alt_supports else base_probs[i]
        edge = our_prob - market_devig[i]
        ev = our_prob / price - 1.0
        if ev <= 0.0 or edge < edge_threshold:
            continue
        selection = (
            meta["home_team_name"] if outcome == "home"
            else "Draw" if outcome == "draw"
            else meta["away_team_name"]
        )
        signals.append(
            BetSignal(
                fixture_id=meta["fixture_id"],
                match_date=meta["match_date"],
                venue=meta.get("venue", ""),
                home_team_name=meta["home_team_name"],
                away_team_name=meta["away_team_name"],
                outcome=outcome,
                selection=selection,
                our_prob=our_prob,
                market_prob=market_devig[i],
                offered_price=price,
                edge=edge,
                ev=ev,
                kelly_stake=kelly_fraction(our_prob, price, kelly_frac),
                altitude_delta_elo=altitude_delta_elo,
                structural="altitude" if alt_supports else None,
                recommendation="BET" if alt_supports else "WATCH",
            )
        )
    return signals


def rank_signals(signals: list[BetSignal]) -> list[BetSignal]:
    """BET before WATCH, then by EV descending."""
    return sorted(signals, key=lambda s: (s.recommendation != "BET", -s.ev))


# ---------------------------------------------------------------------------
# Live runner
# ---------------------------------------------------------------------------
_FLAT = {k: 1.0 for k in (
    "Friendly", "FIFA World Cup", "FIFA World Cup qualification", "UEFA Euro",
    "Copa America", "CONCACAF Championship", "CONCACAF Nations League",
    "UEFA Nations League", "AFC Asian Cup", "African Cup of Nations",
)}
RECAL = dict(k_factor=30.0, home_advantage=75.0, draw_base_probability=0.33,
             draw_rating_scale=600.0, tournament_weights=_FLAT, default_tournament_weight=1.0)


def _market_index(market_rows: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    idx: dict[tuple[str, str], dict[str, Any]] = {}
    if market_rows is None or market_rows.empty:
        return idx
    for r in market_rows.itertuples(index=False):
        h, a = getattr(r, "home_team_id", None), getattr(r, "away_team_id", None)
        if h is None or a is None or pd.isna(h) or pd.isna(a):
            continue

        def _f(v):
            return float(v) if v is not None and not pd.isna(v) else 0.0

        idx.setdefault((str(h), str(a)), {
            "devig": (_f(r.prob_home), _f(r.prob_draw), _f(r.prob_away)),
            "raw": (_f(r.raw_home_price), _f(r.raw_draw_price), _f(r.raw_away_price)),
            "title": str(getattr(r, "event_title", "") or ""),
        })
    return idx


def run_betting(
    *,
    as_of: str,
    training_cutoff: str,
    generated_at_utc: str,
    coef: float = 60.0,
    edge_threshold: float = 0.04,
    kelly_frac: float = 0.25,
    events: list[dict] | None = None,
    reports_dir: str | Path = settings.REPORTS_DIR,
    write_report: bool = True,
    record: bool = True,
) -> list[BetSignal]:
    """Fetch live Polymarket (or use `events`), compare to our model, rank signals."""

    from wc_predictor.forecast_live import (
        _fixture_match_row,
        _team_names,
        _training_matches,
        build_world_cup_host_advantage_fn,
        load_silver_data,
    )
    from wc_predictor.models.elo import EloModel

    matches, fixtures, teams = load_silver_data()
    names = _team_names(teams)
    model = EloModel(
        **RECAL, generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
    model.fit(_training_matches(matches, training_cutoff=training_cutoff))
    baselines = team_altitude_baselines(matches)

    if events is None:
        from wc_predictor.data.ingest_polymarket import fetch_world_cup_markets
        _, events = fetch_world_cup_markets()
    from wc_predictor.data.ingest_polymarket import parse_world_cup_match_events
    market_rows, _ = parse_world_cup_match_events(events)
    idx = _market_index(market_rows)

    today = pd.Timestamp(as_of)
    signals: list[BetSignal] = []
    seen: set[frozenset[str]] = set()
    for fx in fixtures.itertuples(index=False):
        h, a = str(fx.home_team_id), str(fx.away_team_id)
        if h in ("", "nan") or a in ("", "nan"):
            continue
        key = frozenset((h, a))
        if key in seen:
            continue
        try:
            if pd.notna(fx.match_date) and pd.Timestamp(fx.match_date) < today:
                continue
        except Exception:
            pass
        market = idx.get((h, a))
        reversed_ = False
        if market is None:
            market = idx.get((a, h))
            reversed_ = market is not None
        if market is None:
            continue
        seen.add(key)

        row = _fixture_match_row(pd.Series(fx._asdict()), names)
        hr, ar = model.get_rating(h), model.get_rating(a)
        base_adv = model._home_advantage_elo(row, h, a)
        base = model._outcome_probabilities(hr, ar, base_adv)
        delta = home_advantage_delta_elo(getattr(fx, "venue", None), h, a, baselines, coef=coef)
        alt = model._outcome_probabilities(hr, ar, base_adv + delta)

        devig, raw = market["devig"], market["raw"]
        if reversed_:  # market is stored in the opposite orientation
            devig = (devig[2], devig[1], devig[0])
            raw = (raw[2], raw[1], raw[0])

        meta = {
            "fixture_id": str(fx.fixture_id),
            "match_date": str(pd.Timestamp(fx.match_date).date()) if pd.notna(fx.match_date) else "",
            "venue": str(getattr(fx, "venue", "") or ""),
            "home_team_name": names.get(h, h),
            "away_team_name": names.get(a, a),
        }
        signals.extend(evaluate_fixture(
            meta, base, alt, devig, raw, delta,
            edge_threshold=edge_threshold, kelly_frac=kelly_frac,
        ))

    signals = rank_signals(signals)
    if record:
        from wc_predictor.lab.betting_ledger import record_signals
        record_signals(signals, as_of=as_of)
    if write_report:
        write_betting_report(signals, as_of=as_of, coef=coef, reports_dir=reports_dir)
    return signals


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def write_betting_report(
    signals: list[BetSignal], *, as_of: str, coef: float,
    reports_dir: str | Path = settings.REPORTS_DIR,
) -> Path:
    path = Path(reports_dir) / "betting" / f"disagreements_{as_of}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    bets = [s for s in signals if s.recommendation == "BET"]
    watch = [s for s in signals if s.recommendation == "WATCH"]

    lines = [
        f"# Betting disagreements vs Polymarket — as of {as_of}",
        "",
        "**Default stance: the de-vigged market out-predicts our model on average "
        "(shown 3 ways). A disagreement usually means *we* are wrong.** Only rows with "
        "a validated STRUCTURAL edge are promoted to BET; everything else is WATCH "
        "(informational, market probably right). EV uses the real offered price (with "
        "vig). Stakes are quarter-Kelly, capped at 5% of bankroll.",
        "",
        f"Structural edge in play: **altitude** (coef {coef:.0f} Elo/1000 m climb).",
        "",
        "## ✅ Recommended bets (structural edge)",
        "",
    ]
    if bets:
        lines += [
            "| Match | Date | Venue | Pick | Our p | Mkt (fair) | Offered | Edge | EV | Kelly | Why |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for s in bets:
            lines.append(
                f"| {s.home_team_name} vs {s.away_team_name} | {s.match_date} | {s.venue} | "
                f"**{s.selection}** | {_pct(s.our_prob)} | {_pct(s.market_prob)} | {_pct(s.offered_price)} | "
                f"{s.edge*100:+.1f}pp | {s.ev*100:+.1f}% | {_pct(s.kelly_stake)} | "
                f"altitude +{s.altitude_delta_elo:.0f} Elo |"
            )
    else:
        lines.append("_No structural-edge bets in the current slate._")

    lines += ["", "## 👀 Watch (disagreement, no validated edge — market likely right)", ""]
    if watch:
        lines += [
            "| Match | Date | Pick | Our p | Mkt (fair) | Offered | Edge | EV |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for s in watch:
            lines.append(
                f"| {s.home_team_name} vs {s.away_team_name} | {s.match_date} | {s.selection} | "
                f"{_pct(s.our_prob)} | {_pct(s.market_prob)} | {_pct(s.offered_price)} | "
                f"{s.edge*100:+.1f}pp | {s.ev*100:+.1f}% |"
            )
    else:
        lines.append("_No disagreements above threshold._")

    lines += [
        "",
        "## Caveats",
        "- Market prices are a live snapshot; they move with news, lineups, liquidity.",
        "- Only three-way match-result markets; props/spreads/totals excluded.",
        "- WATCH rows are where our model disagrees but has no validated edge — treat as "
        "areas to investigate, not bets.",
        "- Altitude edge is directionally validated but not statistically proven on its own "
        "(small sample); size conservatively.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
