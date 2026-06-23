# Daily World Cup forecast refresh — invoked by the "WorldCupDailyForecast" scheduled task.
# Runs the L1 daily loop (ingest -> retrain -> re-forecast -> refresh odds) and then the
# L2 scorecard, appending all output to runs/daily_update.log. Safe to run manually too.

$ErrorActionPreference = "Stop"
$project = "C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections\worldcup_prediction_lab"
$uv = "C:\Users\ztsha\.local\bin\uv.exe"
$log = Join-Path $project "runs\daily_update.log"

Set-Location $project
$env:PYTHONUTF8 = "1"

$start = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
"" | Out-File -FilePath $log -Append -Encoding utf8
"=================== run start $start ===================" | Out-File -FilePath $log -Append -Encoding utf8

# 1) Daily loop: ingest latest results, retrain, re-forecast upcoming fixtures, refresh odds.
(& $uv run --extra dev python -m wc_predictor.run_daily_update *>&1) | Out-File -FilePath $log -Append -Encoding utf8
$updateExit = $LASTEXITCODE

# 2) Refresh the running scorecard (us vs market vs actual) against whatever has resolved.
(& $uv run --extra dev python -m wc_predictor.evaluation.scorecard *>&1) | Out-File -FilePath $log -Append -Encoding utf8
$scoreExit = $LASTEXITCODE

$end = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
"=================== run end $end (update exit $updateExit, scorecard exit $scoreExit) ===================" | Out-File -FilePath $log -Append -Encoding utf8

if ($updateExit -ne 0 -or $scoreExit -ne 0) { exit 1 }
