# Daily Match-Analyst job - launched by Windows Task Scheduler each morning.
#
# Spins up a fresh HEADLESS Claude Code session that researches today's World Cup
# fixtures (via the match-analyst subagent, anchored on our deterministic model
# info), rebuilds the dashboard, and commits + PUSHES it so Pages goes live.
#
# Runs unattended: --permission-mode bypassPermissions so no tool prompts block it.
# This is the user's own automation on their own machine, pre-authorized.
#
# Set up once via scripts/register_daily_match_analyst.ps1 (schtasks daily 07:00).

$ErrorActionPreference = 'Stop'

$RepoRoot   = 'C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections'
$ClaudeExe  = 'C:\Users\ztsha\.local\bin\claude.exe'
$LogDir     = Join-Path $RepoRoot 'worldcup_prediction_lab\runs\analyst\logs'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp   = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$logFile = Join-Path $LogDir "daily_$stamp.log"

Set-Location $RepoRoot

$prompt = @'
DAILY MATCH-ANALYST JOB (autonomous; user pre-authorized this scheduled run, including the git push). Repo root is the current working directory. Work on master per CLAUDE.md (Claude owns commits via PowerShell). Be leak-free: never use match results when forecasting.

Goal: make live, researched H/D/A picks for today's World Cup fixtures, anchored on our deterministic model info, then rebuild and PUSH the dashboard so it goes live.

Steps:
1) Today's date (America/New_York): run  date +%F  in the Bash tool. Call it TODAY.
2) List today's fixtures still needing research:
   cd worldcup_prediction_lab && uv run python -m wc_predictor.lab.analyst_cli list-fixtures --as-of TODAY
   Each line is: fixture_id<TAB>Home<TAB>Away<TAB>venue. If the list is EMPTY, skip to step 4 (still refresh + push).
3) For EACH fixture line, launch the match-analyst subagent (Agent tool, subagent_type "match-analyst") with a prompt like: 'Research and forecast the upcoming match <Home> vs <Away> for as-of date TODAY. Follow your agent instructions: dump-packet, do live web research, anchor to the market and deviate only on cited findings, then record your agent-mode forecast via analyst_cli record.' If subagent_type "match-analyst" is unavailable, instead follow .claude/agents/match-analyst.md inline yourself for that fixture (dump-packet -> web research -> write forecast JSON -> analyst_cli record). Keep deviations modest and cite every source. Run fixtures sequentially.
4) Refresh standings, record every variant's predictions for today, and rebuild the dashboard:
   cd worldcup_prediction_lab && uv run python -m wc_predictor.lab.championship --as-of TODAY --n-sims 20000
   cd worldcup_prediction_lab && uv run python -m wc_predictor.lab.run_experiments --as-of TODAY
   (run_experiments records ALL registered variants for today's fixtures, refreshes the leaderboard + backtest, and rebuilds the dashboard at the end -- so the "Upcoming forecasts by model" dropdown stays populated with every model, not just one.)
5) Commit + push (PowerShell git). Stage at least: worldcup_prediction_lab/runs/analyst/ledger.jsonl, worldcup_prediction_lab/runs/standings/championship_odds.json, docs/index.html, docs/data/live.json, worldcup_prediction_lab/research/dashboard.html, worldcup_prediction_lab/research/data/live.json, and any regenerated reports under worldcup_prediction_lab/reports or research. Commit message: "Daily match-analyst picks + standings TODAY". Then: git push. Verify the push succeeded (it MUST push, not just commit -- GitHub Pages serves /docs on master).
6) Report a concise summary: which matches were researched, each pick (team + H/D/A), how far each moved off the market and why, and confirm the push landed.

Notes: the match-analyst subagent + analyst_cli are already built and committed. Network is available (Polymarket + web research). If a single fixture's research fails, log it and continue with the rest; still rebuild + push at the end. Do not touch Codex worktrees/branches. CRITICAL: this is a ONE-SHOT non-interactive session (-p mode) -- it does not get a second turn. NEVER run run_experiments, championship, or any other step with run_in_background: true and then wait for a completion notification -- that notification can only be delivered on a future turn, which will never come, so the session would exit having done nothing after that point (this happened on 2026-06-30: run_experiments produced good output but was launched in the background, the session then exited "waiting to be notified," and nothing was committed or pushed). Run every step in this prompt to completion in the FOREGROUND before moving to the next one.
'@

"=== Daily match-analyst run started $stamp ===" | Out-File -FilePath $logFile -Encoding utf8

& $ClaudeExe -p $prompt --permission-mode bypassPermissions --model claude-opus-4-8 *>> $logFile

"=== finished (exit $LASTEXITCODE) at $(Get-Date -Format 'yyyy-MM-dd_HHmmss') ===" | Out-File -FilePath $logFile -Append -Encoding utf8
