# T-75 lineup-check runner - fired by a one-shot scheduled task ~75 minutes before
# kickoff (registered by register_lineup_checks.ps1). Runs a narrow, time-boxed Claude
# session that re-researches ONE fixture with confirmed-XI-era information and records
# an `agent_late` ledger row, then a deterministic tail commits + pushes the ledger and
# deletes this fixture's one-shot task.
#
# Follows daily_match_analyst.ps1's hardened pattern: the LLM step is bounded and
# swallowed on failure; the guaranteed steps (git, task cleanup) never depend on it.
# -DryRun logs what would happen without calling Claude, git, or schtasks.

param(
    [Parameter(Mandatory = $true)][string]$FixtureId,
    [Parameter(Mandatory = $true)][string]$HomeTeam,
    [Parameter(Mandatory = $true)][string]$AwayTeam,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$RepoRoot  = 'C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections'
$LabRoot   = Join-Path $RepoRoot 'worldcup_prediction_lab'
$ClaudeExe = 'C:\Users\ztsha\.local\bin\claude.exe'
$LogDir    = Join-Path $LabRoot 'runs\analyst\logs'
$TaskName  = "WC-LineupCheck-$FixtureId"
$ResearchTimeoutMinutes = 10

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp   = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$logFile = Join-Path $LogDir "lineup_${FixtureId}_$stamp.log"

function Write-Log {
    param([string]$Line)
    $Line | Out-File -FilePath $logFile -Append -Encoding utf8
}

# Same stderr handling as daily_match_analyst.ps1: merge native stderr only while the
# preference is 'Continue' (PS 5.1 + Stop turns benign stderr into terminating errors);
# judge success solely by exit code.
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

$today = Get-Date -Format 'yyyy-MM-dd'
Write-Log "=== Lineup check started $stamp fixture=$FixtureId ($HomeTeam v $AwayTeam) DryRun=$DryRun ==="

if ($DryRun) {
    Write-Log "[dry-run] would launch time-boxed Claude session for $HomeTeam v $AwayTeam (fixture $FixtureId, as-of $today)."
    Write-Log "[dry-run] would record via: analyst_cli record --json runs/analyst/forecast_late_$FixtureId.json --mode agent_late"
    Write-Log "[dry-run] would git add/commit/push worldcup_prediction_lab/runs/analyst/ledger.jsonl"
    Write-Log "[dry-run] would delete scheduled task $TaskName"
    Write-Log "=== Lineup check finished (dry-run) ==="
    exit 0
}

# ---------------------------------------------------------------------------
# Phase 1: bounded lineup research (Claude, one-shot, time-boxed). Any failure
# is logged and swallowed -- the tail must always run.
# ---------------------------------------------------------------------------
$prompt = @"
T-75 LINEUP CHECK (autonomous; user pre-authorized this scheduled pre-kickoff run).
ONE fixture only: $HomeTeam vs $AwayTeam (fixture_id $FixtureId), kicking off in ~75 minutes.
Repo root is the current working directory. Be leak-free: never use match results.
This is a one-shot session: run everything in the foreground, background nothing.

Follow .claude/agents/match-analyst.md "Late mode" scope:
1) cd worldcup_prediction_lab && uv run python -m wc_predictor.lab.analyst_cli dump-packet --fixture "$FixtureId" --as-of $today --out runs/analyst/packet_late_$FixtureId.json
   Read it: market anchor, deterministic baseline, and your_record (your own resolved history --
   it informs how you SIZE deviations, never justifies exceeding them).
2) Research ONLY: confirmed starting XIs, late injury/suspension news from today, and current
   odds at 2-3 reputable books. SKIP travel/weather/social -- the morning pass covered those.
3) Start at the market anchor; deviate only on concrete cited findings, keep it modest.
4) Write the forecast JSON (schema per the agent file, as_of $today, copy elo_probs/market_probs
   from the packet) to worldcup_prediction_lab/runs/analyst/forecast_late_$FixtureId.json, then:
   cd worldcup_prediction_lab && uv run python -m wc_predictor.lab.analyst_cli record --json runs/analyst/forecast_late_$FixtureId.json --mode agent_late
5) Print a 3-line summary (final H/D/A, pick, what moved you off the anchor or that nothing did).
Do NOT run git. Do NOT rebuild dashboards. Do NOT touch other fixtures.
"@

$researchOut = Join-Path $LogDir "lineup_${FixtureId}_$stamp.out.log"
$researchErr = Join-Path $LogDir "lineup_${FixtureId}_$stamp.err.log"
$claudeExit = 1

try {
    # Prompt goes via stdin: Start-Process -ArgumentList joins elements with
    # spaces WITHOUT quoting them, so a multi-line prompt reached claude.exe as
    # loose tokens -- from 2026-07-06 through 2026-07-10 the session received
    # only "DAILY" as its prompt and lost every flag after it (no
    # bypassPermissions, wrong model). claude -p reads the prompt from stdin
    # when no prompt argument is given, and the remaining single-word flags
    # survive the unquoted join.
    $promptFile = Join-Path $LogDir "lineup_prompt_${FixtureId}_$stamp.txt"
    [IO.File]::WriteAllText($promptFile, $prompt, (New-Object System.Text.UTF8Encoding($false)))
    $proc = Start-Process -FilePath $ClaudeExe `
        -ArgumentList @('-p', '--permission-mode', 'bypassPermissions', '--model', 'claude-opus-4-8') `
        -NoNewWindow -PassThru `
        -RedirectStandardInput  $promptFile `
        -RedirectStandardOutput $researchOut `
        -RedirectStandardError  $researchErr

    # PS 5.1: ExitCode is $null after WaitForExit() unless the handle was touched
    # while the process was alive.
    $null = $proc.Handle

    if (-not $proc.WaitForExit($ResearchTimeoutMinutes * 60 * 1000)) {
        Write-Log "[research] TIMED OUT after $ResearchTimeoutMinutes min -- killing and continuing to the tail."
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $claudeExit = 1
    } else {
        $claudeExit = $proc.ExitCode
        if ($null -eq $claudeExit) { $claudeExit = 1 }
    }
} catch {
    Write-Log "[research] FAILED to launch or crashed: $($_.Exception.Message)"
    $claudeExit = 1
}

Write-Log "[research] phase 1 exit code: $claudeExit"
if (Test-Path $researchOut) { Get-Content $researchOut | Out-File -FilePath $logFile -Append -Encoding utf8 }
if (Test-Path $researchErr) { Get-Content $researchErr | Out-File -FilePath $logFile -Append -Encoding utf8 }

# ---------------------------------------------------------------------------
# Phase 2: deterministic tail -- commit + push the ledger (only if the research
# actually appended a row there's something to commit), then delete this task.
# ---------------------------------------------------------------------------
$pushOk = $false
try {
    $addExit = Invoke-NativeLogged 'git' @('add', 'worldcup_prediction_lab/runs/analyst/ledger.jsonl')
    if ($addExit -ne 0) { Write-Log "[git] add exited $addExit; continuing to status check." }

    $status = git status --porcelain -- worldcup_prediction_lab/runs/analyst/ledger.jsonl
    if ($status) {
        $commitExit = Invoke-NativeLogged 'git' @('commit', '-m', "Lineup-check pick $HomeTeam v $AwayTeam $today")
        if ($commitExit -ne 0) {
            Write-Log "[git] commit failed (exit $commitExit)"
        } else {
            $pushExit = Invoke-NativeLogged 'git' @('push')
            if ($pushExit -eq 0) {
                $pushOk = $true
            } else {
                # Same belt-and-braces as the daily job: push success is visible in
                # the remote-tracking ref even when the exit code is misreported.
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
        Write-Log "[git] no ledger change to commit (research likely recorded nothing)."
        $pushOk = $true
    }
} catch {
    Write-Log "[git] FAILED: $($_.Exception.Message)"
}

try {
    schtasks /delete /tn $TaskName /f | Out-Null
    Write-Log "[cleanup] deleted scheduled task $TaskName"
} catch {
    Write-Log "[cleanup] could not delete task $TaskName (non-fatal): $($_.Exception.Message)"
}

Write-Log "=== Lineup check finished (research_exit=$claudeExit push_ok=$pushOk) at $(Get-Date -Format 'yyyy-MM-dd_HHmmss') ==="
if (-not $pushOk) { exit 1 }

