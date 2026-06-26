"""Render a self-contained HTML dashboard for the daily model-research lab.

Reads the live experiment ledger + results + leaderboard and emits a single
offline HTML file (inline CSS, no external assets) at research/dashboard.html.
Regenerate any time; it reflects whatever has been scored so far.
"""

from __future__ import annotations

import html
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
    return f"{value * 100.0:.0f}%" if value is not None else "â€”"


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
        bucket = by_day.setdefault(day, {"n": 0, "hits": 0})
        bucket["n"] += 1
        bucket["hits"] += int(_pick(probs) == actual)

    rows: list[dict] = []
    cumulative_n = 0
    cumulative_hits = 0
    for day in sorted(by_day):
        n = by_day[day]["n"]
        hits = by_day[day]["hits"]
        cumulative_n += n
        cumulative_hits += hits
        rows.append(
            {
                "date": day,
                "n": n,
                "hits": hits,
                "daily_accuracy": hits / n if n else None,
                "cumulative_n": cumulative_n,
                "cumulative_hits": cumulative_hits,
                "cumulative_accuracy": cumulative_hits / cumulative_n
                if cumulative_n
                else None,
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
        body_rows.append(
            f'<tr><td class="dt">{_esc(row["date"])}</td>'
            f'<td class="num">{row["hits"]}/{row["n"]}</td>'
            f'<td class="num">{_pct(row["daily_accuracy"])}</td>'
            f'<td class="accbarcell"><div class="accbar"><div class="accfill" style="width:{width:.1f}%"></div>'
            f'<span>{_pct(cumulative)}</span></div></td>'
            f'<td class="num">{row["cumulative_hits"]}/{row["cumulative_n"]}</td></tr>'
        )

    return (
        f'<h2>Accuracy over time <span class="h2sub">Â· {_esc(variant_id)} cumulative outcome picks</span></h2>'
        '<div class="accuracy-card">'
        f'<div class="bigacc">{_pct(latest["cumulative_accuracy"])}</div>'
        f'<div class="note">Current cumulative accuracy: {latest["cumulative_hits"]}/{latest["cumulative_n"]} '
        'resolved picks. Daily accuracy shows only matches resolved on that date.</div>'
        '<table class="timeline"><thead><tr><th>date</th><th class="num">daily hits</th>'
        '<th class="num">daily acc</th><th>cumulative acc</th><th class="num">cum. hits</th></tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
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
            f'<tr class="{lead}"><td class="rank">{medal or rank}</td>'
            f'<td class="vname">{_esc(s.variant_id)}{crown}</td>'
            f'<td class="num" data-label="n">{s.n_scored}</td>'
            f'<td class="num strong" data-label="RPS">{_fmt(s.mean_rps)}</td>'
            f'<td class="num" data-label="log loss">{_fmt(s.mean_log_loss)}</td>'
            f'<td class="num" data-label="Brier">{_fmt(s.mean_brier)}</td>'
            f'<td class="num" data-label="dec.acc">{_fmt(s.decisive_accuracy, 2)}</td>'
            f'<td class="edge" data-label="edge">{edge_cell}</td></tr>'
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
                f'<tr><td class="rank">{medal or rank}</td>'
                f'<td class="vname">{_esc(s["variant_id"])}{crown}</td>'
                f'<td class="num" data-label="n">{s["n_scored"]}</td>'
                f'<td class="num strong" data-label="RPS">{_fmt(s["mean_rps"])}</td>'
                f'<td class="num" data-label="log loss">{_fmt(s["mean_log_loss"])}</td>'
                f'<td class="num" data-label="Brier">{_fmt(s["mean_brier"])}</td>'
                f'<td class="num" data-label="accuracy">{_fmt(s["decisive_accuracy"], 3)}</td>'
                f'<td class="edge" data-label="edge">{edge_cell}</td></tr>'
            )
        rng = bt.get("date_range")
        sub = f'{bt["n_matches"]} matches' + (f' · {rng[0]} → {rng[1]}' if rng else "")
        backtest_section = (
            f'<h2>Walk-forward backtest <span class="h2sub">· {sub}</span></h2>'
            '<table class="lb"><thead><tr><th>#</th><th>variant</th><th class="num">n</th>'
            '<th class="num">RPS</th><th class="num">log loss</th><th class="num">Brier</th>'
            '<th class="num">accuracy</th><th>edge vs baseline</th></tr></thead>'
            f'<tbody>{"".join(bt_rows)}</tbody></table>'
            '<div class="note">Leak-free: every model is re-trained on results strictly before each '
            'match and scored on the actual outcome — a far larger sample than the live recorded '
            'forecasts above. This is the honest read; the live table is still tiny.</div>'
        )

    # ---- Results cards ----
    result_cards = []
    for mid in scored_match_ids:
        fx = fixture_info.get(mid, {})
        home = names.get(str(fx.get("home_team_id")), str(fx.get("home_team_id")))
        away = names.get(str(fx.get("away_team_id")), str(fx.get("away_team_id")))
        hs, a = results[mid]
        actual = _outcome(hs, a)
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
            f'<div class="resline">result: <b>{actual.upper()}</b></div>'
            f'<table class="mini"><thead><tr><th>variant</th><th>H / D / A</th><th>pick</th><th>upset risk</th><th>RPS</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        )

    # ---- Upcoming (ensemble preferred, baseline fallback) ----
    def _fixture_date(mid: str) -> str:
        fx = fixture_info.get(mid, {})
        try:
            return pd.to_datetime(fx.get("match_date")).strftime("%Y-%m-%d")
        except Exception:
            return ""

    upcoming_sorted = sorted(upcoming_match_ids, key=lambda m: (_fixture_date(m), m))[:14]
    up_rows = []
    for mid in upcoming_sorted:
        preferred_variant = (
            PREFERRED_FORECAST_VARIANT
            if pred_lookup.get((PREFERRED_FORECAST_VARIANT, mid)) is not None
            else BASELINE_VARIANT
        )
        probs = pred_lookup.get((preferred_variant, mid)) or pred_lookup.get((variant_ids[0], mid))
        if probs is None:
            continue
        fx = fixture_info.get(mid, {})
        home = names.get(str(fx.get("home_team_id")), str(fx.get("home_team_id")))
        away = names.get(str(fx.get("away_team_id")), str(fx.get("away_team_id")))
        up_rows.append(
            f'<tr><td class="dt">{_fixture_date(mid)}</td>'
            f'<td class="mt">{_esc(home)} <span class="vs">v</span> {_esc(away)}</td>'
            f'<td class="barcell">{_upcoming_bar(probs)}</td>'
            f'<td>{_upset_cell(probs)} <span class="muted">({_esc(preferred_variant)})</span></td></tr>'
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
        up_rows=("".join(up_rows) or '<tr><td colspan="4" class="muted">No upcoming fixtures.</td></tr>'),
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
.bigacc{{font-size:34px;font-weight:800;line-height:1;margin-bottom:4px;color:var(--pos)}}
.timeline{{margin-top:12px;font-size:12px}}
.timeline th,.timeline td{{padding:7px 8px;border-top:1px solid var(--line);text-align:left}}
.timeline th{{font-size:10px;text-transform:uppercase;color:var(--mut);letter-spacing:.04em}}
.accbarcell{{width:42%}}
.accbar{{height:18px;background:#0b0f14;border-radius:999px;position:relative;overflow:hidden}}
.accfill{{height:100%;background:linear-gradient(90deg,var(--h),var(--pos));border-radius:999px}}
.accbar span{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:var(--ink);text-shadow:0 1px 2px #000}}
.up{{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.up th,.up td{{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left}} .up tr:last-child td{{border-bottom:none}}
.up th{{font-size:11px;text-transform:uppercase;color:var(--mut)}} .dt{{color:var(--mut);font-variant-numeric:tabular-nums;white-space:nowrap}} .vs{{color:var(--mut)}}
.legend{{display:flex;gap:16px;color:var(--mut);font-size:12px;margin:10px 2px}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
.muted{{color:var(--mut)}} .note{{color:var(--mut);font-size:12px;margin-top:8px}}
@media (max-width:640px){{
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

{accuracy_section}

<h2>Leaderboard <span class="h2sub">· live recorded forecasts</span></h2>
<table class="lb"><thead><tr><th>#</th><th>variant</th><th class="num">n</th><th class="num">RPS</th>
<th class="num">log loss</th><th class="num">Brier</th><th class="num">dec.acc</th><th>edge vs baseline</th></tr></thead>
<tbody>{lb_rows}</tbody></table>
<div class="note">Lower RPS / log loss / Brier is better. Edge = baseline RPS − variant RPS (green = beats baseline). Small n — read as direction, not verdict.</div>

{backtest_section}

<h2>Results</h2>
<div class="legend"><span><span class="dot" style="background:var(--h)"></span>Home win</span>
<span><span class="dot" style="background:var(--d)"></span>Draw</span>
<span><span class="dot" style="background:var(--a)"></span>Away win</span>
<span>white outline = actual outcome · ✓ called it</span></div>
<div class="grid">{result_cards}</div>

<h2>Upcoming forecasts <span class="h2sub">Â· ensemble preferred, baseline fallback</span></h2>
<table class="up"><thead><tr><th>date</th><th>match</th><th>H / D / A</th><th>upset risk</th></tr></thead>
<tbody>{up_rows}</tbody></table>

</div></body></html>"""


def main() -> None:
    path = build_dashboard()
    print(f"[dashboard] wrote {path}")


if __name__ == "__main__":
    main()
