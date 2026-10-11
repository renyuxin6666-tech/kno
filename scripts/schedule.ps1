param([switch]$Remove, [string]$TaskName = 'ObsidianKnowledgeWorkspace-Weekly', [ValidateSet('zh','en')][string]$Language = 'zh')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.runtime\venv\Scripts\python.exe'
$config = Join-Path $repo 'settings.local.json'
if (Test-Path -LiteralPath $config) {
    $saved = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($saved.language -in @('zh','en')) { $Language = $saved.language }
}
function Say([string]$Zh, [string]$En) {
    if ($Language -eq 'zh') { return $Zh }
    return $En
}
if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host (Say '已移除本机索引任务。知识库与原文件已保留。' 'Local indexing schedule removed. Your vault and sources are preserved.')
    exit
}
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $config)) {
    throw (Say '请先运行 Start.cmd 建立工作台，再启用本机索引任务。' 'Run Start.cmd to set up your workspace before enabling the local schedule.')
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw (Say '已有同名任务。请先检查已有任务，避免重复整理。' 'A task with this name already exists. Inspect it first to avoid duplicate upkeep.')
}
$pipeline = Join-Path $PSScriptRoot 'pipeline.py'
$arguments = '"' + $pipeline + '" refresh --config "' + $config + '"'
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '20:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 4)
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description (Say '每周刷新个人知识索引；保留原文件和个人笔记。' 'Refresh the personal knowledge index weekly; preserve originals and personal notes.') | Out-Null
Write-Host (Say '已启用本机索引：每周日 20:00，按 Windows 本地时间，在你登录时运行。需要 Agent 整理理解时，请另在 Codex 中设置定期任务。' 'Local indexing enabled: Sunday 20:00, Windows local time, while signed in. For Agent-written insights, configure a recurring task in Codex separately.')
