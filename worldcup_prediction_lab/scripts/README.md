# Scheduled daily forecast refresh

`run_daily_update.ps1` is the wrapper invoked by a Windows **Task Scheduler** task named
**`WorldCupDailyForecast`**. Each run:

1. Ingests the latest international results (martj42), retrains host-aware Elo, re-forecasts all
   upcoming fixtures into a new immutable ledger partition, and refreshes championship odds
   (`wc_predictor.run_daily_update`).
2. Rebuilds the model-research leaderboard, walk-forward backtest cache, HTML dashboard, and
   GitHub Pages copy (`docs/index.html`).
3. Refreshes the running scorecard (`wc_predictor.evaluation.scorecard`).

Output is appended to `runs/daily_update.log` (gitignored).

## HTML report / GitHub Pages

Every daily update now writes the same self-contained dashboard to:

- `worldcup_prediction_lab/research/dashboard.html` for local viewing.
- `docs/index.html` for GitHub Pages.

To view it online after pushing, enable GitHub Pages for this repository with:

- Source: **Deploy from a branch**
- Branch: **main**
- Folder: **/docs**

The report URL will be:

`https://zacharyshaver.github.io/AI_Soccer_Predections/`

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

---

# Autonomous model-research lab (Tue–Thu, this week only)

`run_research_lab.ps1` is invoked by the **`WorldCupResearchLab`** task. It launches
**headless Claude Code** (`claude -p --dangerously-skip-permissions`) with the prompt in
`research/CRON_PROMPT.md`, which drives the daily Claude-orchestrates-Codex model bake-off
per `research/DAILY_PLAYBOOK.md`: score yesterday's variants, then build 3 new feature-model
variants (each in its own git worktree, authored by Codex) and record their predictions.

- **Triggers:** one-time at 2026-06-23, -24, -25 09:08 local (Tue/Wed/Thu). Not recurring —
  it does not repeat next week. Monday (day 1) was seeded manually.
- **Output log:** `runs/research_lab.log` (gitignored).
- **⚠ Security:** runs with `--dangerously-skip-permissions` — the unattended session has full
  tool access (git, Codex, file writes). Only because every command is bounded by the playbook.
  The machine must be on and able to run `claude` + `codex` at the trigger time.

```powershell
Get-ScheduledTaskInfo -TaskName "WorldCupResearchLab"     # status / last result
Start-ScheduledTask   -TaskName "WorldCupResearchLab"     # run a day now (real run!)
Disable-ScheduledTask -TaskName "WorldCupResearchLab"     # pause
Unregister-ScheduledTask -TaskName "WorldCupResearchLab" -Confirm:$false   # remove
Get-Content "..\runs\research_lab.log" -Tail 40           # see what it did
```

To run a lab day manually instead of waiting for the trigger, just open Claude Code and say
"do today's research lab day" (it follows `research/DAILY_PLAYBOOK.md`).
