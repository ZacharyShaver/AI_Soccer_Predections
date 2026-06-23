# Scheduled daily forecast refresh

`run_daily_update.ps1` is the wrapper invoked by a Windows **Task Scheduler** task named
**`WorldCupDailyForecast`**. Each run:

1. Ingests the latest international results (martj42), retrains host-aware Elo, re-forecasts all
   upcoming fixtures into a new immutable ledger partition, and refreshes championship odds
   (`wc_predictor.run_daily_update`).
2. Refreshes the running scorecard (`wc_predictor.evaluation.scorecard`).

Output is appended to `runs/daily_update.log` (gitignored).

## Schedule

- Runs **daily at 9:00 AM local time**, with *Start when available* so a missed run (laptop asleep)
  fires when the machine is next on.
- 9 AM local is deliberate: the loop keys its `as_of` off the **UTC** date. At 9 AM local the UTC
  date matches the local date, so `as_of` = today. Running it late in the evening (local) can roll
  the UTC date to *tomorrow* and create a premature partition — prefer the schedule, or pass an
  explicit `as_of` if running manually after ~5 PM local.

## Managing the task (PowerShell)

```powershell
# See status / last result
Get-ScheduledTaskInfo -TaskName "WorldCupDailyForecast"

# Run it now
Start-ScheduledTask -TaskName "WorldCupDailyForecast"

# Change the time (e.g. 7:30 AM)
$t = New-ScheduledTaskTrigger -Daily -At 7:30am
Set-ScheduledTask -TaskName "WorldCupDailyForecast" -Trigger $t

# Pause / resume
Disable-ScheduledTask -TaskName "WorldCupDailyForecast"
Enable-ScheduledTask  -TaskName "WorldCupDailyForecast"

# Remove entirely
Unregister-ScheduledTask -TaskName "WorldCupDailyForecast" -Confirm:$false

# Tail the log
Get-Content "..\runs\daily_update.log" -Tail 30
```

## Re-create the task from scratch

```powershell
$wrapper  = "C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections\worldcup_prediction_lab\scripts\run_daily_update.ps1"
$action   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$wrapper`""
$trigger  = New-ScheduledTaskTrigger -Daily -At 9:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "WorldCupDailyForecast" -Action $action -Trigger $trigger -Settings $settings -Force
```
