# Autonomous daily model-research run — invoked by the "WorldCupResearchLab" task
# (Tue/Wed/Thu this week). Launches headless Claude Code, which orchestrates Codex in
# git worktrees to build + score the day's model variants per research/DAILY_PLAYBOOK.md.
#
# NOTE: runs with --dangerously-skip-permissions so Claude can use tools unattended.
# That grants full tool access; only run on a machine you trust. The machine must be on.

$ErrorActionPreference = "Stop"
$repo = "C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections"
$pkg = Join-Path $repo "worldcup_prediction_lab"
$claude = "C:\Users\ztsha\.local\bin\claude.exe"
$log = Join-Path $pkg "runs\research_lab.log"

Set-Location $repo
$env:PYTHONUTF8 = "1"

$today = Get-Date -Format "yyyy-MM-dd"
$dow = (Get-Date).DayOfWeek
$body = Get-Content (Join-Path $pkg "research\CRON_PROMPT.md") -Raw
$prompt = "Today's date is $today ($dow).`n`n$body"

$start = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
"" | Out-File -FilePath $log -Append -Encoding utf8
"=================== research lab start $start (as_of $today) ===================" | Out-File -FilePath $log -Append -Encoding utf8

($prompt | & $claude -p --dangerously-skip-permissions *>&1) | Out-File -FilePath $log -Append -Encoding utf8
$code = $LASTEXITCODE

$end = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
"=================== research lab end $end (exit $code) ===================" | Out-File -FilePath $log -Append -Encoding utf8
exit $code
