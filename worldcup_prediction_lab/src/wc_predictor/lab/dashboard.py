"""Render a self-contained HTML dashboard for the daily model-research lab.

Reads the live experiment ledger + results + leaderboard and emits a single
offline HTML file (inline CSS, no external assets) at research/dashboard.html.
Regenerate any time; it reflects whatever has been scored so far.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.metrics import ranked_probability_score
from wc_predictor.forecast_live import load_silver_data
from wc_predictor.lab.backtest import load_cache as load_backtest_cache
from wc_predictor.lab.leaderboard import (
    BASELINE_VARIANT,
    build_standings,
    collect_predictions,
    load_results,
)
from wc_predictor.lab.upset import assess_upset_risk, format_upset_risk

OUT_PATH = settings.RESEARCH_DIR / "dashboard.html"
PAGES_OUT_PATH = settings.PROJECT_DIR.parent / "docs" / "index.html"
_OUTCOMES = ("home", "draw", "away")
PREFERRED_FORECAST_VARIANT = "ensemble_top_k"


def _outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def _esc(value: object) -> str:
    return html.escape(str(value))


def _team_name_map(teams: pd.DataFrame) -> dict[str, str]:
    return (
        teams.drop_duplicates("canonical_team_id")
        .set_index("canonical_team_id")["canonical_name"]
        .astype(str)
        .to_dict()
    )


def _pick(probs: tuple[float, float, float]) -> str:
    return _OUTCOMES[probs.index(max(probs))]


def _bar(probs: tuple[float, float, float], actual: str | None = None) -> str:
    """Stacked H/D/A probability bar; the actual outcome segment gets an outline."""
    labels = ("H", "D", "A")
    classes = ("h", "d", "a")
    cells = []
    for label, cls, prob, key in zip(labels, classes, probs, _OUTCOMES):
        pct = prob * 100.0
        outline = " seg-actual" if actual == key else ""
        text = f"{label} {pct:.0f}" if pct >= 12 else ""
        cells.append(
            f'<div class="seg seg-{cls}{outline}" style="width:{pct:.3f}%" title="{label} {pct:.1f}%">{text}</div>'
        )
    return f'<div class="bar">{"".join(cells)}</div>'


def _upcoming_bar(probs: tuple[float, float, float]) -> str:
    """Readable H/D/A probability display for the wider upcoming forecast table."""
    labels = ("H", "D", "A")
    classes = ("h", "d", "a")
    label_cells = "".join(
        f'<span class="plabel plabel-{cls}">{label} {prob * 100.0:.0f}</span>'
        for label, cls, prob in zip(labels, classes, probs)
    )
    segments = "".join(
        f'<div class="seg seg-{cls}" style="width:{prob * 100.0:.3f}%" title="{label} {prob * 100.0:.1f}%"></div>'
        for label, cls, prob in zip(labels, classes, probs)
    )
    return f'<div class="probwrap"><div class="problabels">{label_cells}</div><div class="bar">{"".join(segments)}</div></div>'


def _upset_cell(probs: tuple[float, float, float]) -> str:
    risk = assess_upset_risk(probs)
    title = f"underdog: {risk.underdog}; favorite: {risk.favorite}"
    return (
        f'<span class="risk risk-{risk.label.lower()}" title="{_esc(title)}">'
        f"{_esc(format_upset_risk(risk))}</span>"
    )


def _fmt(value: float | None, digits: int = 4) -> str:
    return f"{value:.{digits}f}" if value is not None else "—"


def _pct(value: float | None) -> str:
    return f"{value * 100.0:.0f}%" if value is not None else "—"


def _select_upcoming_match_ids(
    match_ids: list[str],
    *,
    fixture_date,
    today: str,
    limit: int = 14,
) -> list[str]:
    """Today's and future fixtures, soonest first.

    A predicted match with no result yet is either genuinely upcoming (incl.
    today's slate) or already played and just awaiting result ingestion (martj42
    lags a day or two). We keep today and the future and drop only strictly-past
    dates, so today's games still show as forecasts while stale already-played
    matches are removed. String dates compare correctly as YYYY-MM-DD.
    """

    upcoming = [m for m in match_ids if fixture_date(m) and fixture_date(m) >= today]
    return sorted(upcoming, key=lambda m: (fixture_date(m), m))[:limit]


def _fixture_day(fixture: object) -> str:
    try:
        value = fixture.get("match_date") if isinstance(fixture, dict) else fixture["match_date"]
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _accuracy_timeline(
    scored_match_ids: list[str],
    *,
    fixture_info: dict[str, object],
    results: dict[str, tuple[int, int]],
    pred_lookup: dict[tuple[str, str], tuple[float, float, float]],
    variant_id: str = BASELINE_VARIANT,
) -> list[dict]:
    by_day: dict[str, dict[str, int]] = {}
    for mid in scored_match_ids:
        probs = pred_lookup.get((variant_id, mid))
        scores = results.get(mid)
        if probs is None or scores is None:
            continue
        day = _fixture_day(fixture_info.get(mid, {}))
        if not day:
            continue

        actual = _outcome(scores[0], scores[1])
        bucket = by_day.setdefault(
            day,
            {"n": 0, "hits": 0, "decisive_n": 0, "decisive_hits": 0},
        )
        hit = int(_pick(probs) == actual)
        bucket["n"] += 1
        bucket["hits"] += hit
        if actual != "draw":
            bucket["decisive_n"] += 1
            bucket["decisive_hits"] += hit

    rows: list[dict] = []
    cumulative_n = 0
    cumulative_hits = 0
    cumulative_decisive_n = 0
    cumulative_decisive_hits = 0
    for day in sorted(by_day):
        n = by_day[day]["n"]
        hits = by_day[day]["hits"]
        decisive_n = by_day[day]["decisive_n"]
        decisive_hits = by_day[day]["decisive_hits"]
        cumulative_n += n
        cumulative_hits += hits
        cumulative_decisive_n += decisive_n
        cumulative_decisive_hits += decisive_hits
        rows.append(
            {
                "date": day,
                "n": n,
                "hits": hits,
                "daily_accuracy": hits / n if n else None,
                "decisive_n": decisive_n,
                "decisive_hits": decisive_hits,
                "daily_decisive_accuracy": decisive_hits / decisive_n
                if decisive_n
                else None,
                "cumulative_n": cumulative_n,
                "cumulative_hits": cumulative_hits,
                "cumulative_accuracy": cumulative_hits / cumulative_n
                if cumulative_n
                else None,
                "cumulative_decisive_n": cumulative_decisive_n,
                "cumulative_decisive_hits": cumulative_decisive_hits,
                "cumulative_decisive_accuracy": (
                    cumulative_decisive_hits / cumulative_decisive_n
                    if cumulative_decisive_n
                    else None
                ),
            }
        )
    return rows


def _accuracy_timeline_section(rows: list[dict], *, variant_id: str) -> str:
    if not rows:
        return ""

    latest = rows[-1]
    body_rows = []
    for row in rows:
        cumulative = row["cumulative_accuracy"]
        width = max(0.0, min(100.0, (cumulative or 0.0) * 100.0))
        decisive = row.get("cumulative_decisive_accuracy")
        decisive_width = max(0.0, min(100.0, (decisive or 0.0) * 100.0))
        body_rows.append(
            f'<tr><td class="dt">{_esc(row["date"])}</td>'
            f'<td class="num">{row["hits"]}/{row["n"]}</td>'
            f'<td class="num">{_pct(row["daily_accuracy"])}</td>'
            f'<td class="accbarcell"><div class="accbar"><div class="accfill" style="width:{width:.1f}%"></div>'
            f'<span>{_pct(cumulative)}</span></div></td>'
            f'<td class="num">{row["cumulative_hits"]}/{row["cumulative_n"]}</td>'
            f'<td class="num">{row.get("decisive_hits", 0)}/{row.get("decisive_n", 0)}</td>'
            f'<td class="accbarcell"><div class="accbar decisive"><div class="accfill decisive" style="width:{decisive_width:.1f}%"></div>'
            f'<span>{_pct(decisive)}</span></div></td></tr>'
        )

    latest_decisive_hits = latest.get("cumulative_decisive_hits", 0)
    latest_decisive_n = latest.get("cumulative_decisive_n", 0)
    return (
        f'<details class="sec"><summary>Accuracy over time <span class="h2sub">· {_esc(variant_id)} cumulative outcome picks</span></summary>'
        '<div class="secbody">'
        '<div class="accuracy-card">'
        '<div class="accsummary">'
        f'<div><div class="bigacc">{_pct(latest["cumulative_accuracy"])}</div>'
        f'<div class="metriclabel">Overall incl. draws · {latest["cumulative_hits"]}/{latest["cumulative_n"]}</div></div>'
        f'<div><div class="bigacc decisive">{_pct(latest.get("cumulative_decisive_accuracy"))}</div>'
        f'<div class="metriclabel">Decisive only · {latest_decisive_hits}/{latest_decisive_n}</div></div>'
        '</div>'
        '<div class="note">Overall accuracy includes draws; decisive accuracy excludes drawn matches so it aligns with leaderboard dec.acc. '
        'Daily accuracy shows only matches resolved on that date.</div>'
        '<table class="timeline"><thead><tr><th>date</th><th class="num">daily hits</th>'
        '<th class="num">daily acc</th><th>overall cumulative</th><th class="num">cum. hits</th>'
        '<th class="num">decisive hits</th><th>decisive cumulative</th></tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
        '</div></details>'
    )


def _betting_section() -> str:
    """Best-effort 'betting edges vs Polymarket' section.

    Fetches the live market and runs the disagreement engine. Network/market
    failures must never break the dashboard, so the whole thing is guarded and
    degrades to a muted note.
    """

    try:
        from wc_predictor.lab.betting import run_betting

        as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        signals = run_betting(
            as_of=as_of,
            training_cutoff=as_of,
            generated_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            write_report=False,
        )
    except Exception as exc:  # pragma: no cover - live/network dependent
        return (
            '<details class="sec"><summary>Betting edges vs Polymarket '
            '<span class="h2sub">· live market disagreements</span></summary>'
            f'<div class="secbody"><p class="muted">Live market unavailable right now '
            f'({_esc(type(exc).__name__)}). Re-runs on the next refresh.</p></div></details>'
        )

    bets = [s for s in signals if s.recommendation == "BET"]
    watch = [s for s in signals if s.recommendation == "WATCH"]

    def _sig_row(s, *, with_extra: bool) -> str:
        extra = (
            f'<td class="num">{_pct(s.kelly_stake)}</td>'
            f'<td>altitude +{s.altitude_delta_elo:.0f} Elo</td>'
            if with_extra
            else ""
        )
        return (
            f'<tr><td class="vname">{_esc(s.home_team_name)} v {_esc(s.away_team_name)}</td>'
            f'<td class="dt">{_esc(s.match_date)}</td>'
            f'<td>{_esc(s.selection)}</td>'
            f'<td class="num" data-sort="{s.our_prob}">{_pct(s.our_prob)}</td>'
            f'<td class="num" data-sort="{s.market_prob}">{_pct(s.market_prob)}</td>'
            f'<td class="num" data-sort="{s.offered_price}">{_pct(s.offered_price)}</td>'
            f'<td class="num" data-sort="{s.edge}">{s.edge * 100:+.1f}pp</td>'
            f'<td class="num strong" data-sort="{s.ev}">{s.ev * 100:+.1f}%</td>'
            f"{extra}</tr>"
        )

    bet_block = (
        '<table class="lb sortable"><thead><tr><th>match</th><th>date</th><th>pick</th>'
        '<th class="num">our p</th><th class="num">mkt fair</th><th class="num">offered</th>'
        '<th class="num">edge</th><th class="num">EV</th><th class="num">Kelly</th><th>why</th></tr></thead>'
        f'<tbody>{"".join(_sig_row(s, with_extra=True) for s in bets)}</tbody></table>'
        if bets
        else '<p class="muted">No structural-edge bets in the current slate.</p>'
    )
    watch_block = (
        '<table class="lb sortable"><thead><tr><th>match</th><th>date</th><th>pick</th>'
        '<th class="num">our p</th><th class="num">mkt fair</th><th class="num">offered</th>'
        '<th class="num">edge</th><th class="num">EV</th></tr></thead>'
        f'<tbody>{"".join(_sig_row(s, with_extra=False) for s in watch)}</tbody></table>'
        if watch
        else '<p class="muted">No disagreements above threshold.</p>'
    )

    return (
        '<details class="sec"><summary>Betting edges vs Polymarket '
        f'<span class="h2sub">· {len(bets)} bet · {len(watch)} watch · click a column to sort</span></summary>'
        '<div class="secbody">'
        '<div class="note">Default stance: the de-vigged market out-predicts our model on average — '
        'a disagreement usually means <b>we</b> are wrong. Only altitude-backed rows are <b>BET</b>; '
        'the rest are <b>WATCH</b> (market probably right). EV uses real offered prices; stakes are '
        'quarter-Kelly capped at 5%.</div>'
        '<h3 class="subh">✅ Recommended bets <span class="h2sub">· structural edge</span></h3>'
        f"{bet_block}"
        '<h3 class="subh">👀 Watch <span class="h2sub">· no validated edge</span></h3>'
        f"{watch_block}"
        "</div></details>"
    )


def _write_dashboard_outputs(
    html_doc: str,
    *,
    out_path: str | Path = OUT_PATH,
    publish_pages: bool = True,
    pages_path: str | Path = PAGES_OUT_PATH,
) -> Path:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html_doc, encoding="utf-8")

    if publish_pages:
        pages_target = Path(pages_path)
        pages_target.parent.mkdir(parents=True, exist_ok=True)
        pages_target.write_text(html_doc, encoding="utf-8")

    return target


def build_dashboard(
    out_path: str | Path = OUT_PATH,
    *,
    publish_pages: bool = True,
    pages_path: str | Path = PAGES_OUT_PATH,
) -> Path:
    standings = build_standings()
    results_df = load_results()
    predictions = collect_predictions()
    matches, fixtures, teams = load_silver_data()

    names = _team_name_map(teams)
    fixture_info = {str(r["fixture_id"]): r for _, r in fixtures.iterrows()}
    results = {
        str(r["match_id"]): (int(r["home_score"]), int(r["away_score"]))
        for _, r in results_df.iterrows()
    } if not results_df.empty else {}

    # Per-(variant, match) latest prediction lookup.
    pred_lookup: dict[tuple[str, str], tuple[float, float, float]] = {}
    pred_match_ids: set[str] = set()
    if not predictions.empty:
        for row in predictions.to_dict("records"):
            key = (row["variant_id"], str(row["match_id"]))
            pred_lookup[key] = (row["prob_home"], row["prob_draw"], row["prob_away"])
            pred_match_ids.add(str(row["match_id"]))

    variant_ids = [s.variant_id for s in standings]

    # ---- Summary numbers (using the baseline as the reference model) ----
    scored_match_ids = sorted(mid for mid in pred_match_ids if mid in results)
    upcoming_match_ids = [mid for mid in pred_match_ids if mid not in results]
    baseline_hits = 0
    for mid in scored_match_ids:
        probs = pred_lookup.get((BASELINE_VARIANT, mid))
        if probs is None:
            continue
        hs, a = results[mid]
        if _pick(probs) == _outcome(hs, a):
            baseline_hits += 1
    n_scored = len(scored_match_ids)
    accuracy = (baseline_hits / n_scored * 100.0) if n_scored else None
    accuracy_rows = _accuracy_timeline(
        scored_match_ids,
        fixture_info=fixture_info,
        results=results,
        pred_lookup=pred_lookup,
        variant_id=BASELINE_VARIANT,
    )
    accuracy_section = _accuracy_timeline_section(
        accuracy_rows,
        variant_id=BASELINE_VARIANT,
    )
    days = sorted({d.name.split("=", 1)[1] for d in (settings.EXPERIMENTS_DIR).glob("date=*")}) \
        if settings.EXPERIMENTS_DIR.exists() else []
    leader = next((s for s in standings if s.n_scored > 0), None)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ---- Leaderboard rows ----
    max_abs_edge = max(
        [abs(s.edge_vs_baseline_rps) for s in standings if s.edge_vs_baseline_rps], default=0.0
    ) or 1.0
    lb_rows = []
    for rank, s in enumerate(standings, start=1):
        is_base = s.variant_id == BASELINE_VARIANT
        edge = s.edge_vs_baseline_rps
        if edge is None or s.n_scored == 0:
            edge_cell = '<span class="muted">—</span>'
        else:
            width = abs(edge) / max_abs_edge * 100.0
            side = "pos" if edge > 0 else ("neg" if edge < 0 else "zero")
            edge_cell = (
                f'<div class="edgewrap"><div class="edgebar {side}" style="width:{width:.1f}%"></div>'
                f'<span class="edgeval">{edge:+.4f}</span></div>'
            )
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "") if s.n_scored > 0 else ""
        crown = ' <span class="tag">baseline</span>' if is_base else ""
        lead = " lead" if (leader and s.variant_id == leader.variant_id) else ""
        lb_rows.append(
            f'<tr class="{lead}"><td class="rank" data-sort="{rank}">{medal or rank}</td>'
            f'<td class="vname">{_esc(s.variant_id)}{crown}</td>'
            f'<td class="num" data-label="n" data-sort="{s.n_scored}">{s.n_scored}</td>'
            f'<td class="num strong" data-label="RPS" data-sort="{s.mean_rps if s.mean_rps is not None else 9}">{_fmt(s.mean_rps)}</td>'
            f'<td class="num" data-label="log loss" data-sort="{s.mean_log_loss if s.mean_log_loss is not None else 9}">{_fmt(s.mean_log_loss)}</td>'
            f'<td class="num" data-label="Brier" data-sort="{s.mean_brier if s.mean_brier is not None else 9}">{_fmt(s.mean_brier)}</td>'
            f'<td class="num" data-label="dec.acc" data-sort="{s.decisive_accuracy if s.decisive_accuracy is not None else -1}">{_fmt(s.decisive_accuracy, 2)}</td>'
            f'<td class="edge" data-label="edge" data-sort="{edge if (edge is not None and s.n_scored) else -9}">{edge_cell}</td></tr>'
        )

    # ---- Walk-forward backtest section (from cache) ----
    backtest_section = ""
    bt = load_backtest_cache()
    if bt and bt.get("standings"):
        bt_standings = bt["standings"]
        max_bt_edge = max(
            [abs(s["edge_vs_baseline_rps"]) for s in bt_standings if s.get("edge_vs_baseline_rps")],
            default=0.0,
        ) or 1.0
        bt_rows = []
        for rank, s in enumerate(bt_standings, start=1):
            edge = s.get("edge_vs_baseline_rps")
            if edge is None:
                edge_cell = '<span class="muted">—</span>'
            else:
                width = abs(edge) / max_bt_edge * 100.0
                side = "pos" if edge > 0 else ("neg" if edge < 0 else "zero")
                edge_cell = (
                    f'<div class="edgewrap"><div class="edgebar {side}" style="width:{width:.1f}%"></div>'
                    f'<span class="edgeval">{edge:+.4f}</span></div>'
                )
            is_base = s["variant_id"] == BASELINE_VARIANT
            crown = ' <span class="tag">baseline</span>' if is_base else ""
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "")
            bt_rows.append(
                f'<tr><td class="rank" data-sort="{rank}">{medal or rank}</td>'
                f'<td class="vname">{_esc(s["variant_id"])}{crown}</td>'
                f'<td class="num" data-label="n" data-sort="{s["n_scored"]}">{s["n_scored"]}</td>'
                f'<td class="num strong" data-label="RPS" data-sort="{s["mean_rps"] if s["mean_rps"] is not None else 9}">{_fmt(s["mean_rps"])}</td>'
                f'<td class="num" data-label="log loss" data-sort="{s["mean_log_loss"] if s["mean_log_loss"] is not None else 9}">{_fmt(s["mean_log_loss"])}</td>'
                f'<td class="num" data-label="Brier" data-sort="{s["mean_brier"] if s["mean_brier"] is not None else 9}">{_fmt(s["mean_brier"])}</td>'
                f'<td class="num" data-label="accuracy" data-sort="{s["decisive_accuracy"] if s["decisive_accuracy"] is not None else -1}">{_fmt(s["decisive_accuracy"], 3)}</td>'
                f'<td class="edge" data-label="edge" data-sort="{edge if edge is not None else -9}">{edge_cell}</td></tr>'
            )
        rng = bt.get("date_range")
        sub = f'{bt["n_matches"]} matches' + (f' · {rng[0]} → {rng[1]}' if rng else "")
        backtest_section = (
            f'<details class="sec"><summary>Walk-forward backtest <span class="h2sub">· {sub}</span></summary>'
            '<div class="secbody">'
            '<table class="lb sortable"><thead><tr><th>#</th><th>variant</th><th class="num">n</th>'
            '<th class="num">RPS</th><th class="num">log loss</th><th class="num">Brier</th>'
            '<th class="num">accuracy</th><th>edge vs baseline</th></tr></thead>'
            f'<tbody>{"".join(bt_rows)}</tbody></table>'
            '<div class="note">Leak-free: every model is re-trained on results strictly before each '
            'match and scored on the actual outcome — a far larger sample than the live recorded '
            'forecasts above. This is the honest read; the live table is still tiny.</div>'
            '</div></details>'
        )

    # ---- Results cards (chronological by match date) ----
    result_cards = []
    scored_by_date = sorted(
        scored_match_ids,
        key=lambda m: (_fixture_day(fixture_info.get(m, {})), m),
    )
    for mid in scored_by_date:
        fx = fixture_info.get(mid, {})
        home = names.get(str(fx.get("home_team_id")), str(fx.get("home_team_id")))
        away = names.get(str(fx.get("away_team_id")), str(fx.get("away_team_id")))
        hs, a = results[mid]
        actual = _outcome(hs, a)
        match_day = _fixture_day(fx)
        rows = []
        for vid in variant_ids:
            probs = pred_lookup.get((vid, mid))
            if probs is None:
                continue
            pick = _pick(probs)
            hit = pick == actual
            total = sum(probs) or 1.0
            rps = ranked_probability_score([p / total for p in probs], actual)
            badge = '<span class="hit">✓</span>' if hit else '<span class="miss">✗</span>'
            rows.append(
                f'<tr><td class="vn">{_esc(vid)}</td><td class="barcell">{_bar(probs, actual)}</td>'
                f'<td class="pk">{badge} {pick.upper()}</td><td>{_upset_cell(probs)}</td>'
                f'<td class="num">{rps:.3f}</td></tr>'
            )
        result_cards.append(
            f'<div class="card"><div class="score"><span class="t">{_esc(home)}</span>'
            f'<span class="sc">{hs}–{a}</span><span class="t">{_esc(away)}</span></div>'
            f'<div class="resline">{f"<span class=\"dt\">{_esc(match_day)}</span> · " if match_day else ""}result: <b>{actual.upper()}</b></div>'
            f'<table class="mini"><thead><tr><th>variant</th><th>H / D / A</th><th>pick</th><th>upset risk</th><th>RPS</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        )

    # ---- Upcoming (interactive by-model view) ----
    def _fixture_date(mid: str) -> str:
        fx = fixture_info.get(mid, {})
        try:
            return pd.to_datetime(fx.get("match_date")).strftime("%Y-%m-%d")
        except Exception:
            return ""

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    upcoming_sorted = _select_upcoming_match_ids(
        upcoming_match_ids, fixture_date=_fixture_date, today=today_utc, limit=60
    )
    # One record per upcoming match carrying *every* model's prediction, so the
    # browser can re-render the table by model / consensus and sort it client-side.
    upcoming_payload = []
    for mid in upcoming_sorted:
        picks = {
            vid: [round(p, 6) for p in pred_lookup[(vid, mid)]]
            for vid in variant_ids
            if pred_lookup.get((vid, mid)) is not None
        }
        if not picks:
            continue
        fx = fixture_info.get(mid, {})
        home = names.get(str(fx.get("home_team_id")), str(fx.get("home_team_id")))
        away = names.get(str(fx.get("away_team_id")), str(fx.get("away_team_id")))
        upcoming_payload.append(
            {
                "id": mid,
                "date": _fixture_date(mid),
                "home": home,
                "away": away,
                "picks": picks,
            }
        )

    # Models actually present in the upcoming slate, leader/standings order preserved.
    upcoming_models = [
        vid for vid in variant_ids if any(vid in m["picks"] for m in upcoming_payload)
    ]
    default_model = (
        PREFERRED_FORECAST_VARIANT
        if PREFERRED_FORECAST_VARIANT in upcoming_models
        else (BASELINE_VARIANT if BASELINE_VARIANT in upcoming_models else "__consensus__")
    )
    upcoming_json = json.dumps(
        {
            "matches": upcoming_payload,
            "models": upcoming_models,
            "default": default_model,
            "baseline": BASELINE_VARIANT,
            "leader": leader.variant_id if leader else None,
        },
        separators=(",", ":"),
    )

    html_doc = _TEMPLATE.format(
        generated=generated,
        days=len(days),
        n_scored=n_scored,
        accuracy=(f"{accuracy:.0f}%" if accuracy is not None else "—"),
        n_variants=len(standings),
        leader=(_esc(leader.variant_id) if leader else "—"),
        leader_rps=(_fmt(leader.mean_rps) if leader else "—"),
        accuracy_section=accuracy_section,
        lb_rows="".join(lb_rows),
        backtest_section=backtest_section,
        result_cards=("".join(result_cards) or '<p class="muted">No matches scored yet.</p>'),
        n_upcoming=len(upcoming_payload),
        upcoming_json=upcoming_json,
        betting_section=_betting_section(),
        script=_SCRIPT,
    )

    return _write_dashboard_outputs(
        html_doc,
        out_path=out_path,
        publish_pages=publish_pages,
        pages_path=pages_path,
    )


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Cup Model-Research Lab</title>
<style>
:root{{--bg:#0d1117;--panel:#161b22;--line:#21262d;--ink:#e6edf3;--mut:#8b949e;
--h:#3b82f6;--d:#a1a1aa;--a:#f97316;--pos:#22c55e;--neg:#ef4444;--gold:#f5c518;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:24px;margin:0 0 2px}} .sub{{color:var(--mut);font-size:13px;margin-bottom:22px}}
h2{{font-size:16px;margin:30px 0 12px;border-bottom:1px solid var(--line);padding-bottom:8px}}
.h2sub{{color:var(--mut);font-size:12px;font-weight:400}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:6px}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.stat .v{{font-size:26px;font-weight:700}} .stat .k{{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse}}
.lb{{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.lb th,.lb td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line)}}
.lb th{{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}}
.lb tr:last-child td{{border-bottom:none}}
.lb tr.lead{{background:rgba(245,197,24,.07)}}
.num{{text-align:right;font-variant-numeric:tabular-nums}} .strong{{font-weight:700}}
.rank{{width:34px;font-size:17px}} .vname{{font-weight:600}}
.tag{{font-size:10px;background:#30363d;color:var(--mut);padding:2px 6px;border-radius:4px;margin-left:6px;text-transform:uppercase}}
.edge{{width:180px}} .edgewrap{{position:relative;display:flex;align-items:center;justify-content:flex-end;gap:8px}}
.edgebar{{height:8px;border-radius:4px}} .edgebar.pos{{background:var(--pos)}} .edgebar.neg{{background:var(--neg)}} .edgebar.zero{{background:#30363d}}
.edgeval{{font-variant-numeric:tabular-nums;font-size:13px;min-width:60px;text-align:right}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:14px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.score{{display:flex;align-items:center;justify-content:space-between;gap:8px;font-weight:600}}
.score .t{{flex:1}} .score .t:last-child{{text-align:right}} .score .sc{{font-size:20px;font-weight:800;background:#21262d;padding:2px 10px;border-radius:6px}}
.resline{{color:var(--mut);font-size:12px;margin:6px 0 10px}}
.mini{{font-size:11px;table-layout:fixed}} .mini th{{color:var(--mut);font-weight:500;text-align:left;padding:4px 5px;font-size:9px;text-transform:uppercase}}
.mini td{{padding:4px 5px;border-top:1px solid var(--line);vertical-align:middle}} .mini .vn{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.mini th:nth-child(1),.mini td:nth-child(1){{width:24%}}
.mini th:nth-child(2),.mini td:nth-child(2){{width:39%}}
.mini th:nth-child(3),.mini td:nth-child(3){{width:14%}}
.mini th:nth-child(4),.mini td:nth-child(4){{width:15%}}
.mini th:nth-child(5),.mini td:nth-child(5){{width:8%}}
.bar{{display:flex;height:18px;border-radius:4px;overflow:hidden;background:#0b0f14;min-width:0}}
.seg{{display:flex;align-items:center;justify-content:center;font-size:10px;color:#0b0f14;font-weight:700;overflow:hidden}}
.seg-h{{background:var(--h)}} .seg-d{{background:var(--d)}} .seg-a{{background:var(--a)}}
.seg-actual{{outline:2px solid #fff;outline-offset:-2px}}
.barcell{{width:auto}} .pk{{white-space:nowrap;font-size:10px}} .hit{{color:var(--pos);font-weight:800}} .miss{{color:var(--neg);font-weight:800}}
.probwrap{{display:flex;flex-direction:column;gap:4px;min-width:190px}}
.probwrap .bar{{height:18px}}
.problabels{{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;font-weight:800;letter-spacing:.02em;line-height:1}}
.plabel{{white-space:nowrap;font-variant-numeric:tabular-nums}}
.plabel-h{{color:var(--h)}} .plabel-d{{color:var(--d)}} .plabel-a{{color:var(--a)}}
.risk{{display:inline-block;white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:700;border-radius:999px;padding:1px 5px;background:#30363d;color:var(--ink);font-size:10px}}
.risk-low{{color:var(--pos)}} .risk-medium{{color:var(--gold)}} .risk-high{{color:var(--neg)}}
.accuracy-card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.accsummary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:6px}}
.bigacc{{font-size:34px;font-weight:800;line-height:1;margin-bottom:4px;color:var(--pos)}}
.bigacc.decisive{{color:var(--gold)}}
.metriclabel{{color:var(--mut);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}}
.timeline{{margin-top:12px;font-size:12px}}
.timeline th,.timeline td{{padding:7px 8px;border-top:1px solid var(--line);text-align:left}}
.timeline th{{font-size:10px;text-transform:uppercase;color:var(--mut);letter-spacing:.04em}}
.accbarcell{{width:42%}}
.accbar{{height:18px;background:#0b0f14;border-radius:999px;position:relative;overflow:hidden}}
.accfill{{height:100%;background:linear-gradient(90deg,var(--h),var(--pos));border-radius:999px}}
.accfill.decisive{{background:linear-gradient(90deg,var(--gold),var(--pos))}}
.accbar span{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:var(--ink);text-shadow:0 1px 2px #000}}
.up{{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.up th,.up td{{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left}} .up tr:last-child td{{border-bottom:none}}
.up th{{font-size:11px;text-transform:uppercase;color:var(--mut)}} .dt{{color:var(--mut);font-variant-numeric:tabular-nums;white-space:nowrap}} .vs{{color:var(--mut)}}
.legend{{display:flex;gap:16px;color:var(--mut);font-size:12px;margin:10px 2px}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
.muted{{color:var(--mut)}} .note{{color:var(--mut);font-size:12px;margin-top:8px}}
/* collapsible sections */
details.sec{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:14px 0;overflow:hidden}}
details.sec>summary{{list-style:none;cursor:pointer;padding:13px 16px;font-size:16px;font-weight:600;display:flex;align-items:center;gap:8px;user-select:none}}
details.sec>summary::-webkit-details-marker{{display:none}}
details.sec>summary::before{{content:"\\25B8";color:var(--mut);font-size:13px;transition:transform .15s}}
details.sec[open]>summary::before{{transform:rotate(90deg)}}
details.sec>summary:hover{{background:rgba(255,255,255,.02)}}
.secbody{{padding:2px 16px 16px}}
.subh{{font-size:13px;margin:16px 0 8px;color:var(--ink);font-weight:700}}
.controls{{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:4px 0 14px}}
.controls label{{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em;display:flex;align-items:center;gap:6px}}
.controls select{{background:#0b0f14;color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:13px;text-transform:none;letter-spacing:0}}
.ghostbtn{{background:#0b0f14;color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 11px;font-size:12px;cursor:pointer}}
.ghostbtn:hover{{border-color:var(--mut)}}
/* sortable headers */
.sortable th{{cursor:pointer;user-select:none;white-space:nowrap}}
.sortable th:hover{{color:var(--ink)}}
.sortable th.sorted-asc::after{{content:" \\25B2";color:var(--mut);font-size:9px}}
.sortable th.sorted-desc::after{{content:" \\25BC";color:var(--mut);font-size:9px}}
/* upcoming by-model */
.umatch{{border:1px solid var(--line);border-radius:9px;margin-bottom:8px;background:#0b0f14}}
.urow{{display:grid;grid-template-columns:84px 1fr 210px 92px 24px;gap:12px;align-items:center;padding:10px 12px;cursor:pointer}}
.urow:hover{{background:rgba(255,255,255,.025)}}
.umeta{{min-width:0}} .umeta .mt{{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.umeta .uspread{{font-size:11px;color:var(--mut)}}
.uchev{{color:var(--mut);text-align:center;transition:transform .15s}}
.umatch.open .uchev{{transform:rotate(90deg)}}
.umodels{{display:none;border-top:1px solid var(--line);padding:6px 12px 10px}}
.umatch.open .umodels{{display:block}}
.umodels table{{font-size:11px;table-layout:fixed}}
.umodels th{{color:var(--mut);font-weight:500;text-align:left;padding:3px 6px;font-size:9px;text-transform:uppercase}}
.umodels td{{padding:3px 6px;border-top:1px solid var(--line);vertical-align:middle}}
.umodels tr.sel td{{background:rgba(245,197,24,.07)}}
.umodels .vn{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.umodels th:nth-child(1),.umodels td:nth-child(1){{width:30%}}
.umodels th:nth-child(2),.umodels td:nth-child(2){{width:50%}}
.umodels th:nth-child(3),.umodels td:nth-child(3){{width:20%}}
.uempty{{color:var(--mut);padding:12px 2px}}
@media (max-width:640px){{
  .urow{{grid-template-columns:1fr 64px 22px;row-gap:6px}}
  .urow .barcell{{grid-column:1 / -1}}
  .controls{{gap:8px}} .controls label{{flex:1}}
  .wrap{{padding:18px 12px 48px}}
  h1{{font-size:20px}}
  .cards{{grid-template-columns:1fr 1fr;gap:8px}}
  .stat{{padding:10px 12px}} .stat .v{{font-size:20px;overflow-wrap:anywhere}}
  .grid{{grid-template-columns:1fr}}
  /* leaderboard table -> stacked cards */
  .lb thead{{display:none}}
  .lb,.lb tbody,.lb tr,.lb td{{display:block;width:100%}}
  .lb tr{{border:1px solid var(--line);border-radius:10px;margin-bottom:10px;padding:10px 14px 8px;position:relative}}
  .lb tr.lead{{background:rgba(245,197,24,.08)}}
  .lb td{{border:none;padding:5px 0;display:flex;justify-content:space-between;align-items:center;text-align:right}}
  .lb td.rank{{position:absolute;top:10px;right:12px;width:auto;padding:0;font-size:15px}}
  .lb td.vname{{font-size:17px;justify-content:flex-start;padding-right:36px;border-bottom:1px solid var(--line);margin-bottom:4px;padding-bottom:6px}}
  .lb td[data-label]::before{{content:attr(data-label);color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
  .lb td.edge{{width:100%}} .edgewrap{{flex:1;justify-content:flex-end}} .edgebar{{max-width:110px}}
  /* upcoming table -> stacked */
  .up thead{{display:none}}
  .up,.up tbody,.up tr,.up td{{display:block;width:100%}}
  .up tr{{padding:10px 2px}} .up td{{border:none;padding:2px 0}}
  .up .mt{{font-weight:600}} .up .barcell{{margin-top:6px}}
  /* result mini-tables */
  .mini{{font-size:10px}} .barcell{{width:auto}} .bar{{min-width:0}}
  .legend{{flex-wrap:wrap;gap:6px 14px}}
}}
</style></head><body><div class="wrap">
<h1>⚽ World Cup Model-Research Lab</h1>
<div class="sub">Claude-orchestrates-Codex daily bake-off · generated {generated}</div>

<div class="cards">
<div class="stat"><div class="v">{days}</div><div class="k">Days run</div></div>
<div class="stat"><div class="v">{n_scored}</div><div class="k">Matches scored</div></div>
<div class="stat"><div class="v">{accuracy}</div><div class="k">Outcome accuracy</div></div>
<div class="stat"><div class="v">{n_variants}</div><div class="k">Models</div></div>
<div class="stat"><div class="v">{leader}</div><div class="k">Leader · RPS {leader_rps}</div></div>
</div>

<details class="sec" open><summary>Upcoming forecasts — by model <span class="h2sub">· {n_upcoming} fixtures · pick a model, sort, or expand a match for all models</span></summary>
<div class="secbody">
<div class="controls">
<label>Model <select id="upModel"></select></label>
<label>Sort <select id="upSort">
<option value="date">Date (soonest)</option>
<option value="home">Home win %</option>
<option value="away">Away win %</option>
<option value="draw">Draw %</option>
<option value="upset">Upset risk</option>
<option value="spread">Model disagreement</option>
</select></label>
<button type="button" id="upExpandAll" class="ghostbtn">Expand all</button>
</div>
<div id="upcoming"></div>
<noscript><p class="muted">Enable JavaScript to browse per-model forecasts.</p></noscript>
<div class="note">Each row shows the selected model's H/D/A. <b>Consensus</b> averages every model. <b>Model disagreement</b> ranks matches by how much the models differ on the home-win probability — the fixtures worth a closer look. Expand a match to see every model side by side.</div>
</div></details>

{betting_section}

{accuracy_section}

<details class="sec" open><summary>Leaderboard <span class="h2sub">· live recorded forecasts · click a column to sort</span></summary>
<div class="secbody">
<table class="lb sortable"><thead><tr><th>#</th><th>variant</th><th class="num">n</th><th class="num">RPS</th>
<th class="num">log loss</th><th class="num">Brier</th><th class="num">dec.acc</th><th>edge vs baseline</th></tr></thead>
<tbody>{lb_rows}</tbody></table>
<div class="note">Lower RPS / log loss / Brier is better. Edge = baseline RPS − variant RPS (green = beats baseline). Small n — read as direction, not verdict.</div>
</div></details>

{backtest_section}

<details class="sec"><summary>Results <span class="h2sub">· scored matches, every model</span></summary>
<div class="secbody">
<div class="legend"><span><span class="dot" style="background:var(--h)"></span>Home win</span>
<span><span class="dot" style="background:var(--d)"></span>Draw</span>
<span><span class="dot" style="background:var(--a)"></span>Away win</span>
<span>white outline = actual outcome · ✓ called it</span></div>
<div class="grid">{result_cards}</div>
</div></details>

</div>
<script>
window.__UPCOMING__ = {upcoming_json};
</script>
<script>
{script}
</script>
</body></html>"""


_SCRIPT = r"""
(function () {
  "use strict";

  // ---- generic click-to-sort for any table.sortable ----
  function cellValue(row, i) {
    var c = row.cells[i];
    if (!c) return "";
    var d = c.getAttribute("data-sort");
    return d !== null ? d : c.textContent.trim();
  }
  function sortTable(table, col, dir) {
    var tb = table.tBodies[0];
    var rows = Array.prototype.slice.call(tb.rows);
    rows.sort(function (a, b) {
      var x = cellValue(a, col), y = cellValue(b, col);
      var nx = parseFloat(x), ny = parseFloat(y);
      var numeric = !isNaN(nx) && !isNaN(ny) && /[0-9]/.test(x) && /[0-9]/.test(y);
      var cmp = numeric ? (nx - ny) : x.toLowerCase().localeCompare(y.toLowerCase());
      return dir === "asc" ? cmp : -cmp;
    });
    rows.forEach(function (r) { tb.appendChild(r); });
  }
  function makeSortable(table) {
    var ths = table.tHead.rows[0].cells;
    Array.prototype.forEach.call(ths, function (th, i) {
      th.addEventListener("click", function () {
        var asc = !th.classList.contains("sorted-asc");
        Array.prototype.forEach.call(ths, function (o) {
          o.classList.remove("sorted-asc", "sorted-desc");
        });
        th.classList.add(asc ? "sorted-asc" : "sorted-desc");
        sortTable(table, i, asc ? "asc" : "desc");
      });
    });
  }
  document.querySelectorAll("table.sortable").forEach(makeSortable);

  // ---- interactive by-model upcoming forecasts ----
  var DATA = window.__UPCOMING__ || { matches: [], models: [], default: "__consensus__" };
  var host = document.getElementById("upcoming");
  var modelSel = document.getElementById("upModel");
  var sortSel = document.getElementById("upSort");
  var expandAllBtn = document.getElementById("upExpandAll");
  if (!host || !modelSel) return;

  var CONSENSUS = "__consensus__";
  var open = {};        // match id -> expanded?
  var allOpen = false;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function consensus(picks) {
    var v = Object.keys(picks).map(function (k) { return picks[k]; });
    var n = v.length || 1, s = [0, 0, 0];
    v.forEach(function (p) { s[0] += p[0]; s[1] += p[1]; s[2] += p[2]; });
    return [s[0] / n, s[1] / n, s[2] / n];
  }
  function spread(picks) {
    var hs = Object.keys(picks).map(function (k) { return picks[k][0]; });
    var n = hs.length || 1;
    var m = hs.reduce(function (a, b) { return a + b; }, 0) / n;
    var va = hs.reduce(function (a, b) { return a + (b - m) * (b - m); }, 0) / n;
    return Math.sqrt(va);
  }
  function displayProbs(m, model) {
    if (model === CONSENSUS) return consensus(m.picks);
    return m.picks[model] || null;
  }
  function upset(p) {
    var t = p[0] + p[1] + p[2] || 1, h = p[0] / t, d = p[1] / t, a = p[2] / t;
    var avoid = h >= a ? d + a : d + h;
    var pct = Math.max(0, Math.min(100, avoid * 100));
    var label = pct < 30 ? "Low" : pct < 45 ? "Medium" : "High";
    return { pct: pct, label: label };
  }
  function upsetCell(p) {
    var u = upset(p);
    return '<span class="risk risk-' + u.label.toLowerCase() + '">' +
      Math.round(u.pct) + "% " + u.label + "</span>";
  }
  function bar(p) {
    var labs = ["H", "D", "A"], cls = ["h", "d", "a"], labels = "", segs = "";
    for (var i = 0; i < 3; i++) {
      var pct = p[i] * 100;
      labels += '<span class="plabel plabel-' + cls[i] + '">' + labs[i] + " " + Math.round(pct) + "</span>";
      segs += '<div class="seg seg-' + cls[i] + '" style="width:' + pct.toFixed(3) +
        '%" title="' + labs[i] + " " + pct.toFixed(1) + '%"></div>';
    }
    return '<div class="probwrap"><div class="problabels">' + labels +
      '</div><div class="bar">' + segs + "</div></div>";
  }

  function populateModels() {
    var opts = '<option value="' + CONSENSUS + '">Consensus (all models)</option>';
    DATA.models.forEach(function (m) {
      var tag = m === DATA.leader ? " — leader" : (m === DATA.baseline ? " — baseline" : "");
      opts += '<option value="' + esc(m) + '">' + esc(m) + tag + "</option>";
    });
    modelSel.innerHTML = opts;
    modelSel.value = DATA.default || CONSENSUS;
  }

  function modelsTable(m, selected) {
    var rows = "";
    DATA.models.forEach(function (vid) {
      var p = m.picks[vid];
      if (!p) return;
      var sel = vid === selected ? ' class="sel"' : "";
      rows += "<tr" + sel + '><td class="vn">' + esc(vid) + "</td>" +
        '<td class="barcell">' + bar(p) + "</td>" +
        "<td>" + upsetCell(p) + "</td></tr>";
    });
    return '<table><thead><tr><th>model</th><th>H / D / A</th><th>upset risk</th></tr></thead><tbody>' +
      rows + "</tbody></table>";
  }

  function render() {
    var model = modelSel.value;
    var sort = sortSel.value;
    var list = DATA.matches.slice();
    var idx = { home: 0, draw: 1, away: 2 };

    list.sort(function (a, b) {
      if (sort === "date") return (a.date + a.id).localeCompare(b.date + b.id);
      if (sort === "spread") return spread(b.picks) - spread(a.picks);
      var pa = displayProbs(a, model), pb = displayProbs(b, model);
      if (!pa) return 1; if (!pb) return -1;
      if (sort === "upset") return upset(pb).pct - upset(pa).pct;
      return pb[idx[sort]] - pa[idx[sort]];
    });

    if (!list.length) {
      host.innerHTML = '<div class="uempty">No upcoming fixtures.</div>';
      return;
    }
    var out = "";
    list.forEach(function (m) {
      var p = displayProbs(m, model);
      var isOpen = open[m.id];
      var barCell = p ? bar(p) : '<span class="muted">no forecast for this model</span>';
      var upCell = p ? upsetCell(p) : "";
      var sp = (spread(m.picks) * 100).toFixed(1);
      out += '<div class="umatch' + (isOpen ? " open" : "") + '" data-id="' + esc(m.id) + '">' +
        '<div class="urow">' +
          '<span class="dt">' + esc(m.date) + "</span>" +
          '<span class="umeta"><div class="mt">' + esc(m.home) + ' <span class="vs">v</span> ' +
            esc(m.away) + '</div><div class="uspread">disagreement ' + sp + " pts</div></span>" +
          '<span class="barcell">' + barCell + "</span>" +
          "<span>" + upCell + "</span>" +
          '<span class="uchev">▸</span>' +
        "</div>" +
        '<div class="umodels">' + modelsTable(m, model) + "</div>" +
        "</div>";
    });
    host.innerHTML = out;

    host.querySelectorAll(".urow").forEach(function (row) {
      row.addEventListener("click", function () {
        var card = row.parentNode, id = card.getAttribute("data-id");
        open[id] = !open[id];
        card.classList.toggle("open", open[id]);
      });
    });
  }

  populateModels();
  render();
  modelSel.addEventListener("change", render);
  sortSel.addEventListener("change", render);
  if (expandAllBtn) {
    expandAllBtn.addEventListener("click", function () {
      allOpen = !allOpen;
      DATA.matches.forEach(function (m) { open[m.id] = allOpen; });
      expandAllBtn.textContent = allOpen ? "Collapse all" : "Expand all";
      render();
    });
  }
})();
"""


def main() -> None:
    path = build_dashboard()
    print(f"[dashboard] wrote {path}")


if __name__ == "__main__":
    main()
