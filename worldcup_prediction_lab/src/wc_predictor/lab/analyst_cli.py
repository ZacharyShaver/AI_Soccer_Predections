"""CLI bridge between the Python data layer and the live match-analyst subagent.

The Claude subagent (``.claude/agents/match-analyst.md``) is sandboxed to tools, not
to our internals — so it talks to the model through this CLI:

  dump-packet --fixture <id|HomeName,AwayName> --as-of <YYYY-MM-DD> [--out path]
      Build the leak-free ContextPacket + deterministic baseline forecast for a
      fixture and write it as JSON. The subagent reads this, does its web research,
      and decides how far to deviate from the market anchor.

  record --json <path>
      Append an agent-authored forecast (its JSON) to the analyst ledger as an
      ``agent``-mode row, so it joins the live track record.

Mirrors the live model wiring in ``lab/betting.run_betting`` (same RECAL config,
host-advantage fn, altitude baselines).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.lab.analyst import AnalystForecast, build_packet, deterministic_analyst


def _build_live_context(as_of: str):
    """Fit the live model as-of `as_of` and return the pieces build_packet needs."""

    from wc_predictor.forecast_live import (
        _fixture_match_row,
        _team_names,
        _training_matches,
        build_world_cup_host_advantage_fn,
        load_silver_data,
    )
    from wc_predictor.lab.altitude import home_advantage_delta_elo, team_altitude_baselines
    from wc_predictor.lab.betting import RECAL, _market_index
    from wc_predictor.models.elo import EloModel

    matches, fixtures, teams = load_silver_data()
    names = _team_names(teams)
    model = EloModel(
        **RECAL,
        generated_at_utc=f"{as_of}T00:00:00Z",
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
    model.fit(_training_matches(matches, training_cutoff=as_of))
    baselines = team_altitude_baselines(matches)

    idx: dict = {}
    try:
        from wc_predictor.data.ingest_polymarket import (
            fetch_world_cup_markets,
            parse_world_cup_match_events,
        )

        _, events = fetch_world_cup_markets()
        market_rows, _ = parse_world_cup_match_events(events)
        idx = _market_index(market_rows)
    except Exception:
        idx = {}  # no live market → analyst falls back to the Elo anchor

    return matches, fixtures, names, model, baselines, idx, _fixture_match_row, home_advantage_delta_elo


def run_analyst_live(as_of: str, *, record: bool = True) -> list:
    """Deterministic analyst forecasts for all upcoming fixtures (>= as_of).

    Used by the dashboard. Records each (idempotent) to the analyst ledger with its
    Elo/market baselines frozen, so the deterministic floor builds a forward record
    alongside the live agent-mode calls. Pure-Python; network failure on the market
    fetch degrades to Elo-anchored forecasts.
    """

    from wc_predictor.lab.analyst_ledger import calibration_summary, load_ledger, record_forecast, resolve_forecasts

    (matches, fixtures, names, model, baselines, idx,
     _fixture_match_row, home_advantage_delta_elo) = _build_live_context(as_of)

    # Feed the agent's own resolved history back in as a calibration temperature.
    try:
        from wc_predictor.lab.leaderboard import load_results

        results_df = load_results()
        results = {
            str(r["match_id"]): (int(r["home_score"]), int(r["away_score"]))
            for _, r in results_df.iterrows()
        } if not results_df.empty else {}
        temp = calibration_summary(resolve_forecasts(load_ledger(), results), mode="deterministic")["temp"]
    except Exception:
        temp = 1.0

    today = pd.Timestamp(as_of)
    forecasts, elo_map, mkt_map = [], {}, {}
    seen: set[frozenset] = set()
    for fx in fixtures.itertuples(index=False):
        hid, aid = str(fx.home_team_id), str(fx.away_team_id)
        if hid in ("", "nan") or aid in ("", "nan"):
            continue
        try:
            if pd.notna(fx.match_date) and pd.Timestamp(fx.match_date) < today:
                continue
        except Exception:
            pass
        key = frozenset((hid, aid))
        if key in seen:
            continue
        seen.add(key)

        row = _fixture_match_row(pd.Series(fx._asdict()), names)
        hr, ar = model.get_rating(hid), model.get_rating(aid)
        base_adv = model._home_advantage_elo(row, hid, aid)
        elo = model._outcome_probabilities(hr, ar, base_adv)
        delta = home_advantage_delta_elo(getattr(fx, "venue", None), hid, aid, baselines, coef=60.0)

        market = idx.get((hid, aid))
        reversed_ = False
        if market is None:
            market = idx.get((aid, hid))
            reversed_ = market is not None
        market_probs = None
        if market is not None:
            devig = market["devig"]
            market_probs = (devig[2], devig[1], devig[0]) if reversed_ else devig

        packet_row = pd.Series({
            "match_id": str(fx.fixture_id), "fixture_id": str(fx.fixture_id),
            "date": str(pd.Timestamp(fx.match_date).date()) if pd.notna(fx.match_date) else "",
            "home_team_id": hid, "away_team_id": aid,
            "home_team": names.get(hid, hid), "away_team": names.get(aid, aid),
            "city": str(getattr(fx, "venue", "") or ""),
            "elo_prob_home": elo[0], "elo_prob_draw": elo[1], "elo_prob_away": elo[2],
            "elo_home_rating": hr, "elo_away_rating": ar, "elo_home_advantage": base_adv,
        })
        packet = build_packet(packet_row, as_of, matches=matches,
                              altitude_delta_elo=delta, market_probs=market_probs)
        fc = deterministic_analyst(packet, temp=temp)
        forecasts.append(fc)
        elo_map[fc.fixture_id] = elo
        if market_probs is not None:
            mkt_map[fc.fixture_id] = market_probs

    if record and forecasts:
        record_forecast(forecasts, as_of=as_of, elo_probs=elo_map, market_probs=mkt_map)
    return forecasts


def _find_fixture(fixtures: pd.DataFrame, names: dict[str, str], fixture: str) -> pd.Series:
    """Resolve a fixture by id or by 'HomeName,AwayName' (case-insensitive)."""

    fid_col = fixtures["fixture_id"].astype(str)
    hit = fixtures[fid_col == str(fixture)]
    if not hit.empty:
        return hit.iloc[0]
    if "," in fixture:
        home, away = (s.strip().lower() for s in fixture.split(",", 1))
        rev = {v.lower(): k for k, v in names.items()}
        hid, aid = rev.get(home), rev.get(away)
        if hid and aid:
            m = fixtures[
                (fixtures["home_team_id"].astype(str) == hid)
                & (fixtures["away_team_id"].astype(str) == aid)
            ]
            if not m.empty:
                return m.iloc[0]
    raise SystemExit(f"fixture not found: {fixture!r}")


def cmd_dump_packet(args: argparse.Namespace) -> None:
    as_of = args.as_of
    (matches, fixtures, names, model, baselines, idx,
     _fixture_match_row, home_advantage_delta_elo) = _build_live_context(as_of)

    fx = _find_fixture(fixtures, names, args.fixture)
    hid, aid = str(fx.home_team_id), str(fx.away_team_id)

    row = _fixture_match_row(pd.Series(fx._asdict() if hasattr(fx, "_asdict") else fx.to_dict()), names)
    hr, ar = model.get_rating(hid), model.get_rating(aid)
    base_adv = model._home_advantage_elo(row, hid, aid)
    elo = model._outcome_probabilities(hr, ar, base_adv)
    delta = home_advantage_delta_elo(getattr(fx, "venue", None), hid, aid, baselines, coef=60.0)

    market = idx.get((hid, aid))
    reversed_ = False
    if market is None:
        market = idx.get((aid, hid))
        reversed_ = market is not None
    market_probs = offered = None
    if market is not None:
        devig, raw = market["devig"], market["raw"]
        if reversed_:
            devig, raw = (devig[2], devig[1], devig[0]), (raw[2], raw[1], raw[0])
        market_probs, offered = devig, raw

    packet_row = pd.Series({
        "match_id": str(fx.fixture_id),
        "fixture_id": str(fx.fixture_id),
        "date": str(pd.Timestamp(fx.match_date).date()) if pd.notna(fx.match_date) else "",
        "home_team_id": hid, "away_team_id": aid,
        "home_team": names.get(hid, hid), "away_team": names.get(aid, aid),
        "city": str(getattr(fx, "venue", "") or ""),
        "elo_prob_home": elo[0], "elo_prob_draw": elo[1], "elo_prob_away": elo[2],
        "elo_home_rating": hr, "elo_away_rating": ar, "elo_home_advantage": base_adv,
    })
    packet = build_packet(
        packet_row, as_of, matches=matches, altitude_delta_elo=delta,
        market_probs=market_probs, offered_prices=offered,
    )
    baseline = deterministic_analyst(packet)
    payload = {
        "packet": packet.to_dict(),
        "deterministic_baseline": {
            "p_home": baseline.p_home, "p_draw": baseline.p_draw, "p_away": baseline.p_away,
            "pick": baseline.pick, "pick_team": baseline.pick_team,
            "rationale": baseline.rationale,
        },
        "instructions": (
            "Anchor to the market probs. Deviate only on concrete, cited findings "
            "(confirmed lineups, injuries, suspensions, travel, weather, odds moves). "
            "Output p_home+p_draw+p_away=1.0, a single pick, a short rationale, and a "
            "sources list of URLs with dates. If you find nothing, return the baseline."
        ),
    }
    out = Path(args.out) if args.out else (settings.REPORTS_DIR / "analyst" / f"packet_{packet.fixture_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(str(out))


def cmd_record(args: argparse.Namespace) -> None:
    from wc_predictor.lab.analyst_ledger import record_forecast

    data = json.loads(Path(args.json).read_text(encoding="utf-8"))
    p = (float(data["p_home"]), float(data["p_draw"]), float(data["p_away"]))
    total = sum(p)
    if not (0.99 <= total <= 1.01):
        raise SystemExit(f"probabilities must sum to 1.0 (got {total:.3f})")
    p = tuple(v / total for v in p)
    idx = max(range(3), key=lambda i: p[i])
    pick = ("home", "draw", "away")[idx]
    forecast = AnalystForecast(
        fixture_id=str(data["fixture_id"]),
        as_of=str(data["as_of"]),
        match_date=str(data.get("match_date", "")),
        home_team_name=str(data.get("home_team_name", "")),
        away_team_name=str(data.get("away_team_name", "")),
        p_home=p[0], p_draw=p[1], p_away=p[2],
        pick=str(data.get("pick", pick)),
        pick_team=str(data.get("pick_team", "")),
        confidence=max(p),
        rationale=str(data.get("rationale", "")),
        sources=list(data.get("sources", [])),
        mode="agent",
    )
    elo = {forecast.fixture_id: tuple(data["elo_probs"])} if data.get("elo_probs") else None
    mkt = {forecast.fixture_id: tuple(data["market_probs"])} if data.get("market_probs") else None
    added = record_forecast([forecast], as_of=forecast.as_of, elo_probs=elo, market_probs=mkt)
    print(f"recorded {added} agent forecast(s) for fixture {forecast.fixture_id}")


def cmd_list_fixtures(args: argparse.Namespace) -> None:
    """Print fixtures kicking off within [as_of, as_of+days) as TSV lines.

    Columns: fixture_id<TAB>Home<TAB>Away<TAB>venue. Used by the daily morning job
    to decide which matches to send to the live match-analyst subagent. Already-
    researched fixtures (an agent-mode row in the ledger) are skipped unless --all.
    """

    from wc_predictor.forecast_live import _team_names, load_silver_data

    _, fixtures, teams = load_silver_data()
    names = _team_names(teams)
    start = pd.Timestamp(args.as_of)
    end = start + pd.Timedelta(days=max(1, args.days))

    done: set[str] = set()
    if not args.all:
        try:
            from wc_predictor.lab.analyst_ledger import load_ledger

            done = {str(r["fixture_id"]) for r in load_ledger() if r.get("mode") == "agent"}
        except Exception:
            done = set()

    seen: set[frozenset] = set()
    for fx in fixtures.itertuples(index=False):
        hid, aid = str(fx.home_team_id), str(fx.away_team_id)
        if hid in ("", "nan") or aid in ("", "nan"):
            continue
        try:
            if not (pd.notna(fx.match_date) and start <= pd.Timestamp(fx.match_date) < end):
                continue
        except Exception:
            continue
        if str(fx.fixture_id) in done:
            continue
        key = frozenset((hid, aid))
        if key in seen:
            continue
        seen.add(key)
        print(f"{fx.fixture_id}\t{names.get(hid, hid)}\t{names.get(aid, aid)}\t{getattr(fx, 'venue', '') or ''}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Match-analyst CLI bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)

    dp = sub.add_parser("dump-packet", help="write a leak-free context packet JSON")
    dp.add_argument("--fixture", required=True, help="fixture_id or 'HomeName,AwayName'")
    dp.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    dp.add_argument("--out", default=None, help="output JSON path")
    dp.set_defaults(func=cmd_dump_packet)

    lf = sub.add_parser("list-fixtures", help="list fixtures to research (TSV)")
    lf.add_argument("--as-of", required=True, help="YYYY-MM-DD (today)")
    lf.add_argument("--days", type=int, default=1, help="window size in days (default 1 = today)")
    lf.add_argument("--all", action="store_true", help="include already-researched fixtures")
    lf.set_defaults(func=cmd_list_fixtures)

    rc = sub.add_parser("record", help="append an agent forecast JSON to the ledger")
    rc.add_argument("--json", required=True, help="path to the agent forecast JSON")
    rc.set_defaults(func=cmd_record)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
