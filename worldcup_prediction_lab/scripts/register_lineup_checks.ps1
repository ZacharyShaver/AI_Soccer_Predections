# Registers one-shot scheduled tasks that fire lineup_check.ps1 at kickoff-75min for
# each of today's fixtures (kickoff times from config/kickoff_times.csv via
# wc_predictor.lab.kickoffs; team names from analyst_cli list-fixtures). Invoked by
# daily_match_analyst.ps1 as phase 1.5; safe to re-run (Register-ScheduledTask -Force
# overwrites, past trigger times and already-researched fixtures are skipped).
#
# Tasks run as the logged-on user with -WakeToRun -StartWhenAvailable so a sleeping
# machine wakes (or fires late) rather than silently missing the window. Each task
# deletes itself at the end of lineup_check.ps1.

param(
    [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
    [int]$LeadMinutes = 75
)

$ErrorActionPreference = 'Stop'

$RepoRoot = 'C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections'
$LabRoot  = Join-Path $RepoRoot 'worldcup_prediction_lab'
$Uv       = 'C:\Users\ztsha\.local\bin\uv.exe'
$Runner   = Join-Path $LabRoot 'scripts\lineup_check.ps1'

Set-Location $LabRoot
$env:PYTHONUTF8 = "1"

# --- Today's kickoffs: lines of "fixture_id<TAB>YYYY-MM-DD HH:MM" -------------------
$kickoffCode = "from wc_predictor.lab.kickoffs import kickoffs_for_date`n" +
               "for fid, ts in kickoffs_for_date('$Date'):`n" +
               "    print(f'{fid}\t{ts:%Y-%m-%d %H:%M}')"
$kickoffLines = & $Uv run python -c $kickoffCode
if ($LASTEXITCODE -ne 0) { throw "kickoffs_for_date failed (exit $LASTEXITCODE)" }
$kickoffs = @{}
foreach ($line in @($kickoffLines)) {
    if ("$line".Trim()) {
        $parts = "$line".Split("`t")
        $kickoffs[$parts[0]] = [datetime]::ParseExact($parts[1], 'yyyy-MM-dd HH:mm', $null)
    }
}
Write-Output "[register] $($kickoffs.Count) kickoff(s) on $Date in config/kickoff_times.csv."
if ($kickoffs.Count -eq 0) { exit 0 }

# --- Today's fixtures still lacking an agent_late row (TSV: id, home, away, venue) --
$fixtureLines = & $Uv run python -m wc_predictor.lab.analyst_cli list-fixtures --as-of $Date --mode agent_late
if ($LASTEXITCODE -ne 0) { throw "list-fixtures failed (exit $LASTEXITCODE)" }

$registered = 0
foreach ($line in @($fixtureLines)) {
    if (-not "$line".Trim()) { continue }
    $f = "$line".Split("`t")
    $fid = $f[0]; $homeName = $f[1]; $awayName = $f[2]

    if (-not $kickoffs.ContainsKey($fid)) {
        Write-Output "[register] SKIP $homeName v $awayName ($fid): no kickoff time in config/kickoff_times.csv."
        continue
    }
    $fireAt = $kickoffs[$fid].AddMinutes(-$LeadMinutes)
    if ($fireAt -le (Get-Date)) {
        Write-Output "[register] SKIP $homeName v $awayName ($fid): T-$LeadMinutes ($fireAt) already past."
        continue
    }

    $taskName = "WC-LineupCheck-$fid"
    $argString = "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" " +
                 "-FixtureId `"$fid`" -HomeTeam `"$homeName`" -AwayTeam `"$awayName`""
    $action   = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argString
    $trigger  = New-ScheduledTaskTrigger -Once -At $fireAt
    $settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Force | Out-Null
    Write-Output "[register] $taskName -> $($fireAt.ToString('yyyy-MM-dd HH:mm')) ($homeName v $awayName, kickoff $($kickoffs[$fid].ToString('HH:mm')))."
    $registered++
}
Write-Output "[register] done: $registered task(s) registered."


