# Daily Match-Analyst job - launched by Windows Task Scheduler each morning.
#
# HARDENED 2026-07-02: previously a single one-shot Claude session (-p mode) did
# everything -- research, dashboard rebuild, commit, push -- and was trusted to run
# every step in the foreground. It didn't: on 2026-06-30 AND again on 2026-07-01 the
# session launched the dashboard-rebuild step with run_in_background and then waited
# for a completion notification that a one-shot session can never receive (no future
# turn exists to deliver it), so it exited having done nothing after that point --
# nothing committed, nothing pushed, on TWO separate mornings, even though the prompt
# already warned against exactly this after the first incident.
#
# New design: split into two phases so the guaranteed steps no longer depend on the
# LLM reliably following a "don't do X" instruction under time pressure.
#   Phase 1 (Claude, bounded + time-boxed): research today's fixtures and record
#   picks. Nothing else. If it fails, hangs, or times out, it is killed and phase 2
#   proceeds regardless.
#   Phase 2 (pure PowerShell, deterministic, ALWAYS runs): refresh standings +
#   dashboard, commit, push. This is the guaranteed part -- it does not ask an LLM to
#   remember to do it.
#
# Set up once via scripts/register_daily_match_analyst.ps1 (schtasks daily 07:00).

$ErrorActionPreference = 'Stop'

$RepoRoot   = 'C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections'
$LabRoot    = Join-Path $RepoRoot 'worldcup_prediction_lab'
$ClaudeExe  = 'C:\Users\ztsha\.local\bin\claude.exe'
$Uv         = 'C:\Users\ztsha\.local\bin\uv.exe'
$LogDir     = Join-Path $LabRoot 'runs\analyst\logs'
$ResearchTimeoutMinutes = 20

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp   = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$logFile = Join-Path $LogDir "daily_$stamp.log"

function Write-Log {
    param([string]$Line)
    $Line | Out-File -FilePath $logFile -Append -Encoding utf8
}

Set-Location $RepoRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

Write-Log "=== Daily match-analyst run started $stamp ==="

# ---------------------------------------------------------------------------
# Phase 1: bounded live research (Claude, one-shot, time-boxed). Any failure or
# timeout here is logged and swallowed -- it must never block phase 2.
# ---------------------------------------------------------------------------
$researchPrompt = @'
DAILY MATCH-ANALYST RESEARCH JOB (autonomous; user pre-authorized this scheduled run).
Repo root is the current working directory. Be leak-free: never use match results when
forecasting.

Scope: this session ONLY researches fixtures and records picks. It does NOT rebuild the
dashboard, run_experiments, championship, commit, or push -- a separate deterministic
script step does all of that immediately after this session exits, regardless of what
happens here. Do not wait for it, do not attempt it, do not background anything and wait
for a notification -- this is a one-shot session with no future turn to receive one.

Steps:
1) Today's date (America/New_York): run  date +%F  in the Bash tool. Call it TODAY.
2) List today's fixtures still needing research:
   cd worldcup_prediction_lab && uv run python -m wc_predictor.lab.analyst_cli list-fixtures --as-of TODAY
   Each line is: fixture_id<TAB>Home<TAB>Away<TAB>venue. If EMPTY, stop -- nothing to do.
3) For EACH fixture line, launch the match-analyst subagent (Agent tool, subagent_type
   "match-analyst") with a prompt like: 'Research and forecast the upcoming match <Home>
   vs <Away> for as-of date TODAY. Follow your agent instructions: dump-packet, do live
   web research, anchor to the market and deviate only on cited findings, then record
   your agent-mode forecast via analyst_cli record.' If subagent_type "match-analyst" is
   unavailable, follow .claude/agents/match-analyst.md inline yourself for that fixture.
   Keep deviations modest and cite every source. Run fixtures sequentially, entirely in
   the foreground.
4) Report a short summary: which matches were researched and each pick (team + H/D/A).

Notes: do not touch Codex worktrees/branches. Do not run git. Do not run
run_experiments, championship, or any dashboard rebuild.
'@

$researchOut = Join-Path $LogDir "research_$stamp.out.log"
$researchErr = Join-Path $LogDir "research_$stamp.err.log"
$claudeExit = 1

try {
    $proc = Start-Process -FilePath $ClaudeExe `
        -ArgumentList @('-p', $researchPrompt, '--permission-mode', 'bypassPermissions', '--model', 'claude-opus-4-8') `
        -NoNewWindow -PassThru `
        -RedirectStandardOutput $researchOut `
        -RedirectStandardError  $researchErr

    if (-not $proc.WaitForExit($ResearchTimeoutMinutes * 60 * 1000)) {
        Write-Log "[research] TIMED OUT after $ResearchTimeoutMinutes min -- killing and continuing to phase 2."
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $claudeExit = 1
    } else {
        $claudeExit = $proc.ExitCode
    }
} catch {
    Write-Log "[research] FAILED to launch or crashed: $($_.Exception.Message)"
    $claudeExit = 1
}

Write-Log "[research] phase 1 exit code: $claudeExit"
if (Test-Path $researchOut) { Get-Content $researchOut | Out-File -FilePath $logFile -Append -Encoding utf8 }
if (Test-Path $researchErr) { Get-Content $researchErr | Out-File -FilePath $logFile -Append -Encoding utf8 }

# ---------------------------------------------------------------------------
# Phase 2: deterministic pipeline refresh + commit + push. ALWAYS runs, even if
# phase 1 failed or timed out, so a bad LLM session can never again silently skip
# the push the way it did on 2026-06-30 and 2026-07-01.
# ---------------------------------------------------------------------------
$today = Get-Date -Format 'yyyy-MM-dd'
$pipelineOk = $true

try {
    Set-Location $LabRoot

    (& $Uv run python -m wc_predictor.lab.championship --as-of $today --n-sims 20000 *>&1) |
        Out-File -FilePath $logFile -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        $pipelineOk = $false
        Write-Log "[pipeline] championship step failed (exit $LASTEXITCODE)"
    }

    (& $Uv run python -m wc_predictor.lab.run_experiments --as-of $today *>&1) |
        Out-File -FilePath $logFile -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        $pipelineOk = $false
        Write-Log "[pipeline] run_experiments step failed (exit $LASTEXITCODE)"
    }
} catch {
    $pipelineOk = $false
    Write-Log "[pipeline] FAILED: $($_.Exception.Message)"
}

Set-Location $RepoRoot
$pushOk = $false

try {
    git add `
        worldcup_prediction_lab/runs/analyst/ledger.jsonl `
        worldcup_prediction_lab/runs/standings/championship_odds.json `
        docs/index.html `
        docs/data/live.json `
        worldcup_prediction_lab/research/dashboard.html `
        worldcup_prediction_lab/research/data/live.json `
        worldcup_prediction_lab/reports `
        worldcup_prediction_lab/research `
        2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8

    $status = git status --porcelain
    if ($status) {
        git commit -m "Daily match-analyst picks + standings $today" 2>&1 |
            Out-File -FilePath $logFile -Append -Encoding utf8
        git push 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
        if ($LASTEXITCODE -eq 0) {
            $pushOk = $true
        } else {
            Write-Log "[git] push failed (exit $LASTEXITCODE)"
        }
    } else {
        Write-Log "[git] nothing to commit."
        $pushOk = $true
    }
} catch {
    Write-Log "[git] FAILED: $($_.Exception.Message)"
}

$overallOk = $pipelineOk -and $pushOk
Write-Log "=== finished (research_exit=$claudeExit pipeline_ok=$pipelineOk push_ok=$pushOk) at $(Get-Date -Format 'yyyy-MM-dd_HHmmss') ==="

if (-not $overallOk) { exit 1 }
