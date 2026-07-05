"""PROTOTYPE (throwaway) — generate 3 information-architecture redesigns of the
dashboard on one page, switchable via ?variant=A/B/C + a floating bottom bar.

Question being answered: "what are the right top-level BUCKETS for the dashboard?"
The three variants disagree about STRUCTURE, reusing the real rendered fragments
(standings / betting / analyst / leaderboard from data/live.json, upcoming from the
baked __UPCOMING__ JSON) so they butt against real density.

  A — Intent tabs        : top tab bar (Predict · Standings · Bet · Model Lab)
  B — Narrative funnel    : single prioritized scroll + sticky jump-nav (Now/Outlook/Record/Lab)
  C — Cockpit grid        : dense two-column panel grid, minimal scroll

Run:  uv run python runs/prototype_dashboard_gen.py
Out:  research/prototype_dashboard.html   (throwaway — delete once a winner is picked)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT.parent / "docs" / "index.html"
LIVE = ROOT.parent / "docs" / "data" / "live.json"
OUT = ROOT / "research" / "prototype_dashboard.html"


def _balanced(html: str, start_marker: str, tag: str) -> str:
    """Extract a balanced <tag>...</tag> block starting at start_marker."""
    i = html.find(start_marker)
    if i < 0:
        return ""
    depth = 0
    open_re = re.compile(rf"<{tag}\b", re.I)
    close = f"</{tag}>"
    j = i
    while j < len(html):
        no = open_re.search(html, j)
        nc = html.find(close, j)
        if nc < 0:
            break
        if no and no.start() < nc:
            depth += 1
            j = no.end()
        else:
            depth -= 1
            j = nc + len(close)
            if depth == 0:
                return html[i:j]
    return ""


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")
    live = json.loads(LIVE.read_text(encoding="utf-8"))

    css = (re.search(r"<style>(.*?)</style>", html, re.S) or [None, ""])[1]
    cards = _balanced(html, '<div class="cards">', "div")
    upcoming = _balanced(html, '<details class="sec" open><summary>Upcoming forecasts', "details")
    leaderboard = _balanced(html, '<details class="sec" open><summary>Leaderboard', "details")
    results = _balanced(html, '<details class="sec"><summary>Results', "details")
    backtest = _balanced(html, "<details", "details") if "Walk-forward" in html else ""

    sec = live.get("sections", {})
    standings = sec.get("sec-standings", "<p>standings</p>")
    betting = sec.get("sec-betting", "<p>betting</p>")
    analyst = sec.get("sec-analyst", "<p>analyst</p>")
    lb = leaderboard or (
        '<details class="sec" open><summary>Leaderboard</summary><div class="secbody">'
        f'<table class="lb"><tbody>{live.get("lb_rows","")}</tbody></table></div></details>'
    )
    gen = live.get("generated", "")

    extra_css = """
    /* prototype switcher + per-variant layout */
    .pbar{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:9999;
      display:flex;gap:10px;align-items:center;background:#000;border:1px solid var(--gold);
      border-radius:999px;padding:8px 14px;box-shadow:0 6px 24px rgba(0,0,0,.6)}
    .pbar button{background:var(--gold);color:#000;border:0;border-radius:50%;width:28px;height:28px;
      font-size:16px;cursor:pointer;font-weight:700}
    .pbar .lbl{color:var(--ink);font-size:13px;min-width:230px;text-align:center;font-weight:600}
    .ptag{position:fixed;top:8px;right:10px;z-index:9999;background:#000;border:1px solid var(--neg);
      color:var(--neg);font-size:11px;padding:2px 8px;border-radius:6px}
    .variant{display:none} .variant.on{display:block}
    /* A: tabs */
    .tabs{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 18px}
    .tabs button{background:var(--panel);color:var(--mut);border:1px solid var(--line);
      border-radius:10px;padding:9px 16px;font-size:14px;cursor:pointer}
    .tabs button.sel{color:var(--ink);border-color:var(--h);background:#11203b}
    .pane{display:none} .pane.on{display:block}
    /* B: sticky jump nav + hero */
    .hero{background:linear-gradient(135deg,#11203b,#161b22);border:1px solid var(--line);
      border-radius:14px;padding:22px 24px;margin-bottom:8px}
    .hero h2{margin:.2em 0;font-size:22px} .hero .big{font-size:13px;color:var(--mut)}
    .jump{position:sticky;top:0;background:rgba(13,17,23,.92);backdrop-filter:blur(6px);
      z-index:50;display:flex;gap:8px;padding:10px 0;border-bottom:1px solid var(--line);margin-bottom:6px}
    .jump a{color:var(--mut);text-decoration:none;font-size:13px;padding:4px 10px;border-radius:8px}
    .jump a:hover{color:var(--ink);background:var(--panel)}
    .bucket{margin:18px 0} .bucket>h2{font-size:15px;color:var(--gold);border-bottom:1px solid var(--line);padding-bottom:6px}
    /* C: cockpit grid */
    .cockpit{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
    .cockpit .full{grid-column:1 / -1}
    .panelhead{font-size:13px;color:var(--gold);text-transform:uppercase;letter-spacing:.04em;margin:6px 0}
    @media(max-width:820px){.cockpit{grid-template-columns:1fr}}
    """

    def section(title, body):
        return f'<div class="bucket"><h2>{title}</h2>{body}</div>'

    upcoming_ph = upcoming or '<details class="sec" open><summary>Upcoming forecasts — by model</summary><div class="secbody"><p class="muted">[interactive upcoming-by-model widget mounts here]</p></div></details>'

    # ---- Variant A: intent tabs ----
    var_a = f"""
    <div class="variant" id="var-A">
      {cards}
      <div class="tabs">
        <button class="sel" data-pane="A-predict">🔮 Predict</button>
        <button data-pane="A-stand">🏆 Standings</button>
        <button data-pane="A-bet">💰 Bet</button>
        <button data-pane="A-lab">🔬 Model Lab</button>
      </div>
      <div class="pane on" id="A-predict">{upcoming_ph}{analyst}</div>
      <div class="pane" id="A-stand">{standings}</div>
      <div class="pane" id="A-bet">{betting}</div>
      <div class="pane" id="A-lab">{lb}{backtest}{results}</div>
    </div>"""

    # ---- Variant B: narrative funnel ----
    var_b = f"""
    <div class="variant" id="var-B">
      <div class="hero"><h2>⚽ World Cup Lab</h2>
        <div class="big">What to watch today, who's likely to win it, and how our models are doing — top to bottom by what matters most.</div>
      </div>
      {cards}
      <div class="jump"><a href="#b-now">Now</a><a href="#b-outlook">Outlook</a><a href="#b-record">Track record</a><a href="#b-lab">Research lab</a></div>
      <div id="b-now">{section("🔮 Now — today's picks & edges", upcoming_ph + analyst + betting)}</div>
      <div id="b-outlook">{section("🏆 Tournament outlook", standings)}</div>
      <div id="b-record">{section("📒 Track record", results)}</div>
      <div id="b-lab">{section("🔬 Research lab (advanced)", lb + backtest)}</div>
    </div>"""

    # ---- Variant C: cockpit grid ----
    var_c = f"""
    <div class="variant" id="var-C">
      {cards}
      <div class="cockpit">
        <div><div class="panelhead">Predictions</div>{upcoming_ph}{analyst}</div>
        <div><div class="panelhead">Outlook &amp; Models</div>{standings}{lb}</div>
        <div class="full"><div class="panelhead">Edges &amp; Bets</div>{betting}</div>
        <div class="full"><div class="panelhead">Validation</div>{backtest}{results}</div>
      </div>
    </div>"""

    names = {"A": "A — Intent tabs", "B": "B — Narrative funnel", "C": "C — Cockpit grid"}
    script = """
    (function(){
      var ORDER=["A","B","C"], NAMES=%s;
      function cur(){var v=new URLSearchParams(location.search).get("variant");return ORDER.indexOf(v)>=0?v:"A";}
      function show(v){
        ORDER.forEach(function(k){var el=document.getElementById("var-"+k);if(el)el.classList.toggle("on",k===v);});
        document.getElementById("plabel").textContent=NAMES[v];
        var u=new URL(location);u.searchParams.set("variant",v);history.replaceState(null,"",u);
      }
      function step(d){var v=cur();var i=(ORDER.indexOf(v)+d+ORDER.length)%%ORDER.length;show(ORDER[i]);}
      document.addEventListener("keydown",function(e){
        if(/INPUT|TEXTAREA/.test((e.target||{}).tagName))return;
        if(e.key==="ArrowLeft")step(-1);if(e.key==="ArrowRight")step(1);
      });
      window.__pstep=step;
      // tabs (variant A)
      document.querySelectorAll(".tabs button").forEach(function(b){
        b.addEventListener("click",function(){
          b.parentNode.querySelectorAll("button").forEach(function(o){o.classList.remove("sel");});
          b.classList.add("sel");
          document.querySelectorAll("#var-A .pane").forEach(function(p){p.classList.remove("on");});
          document.getElementById(b.dataset.pane).classList.add("on");
        });
      });
      show(cur());
    })();
    """ % json.dumps(names)

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard IA prototype — 3 variants</title>
<style>{css}{extra_css}</style></head>
<body><div class="ptag">PROTOTYPE · throwaway · 3 IA variants · ← / → to switch</div>
<div class="wrap">
<h1>⚽ World Cup Model-Research Lab</h1>
<div class="sub">IA redesign prototype · data as of {gen} · same content, three buckets</div>
{var_a}{var_b}{var_c}
</div>
<div class="pbar"><button onclick="__pstep(-1)">‹</button>
<span class="lbl" id="plabel">A</span>
<button onclick="__pstep(1)">›</button></div>
<script>{script}</script>
</body></html>"""

    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT}")
    print("open it and use the bottom bar or arrow keys to flip A/B/C")
    for v, n in names.items():
        print(f"  ?variant={v}  {n}")


if __name__ == "__main__":
    main()
