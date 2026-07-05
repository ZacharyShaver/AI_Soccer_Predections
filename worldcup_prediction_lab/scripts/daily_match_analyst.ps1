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

# Run a native command, folding stdout+stderr into the log, and return its exit
# code. Under Windows PowerShell 5.1 with $ErrorActionPreference='Stop', a
# PS-level `2>&1` on a native exe turns every stderr line into a terminating
# NativeCommandError -- on 2026-07-05 that made a successful `git push` (which
# reports "To https://..." on stderr) look like a failure. So stderr is merged
# only while the preference is temporarily 'Continue', and success is judged
# solely by the exit code.
function Invoke-NativeLogged {
    param(
        [string]$Exe,
        [string[]]$ArgumentList
    )
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Exe @ArgumentList 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEap
    }
    $output | ForEach-Object { $_.ToString() } |
        Out-File -FilePath $logFile -Append -Encoding utf8
    return $exitCode
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

    # In Windows PowerShell 5.1, Process.ExitCode is $null after WaitForExit()
    # unless the handle was touched while the process was alive (the 2026-07-05
    # log printed an empty phase-1 exit code because of this).
    $null = $proc.Handle

    if (-not $proc.WaitForExit($ResearchTimeoutMinutes * 60 * 1000)) {
        Write-Log "[research] TIMED OUT after $ResearchTimeoutMinutes min -- killing and continuing to phase 2."
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $claudeExit = 1
    } else {
        $claudeExit = $proc.ExitCode
        if ($null -eq $claudeExit) {
            Write-Log "[research] exit code unavailable from process handle; recording as 1."
            $claudeExit = 1
        }
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

    $champExit = Invoke-NativeLogged $Uv @('run', 'python', '-m', 'wc_predictor.lab.championship', '--as-of', $today, '--n-sims', '20000')
    if ($champExit -ne 0) {
        $pipelineOk = $false
        Write-Log "[pipeline] championship step failed (exit $champExit)"
    }

    $expExit = Invoke-NativeLogged $Uv @('run', 'python', '-m', 'wc_predictor.lab.run_experiments', '--as-of', $today)
    if ($expExit -ne 0) {
        $pipelineOk = $false
        Write-Log "[pipeline] run_experiments step failed (exit $expExit)"
    }
} catch {
    $pipelineOk = $false
    Write-Log "[pipeline] FAILED: $($_.Exception.Message)"
}

Set-Location $RepoRoot
$pushOk = $false

try {
    $addExit = Invoke-NativeLogged 'git' @('add',
        'worldcup_prediction_lab/runs/analyst/ledger.jsonl',
        'worldcup_prediction_lab/runs/standings/championship_odds.json',
        'docs/index.html',
        'docs/data/live.json',
        'worldcup_prediction_lab/research/dashboard.html',
        'worldcup_prediction_lab/research/data/live.json',
        'worldcup_prediction_lab/reports',
        'worldcup_prediction_lab/research')
    if ($addExit -ne 0) {
        Write-Log "[git] add exited $addExit; continuing to status check."
    }

    $status = git status --porcelain
    if ($status) {
        $commitExit = Invoke-NativeLogged 'git' @('commit', '-m', "Daily match-analyst picks + standings $today")
        if ($commitExit -ne 0) {
            Write-Log "[git] commit failed (exit $commitExit)"
        } else {
            $pushExit = Invoke-NativeLogged 'git' @('push')
            if ($pushExit -eq 0) {
                $pushOk = $true
            } else {
                # Belt and braces: a push has been misreported as failed before
                # (2026-07-05). git push updates the remote-tracking ref only on
                # success, so if it now matches HEAD the push actually landed.
                $head = git rev-parse HEAD
                $remoteHead = git rev-parse '@{upstream}'
                if ($head -and $remoteHead -and ($head -eq $remoteHead)) {
                    Write-Log "[git] push exited $pushExit but upstream matches HEAD -- treating as pushed."
                    $pushOk = $true
                } else {
                    Write-Log "[git] push failed (exit $pushExit)"
                }
            }
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
