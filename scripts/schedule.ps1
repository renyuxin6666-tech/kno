param([switch]$Remove, [string]$TaskName = 'ObsidianResearchPipeline-Weekly')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.runtime\venv\Scripts\python.exe'
$config = Join-Path $repo 'settings.local.json'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host 'Local indexing schedule removed. Your vault and source files are preserved.'
    exit
}
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $config)) {
    throw 'Run Start.cmd before enabling the schedule.'
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw 'A task with this name already exists. Inspect it rather than overwriting it.'
}
$pipeline = Join-Path $PSScriptRoot 'pipeline.py'
$arguments = '"' + $pipeline + '" refresh --config "' + $config + '"'
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '20:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 4)
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Refresh local research indexes weekly; original research files remain read-only.' | Out-Null
Write-Host 'Enabled: Sunday 20:00, Windows local time, while you are signed in. No AI service is invoked.'
