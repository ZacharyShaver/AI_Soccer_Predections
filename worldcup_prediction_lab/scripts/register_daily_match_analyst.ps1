# One-time setup: register the daily Match-Analyst job with Windows Task Scheduler.
#
# Creates a task that runs scripts/daily_match_analyst.ps1 every day at 07:00 local,
# as the current user, only while logged on (so it needs the PC on + signed in).
# Re-run with -Force semantics (/F) to update. Unregister with:
#   schtasks /Delete /TN "WC-Daily-Match-Analyst" /F

$ErrorActionPreference = 'Stop'

$TaskName = 'WC-Daily-Match-Analyst'
$Script   = 'C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections\worldcup_prediction_lab\scripts\daily_match_analyst.ps1'
$Action   = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Script`""

schtasks /Create /TN $TaskName /TR $Action /SC DAILY /ST 07:00 /F

Write-Host ''
Write-Host "Registered '$TaskName' - daily at 07:00 local."
Write-Host "Inspect: schtasks /Query /TN `"$TaskName`" /V /FO LIST"
Write-Host "Run now: schtasks /Run /TN `"$TaskName`""
Write-Host "Remove : schtasks /Delete /TN `"$TaskName`" /F"
