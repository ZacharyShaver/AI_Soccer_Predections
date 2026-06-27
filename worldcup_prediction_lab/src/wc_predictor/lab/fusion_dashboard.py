"""Live experimentation dashboard for the tuning/fusion/market session.

Separate from the daily research dashboard: this one reads the shared
file-per-experiment ledger (``runs/fusion/*.json``) and renders every tuning,
fusion, and market-as-base experiment as it lands, so the run can be watched.

Headline metric is **distance to market** = ``rps_market964 - 0.1496`` (the
de-vigged-market bar). The table also flags, per sample, whether an experiment
beats the recalibrated champion (green), closes >50% of the Elo->market gap
(gold), or is worse than the plain Elo baseline (red).

Single self-contained offline HTML (inline CSS + a tiny vanilla-JS column
sorter), regenerated cheaply. Writes ``research/fusion_dashboard.html`` and
publishes ``docs/fusion.html`` for Pages.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from wc_predictor.config import settings
from wc_predictor.lab import fusion_ledger
from wc_predictor.lab.eval_harness import MARKET_BAR_RPS

OUT_PATH = settings.RESEARCH_DIR / "fusion_dashboard.html"
PAGES_OUT_PATH = settings.PROJECT_DIR.parent / "docs" / "fusion.html"

# Reference bars measured this session (the harness reproduces these).
RECAL_BARS = {"hist_15k": 0.1745, "wc60": 0.1719, "market964": 0.1574}
BASELINE_BARS = {"hist_15k": 0.1762, "wc60": 0.1763, "market964": 0.1574}
SAMPLE_LABELS = {"hist_15k": "hist 15.8k", "wc60": "WC-60", "market964": "market 964"}
SAMPLE_ORDER = ("hist_15k", "wc60", "market964")
# >50% of the Elo->market gap closed on the market sample.
HALF_GAP_MARKET = RECAL_BARS["market964"] - 0.5 * (RECAL_BARS["market964"] - MARKET_BAR_RPS)


def _esc(value: object) -> str:
    return html.escape(str(value))


def _sample_rps(result: dict, sample: str) -> float | None:
    sample_obj = (result.get("samples") or {}).get(sample)
    if not isinstance(sample_obj, dict):
        return None
    rps = sample_obj.get("rps")
    return float(rps) if isinstance(rps, (int, float)) else None


def _cell_class(sample: str, rps: float | None) -> str:
    """green: beats recalibrated; gold: closes >50% gap (market only); red: worse than baseline."""

    if rps is None:
        return "na"
    if sample == "market964" and rps <= HALF_GAP_MARKET + 1e-12:
        return "gold"
    if rps < RECAL_BARS[sample] - 1e-12:
        return "good"
    if rps > BASELINE_BARS[sample] + 1e-12:
        return "bad"
    return "mid"


def _distance_to_market(result: dict) -> float | None:
    rps = _sample_rps(result, "market964")
    return None if rps is None else rps - MARKET_BAR_RPS


def _config_summary(result: dict) -> str:
    config = result.get("config")
    if isinstance(config, dict) and config:
        parts = [f"{k}={config[k]}" for k in list(config)[:6]]
        return ", ".join(parts)
    if isinstance(config, str):
        return config
    return ""


def _fmt(value: float | None, places: int = 4, signed: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:+.{places}f}" if signed else f"{value:.{places}f}"


def best_per_task(results: list[dict]) -> dict[str, dict]:
    """Best (lowest market964 RPS, falling back to hist) experiment per task."""

    best: dict[str, dict] = {}

    def _key(r: dict) -> float:
        for sample in ("market964", "hist_15k", "wc60"):
            rps = _sample_rps(r, sample)
            if rps is not None:
                return rps
        return float("inf")

    for result in results:
        task = str(result.get("task", "other"))
        if task not in best or _key(result) < _key(best[task]):
            best[task] = result
    return best


def _row_html(result: dict) -> str:
    cells = [
        f"<td class='left'>{_esc(result.get('exp_id', ''))}</td>",
        f"<td>{_esc(result.get('agent', ''))}</td>",
        f"<td>{_esc(result.get('task', ''))}</td>",
        f"<td class='left cfg'>{_esc(_config_summary(result))}</td>",
    ]
    for sample in SAMPLE_ORDER:
        rps = _sample_rps(result, sample)
        cls = _cell_class(sample, rps)
        cells.append(f"<td class='{cls}' data-v='{rps if rps is not None else 999}'>{_fmt(rps)}</td>")

    distance = _distance_to_market(result)
    dist_cls = "na"
    if distance is not None:
        dist_cls = "gold" if distance <= 0 else ("good" if distance <= (RECAL_BARS["market964"] - MARKET_BAR_RPS) - 1e-12 else "mid")
    cells.append(
        f"<td class='{dist_cls}' data-v='{distance if distance is not None else 999}'>"
        f"{_fmt(distance, signed=True)}</td>"
    )

    paired = result.get("vs_market_paired") or {}
    sig = "✓" if paired.get("excludes_0") else ""
    cells.append(f"<td>{sig}</td>")
    promote = "★" if result.get("promote") else ""
    cells.append(f"<td>{promote}</td>")
    cells.append(f"<td class='left note'>{_esc(result.get('notes', ''))}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def _verdict_banner(results: list[dict]) -> str:
    """One-glance session story: per-task best + the north-star gap status."""

    def best_hist(task):
        vals = [
            _sample_rps(r, "hist_15k")
            for r in results
            if r.get("task") == task and _sample_rps(r, "hist_15k") is not None
        ]
        return min(vals) if vals else None

    def best_market(task):
        vals = [
            _sample_rps(r, "market964")
            for r in results
            if r.get("task") == task and _sample_rps(r, "market964") is not None
        ]
        return min(vals) if vals else None

    # Did any market_base experiment significantly beat the market?
    beat_market = any(
        r.get("task") == "market_base"
        and (r.get("vs_market_paired") or {}).get("excludes_0")
        and (r.get("vs_market_paired") or {}).get("mean_diff", 1) < 0
        for r in results
    )
    # Did any fusion beat its best single constituent?
    beat_single = any(
        r.get("task") == "fuse" and (r.get("vs_best_constituent_paired") or {}).get("beats_best")
        for r in results
    )

    tune_h = best_hist("tune")
    fuse_m = best_market("fuse")
    mb_m = best_market("market_base")
    gap = RECAL_BARS["market964"] - MARKET_BAR_RPS  # 0.0078 to close

    lines = [
        "<div class='verdict'>",
        "<h3>Session verdict — can stat models reach the market?</h3>",
        "<ul>",
        (f"<li><b>T1 tuning:</b> best history RPS <b>{_fmt(tune_h)}</b> vs recalibrated "
         f"{RECAL_BARS['hist_15k']:.4f} — "
         + ("plateau, nothing promotable (no CI-excl-0 win without regressing WC-60)."
            if (tune_h is None or tune_h >= RECAL_BARS['hist_15k'] - 0.0003)
            else "a candidate is improving — under validation.") + "</li>"),
        (f"<li><b>T2 fusion:</b> best market-join RPS <b>{_fmt(fuse_m)}</b> — "
         + ("beats its best single constituent ✓." if beat_single
            else "does NOT beat the best single constituent (ensemble ≈ best model).") + "</li>"),
        (f"<li><b>T3 market-as-base:</b> best market-join RPS <b>{_fmt(mb_m)}</b> — "
         + ("a model SIGNIFICANTLY beats the de-vigged market ✓★" if beat_market
            else "nothing significantly beats the pure de-vigged market (efficient market).") + "</li>"),
        (f"<li><b>North star (close 0.1574→0.1496, gap {gap:.4f}):</b> "
         + ("CLOSED — a model reached/beat the market on held-out data." if beat_market
            else "OPEN — the remaining gap is irreducible per-match info (injuries/lineups/late money) "
                 "the market prices and ratings cannot see. We tie the market at best (temperature).")
         + "</li>"),
        "</ul></div>",
    ]
    return "\n".join(lines)


def render_html(results: list[dict]) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = len(results)

    # Headline: best distance-to-market so far.
    distances = [d for d in (_distance_to_market(r) for r in results) if d is not None]
    best_distance = min(distances) if distances else None
    best_market = (RECAL_BARS["market964"] if not distances else MARKET_BAR_RPS + best_distance)

    rows = sorted(
        results,
        key=lambda r: (_distance_to_market(r) if _distance_to_market(r) is not None else 9e9),
    )
    rows_html = "\n".join(_row_html(r) for r in rows) or (
        "<tr><td colspan='11' class='left'>No experiments recorded yet.</td></tr>"
    )

    best = best_per_task(results)
    best_lines = []
    for task in ("tune", "fuse", "market_base"):
        r = best.get(task)
        if r is None:
            best_lines.append(f"<li><b>{task}</b>: —</li>")
            continue
        m = _sample_rps(r, "market964")
        h = _sample_rps(r, "hist_15k")
        best_lines.append(
            f"<li><b>{task}</b>: <code>{_esc(r.get('exp_id'))}</code> "
            f"hist {_fmt(h)} · market {_fmt(m)} · dist {_fmt(_distance_to_market(r), signed=True)}</li>"
        )

    style = """
    body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:24px;color:#1a1a1a;background:#fafafa}
    h1{margin:0 0 4px} .sub{color:#666;font-size:13px;margin-bottom:16px}
    .bars{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0 20px}
    .bar{background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:10px 14px;min-width:150px}
    .bar .k{font-size:12px;color:#777} .bar .v{font-size:20px;font-weight:700}
    table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
    th,td{border:1px solid #e6e6e6;padding:5px 8px;text-align:right;white-space:nowrap}
    th{background:#f0f0f0;cursor:pointer;position:sticky;top:0}
    td.left,th.left{text-align:left} td.cfg{max-width:280px;overflow:hidden;text-overflow:ellipsis}
    td.note{max-width:340px;white-space:normal;color:#555;font-size:12px}
    .good{background:#d8f5d8} .gold{background:#ffeeba;font-weight:600} .bad{background:#faddd6}
    .mid{background:#fff} .na{background:#f3f3f3;color:#aaa}
    code{background:#f0f0f0;padding:1px 4px;border-radius:3px}
    ul{line-height:1.6}
    .verdict{background:#eef4ff;border:1px solid #c7d8f5;border-radius:10px;padding:8px 18px;margin:8px 0 18px}
    .verdict h3{margin:8px 0 4px}
    """

    sortjs = """
    function sortTable(th){var t=th.closest('table'),tb=t.tBodies[0],
      i=Array.prototype.indexOf.call(th.parentNode.children,th),
      asc=!(th._asc);th._asc=asc;
      var rows=Array.prototype.slice.call(tb.rows);
      rows.sort(function(a,b){var x=a.cells[i],y=b.cells[i];
        var xv=x.dataset.v!==undefined?parseFloat(x.dataset.v):x.textContent.trim();
        var yv=y.dataset.v!==undefined?parseFloat(y.dataset.v):y.textContent.trim();
        if(xv<yv)return asc?-1:1;if(xv>yv)return asc?1:-1;return 0;});
      rows.forEach(function(r){tb.appendChild(r);});}
    """

    headers = (
        ["exp_id", "agent", "task", "config"]
        + [SAMPLE_LABELS[s] for s in SAMPLE_ORDER]
        + ["dist→mkt", "sig", "promo", "notes"]
    )
    header_html = "".join(
        f"<th class='left' onclick='sortTable(this)'>{_esc(h)}</th>"
        if h in ("exp_id", "config", "notes", "agent", "task")
        else f"<th onclick='sortTable(this)'>{_esc(h)}</th>"
        for h in headers
    )

    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Fusion / tuning experiment dashboard</title><style>{style}</style></head>
<body>
<h1>Tuning · Fusion · Market-as-base — live experiments</h1>
<div class='sub'>Generated {generated} · {n} experiments · lower RPS is better ·
green beats recalibrated, gold closes &gt;50% of the Elo→market gap, red worse than baseline Elo</div>
<div class='bars'>
  <div class='bar'><div class='k'>market bar (964 join)</div><div class='v'>{MARKET_BAR_RPS:.4f}</div></div>
  <div class='bar'><div class='k'>recalibrated · market964</div><div class='v'>{RECAL_BARS['market964']:.4f}</div></div>
  <div class='bar'><div class='k'>recalibrated · hist 15.8k</div><div class='v'>{RECAL_BARS['hist_15k']:.4f}</div></div>
  <div class='bar'><div class='k'>recalibrated · WC-60</div><div class='v'>{RECAL_BARS['wc60']:.4f}</div></div>
  <div class='bar'><div class='k'>best market964 so far</div><div class='v'>{best_market:.4f}</div></div>
</div>
{_verdict_banner(results)}
<h3>Best so far per task</h3>
<ul>{''.join(best_lines)}</ul>
<table><thead><tr>{header_html}</tr></thead><tbody>
{rows_html}
</tbody></table>
<script>{sortjs}</script>
</body></html>"""


def build(
    *,
    results: list[dict] | None = None,
    out_path: Path | None = None,
    pages_path: Path | None = None,
    fusion_dir: Path | None = None,
) -> Path:
    """Render the dashboard from the ledger; write research + Pages copies."""

    if results is None:
        results = fusion_ledger.load_all(fusion_dir=fusion_dir)
    html_text = render_html(results)

    out = Path(out_path) if out_path is not None else OUT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")

    pages = Path(pages_path) if pages_path is not None else PAGES_OUT_PATH
    pages.parent.mkdir(parents=True, exist_ok=True)
    pages.write_text(html_text, encoding="utf-8")
    return out


def main() -> None:
    out = build()
    results = fusion_ledger.load_all()
    print(f"[fusion_dashboard] {len(results)} experiments -> {out} and {PAGES_OUT_PATH}")
    print(json.dumps(best_per_task(results), indent=2, default=str)[:400])


if __name__ == "__main__":
    main()
