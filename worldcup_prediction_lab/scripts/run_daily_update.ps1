# Daily World Cup forecast refresh — invoked by the "WorldCupDailyForecast" scheduled task.
# Runs the L1 daily loop (ingest -> retrain -> re-forecast -> refresh odds -> bake HTML
# dashboard/GitHub Pages copy) and then the L2 scorecard, appending all output to
# runs/daily_update.log. Safe to run manually too.
#
# HARDENED 2026-07-02: this task ran silently empty three days in a row
# (2026-06-26 to 2026-06-28) -- the log shows "run start" then nothing at all, no
# error, no "run end". Root cause (confirmed via commit 5e81ded): an unhandled
# WindowsPath JSON-serialization crash in run_daily_update.py's summary step. The
# Python side now always prints a "[run_daily_update] FAILED" marker + traceback on
# any exception (see run_daily_update.py main()), but this wrapper is hardened too,
# for two more reasons: (1) Python buffers stdout when it isn't a terminal, so a
# crash's output can be lost entirely if the process is killed (e.g. by the
# scheduled task's execution time limit) before it flushes -- PYTHONUNBUFFERED fixes
# that; (2) the wrapper itself must guarantee a closing "run end" log line even if
# something throws before reaching it, so a run is never left silently open-ended.

$ErrorActionPreference = "Stop"
$project = "C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections\worldcup_prediction_lab"
$uv = "C:\Users\ztsha\.local\bin\uv.exe"
$log = Join-Path $project "runs\daily_update.log"

Set-Location $project
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

$start = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
"" | Out-File -FilePath $log -Append -Encoding utf8
"=================== run start $start ===================" | Out-File -FilePath $log -Append -Encoding utf8

$updateExit = 1
$scoreExit = 1

try {
    # 1) Daily loop: ingest latest results, retrain, re-forecast upcoming fixtures, refresh odds.
    (& $uv run --extra dev python -m wc_predictor.run_daily_update *>&1) | Out-File -FilePath $log -Append -Encoding utf8
    $updateExit = $LASTEXITCODE

    # 2) Refresh the running scorecard (us vs market vs actual) against whatever has resolved.
    (& $uv run --extra dev python -m wc_predictor.evaluation.scorecard *>&1) | Out-File -FilePath $log -Append -Encoding utf8
    $scoreExit = $LASTEXITCODE
} catch {
    # A terminating PowerShell-level error (e.g. uv.exe not found) would otherwise skip
    # straight past both steps above with nothing logged. Make it loud instead.
    "[run_daily_update.ps1] WRAPPER FAILED: $($_.Exception.Message)" | Out-File -FilePath $log -Append -Encoding utf8
} finally {
    # Always write a closing line, even on an unhandled wrapper-level failure, so a run
    # is never left as a bare "run start" with nothing after it.
    $end = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    "=================== run end $end (update exit $updateExit, scorecard exit $scoreExit) ===================" | Out-File -FilePath $log -Append -Encoding utf8
}

if ($updateExit -ne 0 -or $scoreExit -ne 0) { exit 1 }
