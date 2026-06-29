"""Match-Analyst agent — the backtestable quantitative core.

This is the by-date, leak-free half of the analyst. For a single fixture and an
``as_of`` date it assembles a :class:`ContextPacket` from signals we can honestly
reconstruct for any historical match (Elo, de-vigged market, recent form,
altitude, the agent's own calibration history) and turns it into an H/D/A forecast
plus a single chosen winner.

Design stance (decided 2026-06-28 with Zach, earned the hard way in the edge hunt):
the de-vigged market out-predicts our Elo, so the analyst is **market-anchored** —
it starts from the market price and only deviates when a tracked signal (form,
altitude) justifies it, with the deviation capped. When no market price exists it
falls back to the Elo anchor nudged by the same signals.

The live half (news/lineups/social) is a Claude subagent that consumes the packet
this module emits (see ``.claude/agents/match-analyst.md`` + ``analyst_cli.py``);
that half is forward-only and not backtestable, by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import pandas as pd

_OUTCOMES = ("home", "draw", "away")

# How strongly recent form moves the anchor, and the hard cap on any single
# signal's Elo-equivalent push (keeps the analyst close to the market).
FORM_COEF = 40.0
MAX_SHIFT_ELO = 60.0


@dataclass(frozen=True)
class ContextPacket:
    """Everything the analyst (deterministic or live) gets to reason over."""

    fixture_id: str
    as_of: str
    match_date: str
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    venue: str
    elo_probs: tuple[float, float, float]
    elo_ratings: tuple[float, float, float]  # (home, away, home_advantage)
    market_probs: tuple[float, float, float] | None
    offered_prices: tuple[float, float, float] | None
    form_home: float          # last-N result rate (win=1, draw=0.5, loss=0)
    form_away: float
    altitude_delta_elo: float
    calib: dict[str, Any] = field(default_factory=dict)
    live_notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "as_of": self.as_of,
            "match_date": self.match_date,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "home_team_name": self.home_team_name,
            "away_team_name": self.away_team_name,
            "venue": self.venue,
            "elo_probs": list(self.elo_probs),
            "elo_ratings": list(self.elo_ratings),
            "market_probs": list(self.market_probs) if self.market_probs else None,
            "offered_prices": list(self.offered_prices) if self.offered_prices else None,
            "form_home": self.form_home,
            "form_away": self.form_away,
            "altitude_delta_elo": self.altitude_delta_elo,
            "calib": self.calib,
            "live_notes": self.live_notes,
        }


@dataclass(frozen=True)
class AnalystForecast:
    fixture_id: str
    as_of: str
    match_date: str
    home_team_name: str
    away_team_name: str
    p_home: float
    p_draw: float
    p_away: float
    pick: str           # "home" | "draw" | "away"
    pick_team: str      # team name or "Draw"
    confidence: float   # max(probs)
    rationale: str
    sources: list[str]
    mode: str           # "deterministic" | "agent"

    @property
    def probs(self) -> tuple[float, float, float]:
        return (self.p_home, self.p_draw, self.p_away)


# ---------------------------------------------------------------------------
# Signal helpers (leak-free)
# ---------------------------------------------------------------------------
def _normalize(probs: Sequence[float]) -> tuple[float, float, float]:
    p = [max(0.0, float(x)) for x in probs]
    total = sum(p)
    if total <= 0.0:
        return (1 / 3, 1 / 3, 1 / 3)
    return (p[0] / total, p[1] / total, p[2] / total)


def recent_form(
    matches: pd.DataFrame, team_id: str, as_of: str, *, n: int = 5
) -> float:
    """Last-`n` result rate (win=1, draw=0.5, loss=0) strictly before `as_of`.

    Mirrors the windowing idiom in ``lab/variants/recent_form.py`` but as a pure,
    as-of-bounded function so it can be replayed for any historical date. Returns
    0.5 (neutral) when the team has no prior matches.
    """

    if matches is None or matches.empty:
        return 0.5
    tid = str(team_id)
    cutoff = pd.Timestamp(as_of)
    dates = pd.to_datetime(matches["date"], errors="coerce")
    mask = (dates < cutoff) & (
        (matches["home_team_id"].astype(str) == tid)
        | (matches["away_team_id"].astype(str) == tid)
    )
    sub = matches.loc[mask].copy()
    if sub.empty:
        return 0.5
    sub["_d"] = dates[mask]
    sort_cols = ["_d"]
    if "occurrence_index" in sub.columns:
        sort_cols.append("occurrence_index")
    if "match_id" in sub.columns:
        sort_cols.append("match_id")
    sub = sub.sort_values(sort_cols, kind="mergesort")

    results: list[float] = []
    for _, row in sub.iterrows():
        hs, as_ = row.get("home_score"), row.get("away_score")
        if pd.isna(hs) or pd.isna(as_):
            continue
        is_home = str(row["home_team_id"]) == tid
        if hs == as_:
            results.append(0.5)
        elif (hs > as_) == is_home:
            results.append(1.0)
        else:
            results.append(0.0)
    if not results:
        return 0.5
    window = results[-n:]
    return sum(window) / len(window)


def build_packet(
    row: pd.Series,
    as_of: str,
    *,
    matches: pd.DataFrame,
    altitude_delta_elo: float = 0.0,
    market_probs: tuple[float, float, float] | None = None,
    offered_prices: tuple[float, float, float] | None = None,
    calib: dict[str, Any] | None = None,
    live_notes: list[str] | None = None,
) -> ContextPacket:
    """Assemble a leak-free packet from a market964-style row (or a fixture row).

    The row must carry ``elo_prob_*``, ``elo_home_rating``/``elo_away_rating``/
    ``elo_home_advantage``, ids, names and a date. ``market_probs`` are read from
    ``market_prob_*`` columns when present and not passed explicitly.
    """

    def _g(key, default=""):
        val = row.get(key, default)
        return default if val is None or (not isinstance(val, (list, dict)) and pd.isna(val)) else val

    hid, aid = str(_g("home_team_id")), str(_g("away_team_id"))
    if market_probs is None and "market_prob_home" in row.index:
        market_probs = _normalize(
            (float(row["market_prob_home"]), float(row["market_prob_draw"]), float(row["market_prob_away"]))
        )
    elo_probs = _normalize(
        (float(_g("elo_prob_home", 1 / 3)), float(_g("elo_prob_draw", 1 / 3)), float(_g("elo_prob_away", 1 / 3)))
    )
    return ContextPacket(
        fixture_id=str(_g("match_id") or _g("fixture_id")),
        as_of=str(as_of),
        match_date=str(_g("date") or _g("match_date")),
        home_team_id=hid,
        away_team_id=aid,
        home_team_name=str(_g("home_team") or _g("home_team_name") or hid),
        away_team_name=str(_g("away_team") or _g("away_team_name") or aid),
        venue=str(_g("city") or _g("venue")),
        elo_probs=elo_probs,
        elo_ratings=(
            float(_g("elo_home_rating", 1500.0)),
            float(_g("elo_away_rating", 1500.0)),
            float(_g("elo_home_advantage", 0.0)),
        ),
        market_probs=market_probs,
        offered_prices=offered_prices,
        form_home=recent_form(matches, hid, as_of),
        form_away=recent_form(matches, aid, as_of),
        altitude_delta_elo=float(altitude_delta_elo),
        calib=dict(calib or {}),
        live_notes=live_notes,
    )


# ---------------------------------------------------------------------------
# The deterministic, market-anchored analyst
# ---------------------------------------------------------------------------
def _apply_elo_delta(anchor: tuple[float, float, float], delta_elo: float) -> tuple[float, float, float]:
    """Shift the home-vs-away split of `anchor` by an Elo delta, keeping the draw.

    delta_elo > 0 favours home. We move only the H-vs-A balance (form/altitude are
    strength signals, not draw-rate signals) using the Elo odds multiplier
    10**(delta/400), then renormalize. delta_elo == 0 returns the anchor unchanged.
    """

    ph, pd_, pa = anchor
    if delta_elo == 0.0 or ph <= 0.0 or pa <= 0.0:
        return _normalize(anchor)
    non_draw = ph + pa
    factor = 10.0 ** (delta_elo / 400.0)
    ratio = (ph / pa) * factor  # new home:away odds
    new_home = non_draw * ratio / (1.0 + ratio)
    new_away = non_draw - new_home
    return _normalize((new_home, pd_, new_away))


def _temper(probs: tuple[float, float, float], temp: float) -> tuple[float, float, float]:
    if temp == 1.0 or temp <= 0.0:
        return _normalize(probs)
    return _normalize(tuple(p ** (1.0 / temp) for p in probs))


def signal_delta_elo(
    packet: ContextPacket, *, form_coef: float = FORM_COEF, max_shift_elo: float = MAX_SHIFT_ELO
) -> float:
    """Combined Elo-equivalent push from tracked signals (form + altitude), capped."""

    form_delta = form_coef * (packet.form_home - packet.form_away)
    form_delta = max(-max_shift_elo, min(max_shift_elo, form_delta))
    total = form_delta + packet.altitude_delta_elo
    return max(-max_shift_elo, min(max_shift_elo, total))


def deterministic_analyst(
    packet: ContextPacket,
    *,
    form_coef: float = FORM_COEF,
    max_shift_elo: float = MAX_SHIFT_ELO,
    temp: float = 1.0,
) -> AnalystForecast:
    """Market-anchored forecast: start at the market, deviate on signal, capped.

    Falls back to the Elo anchor when no market price is available. Pure and
    deterministic. ``temp`` (>1 softens, <1 sharpens) lets the agent's own
    calibration history feed back in via ``calibration_summary``.
    """

    anchored_to = "market" if packet.market_probs is not None else "elo"
    anchor = packet.market_probs if packet.market_probs is not None else packet.elo_probs
    delta = signal_delta_elo(packet, form_coef=form_coef, max_shift_elo=max_shift_elo)
    probs = _temper(_apply_elo_delta(anchor, delta), temp)

    idx = max(range(3), key=lambda i: probs[i])
    pick = _OUTCOMES[idx]
    pick_team = (
        packet.home_team_name if pick == "home"
        else "Draw" if pick == "draw"
        else packet.away_team_name
    )
    bits = [f"anchored to {anchored_to} ({anchor[0]:.0%}/{anchor[1]:.0%}/{anchor[2]:.0%})"]
    if delta:
        side = "home" if delta > 0 else "away"
        bits.append(f"form/altitude push {delta:+.0f} Elo → {side}")
    if temp != 1.0:
        bits.append(f"temp {temp:.2f} from own history")
    return AnalystForecast(
        fixture_id=packet.fixture_id,
        as_of=packet.as_of,
        match_date=packet.match_date,
        home_team_name=packet.home_team_name,
        away_team_name=packet.away_team_name,
        p_home=probs[0],
        p_draw=probs[1],
        p_away=probs[2],
        pick=pick,
        pick_team=pick_team,
        confidence=probs[idx],
        rationale="; ".join(bits),
        sources=["elo", anchored_to, "recent_form"]
        + (["altitude"] if packet.altitude_delta_elo else []),
        mode="deterministic",
    )
