param(
    [string]$Source = '',
    [string]$Workspace = '',
    [string]$PythonExe = '',
    [string]$ObsidianExe = '',
    [ValidateSet('zh','en')][string]$Language = 'zh',
    [string]$VaultName = '',
    [string]$TimeZone = '',
    [switch]$SkipDependencies,
    [switch]$SkipOpen
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$config = Join-Path $repo 'settings.local.json'

function Say([string]$Zh, [string]$En) {
    if ($Language -eq 'zh') { return $Zh }
    return $En
}
if (Test-Path -LiteralPath $config) {
    $saved = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($saved.language -in @('zh','en')) { $Language = $saved.language }
}

function Find-Python {
    $candidates = @()
    if ($PythonExe) { $candidates += $PythonExe }
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { $candidates += $cmd.Source }
    foreach ($root in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore')) {
        if (Test-Path $root) {
            foreach ($version in Get-ChildItem $root) {
                $key = Join-Path $version.PSPath 'InstallPath'
                if (Test-Path $key) {
                    $location = (Get-Item $key).GetValue('')
                    if ($location) { $candidates += (Join-Path $location 'python.exe') }
                }
            }
        }
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return ''
}

function Find-Obsidian {
    $candidates = @()
    if ($ObsidianExe) { $candidates += $ObsidianExe }
    foreach ($process in Get-Process -Name Obsidian -ErrorAction SilentlyContinue) {
        if ($process.Path) { $candidates += $process.Path }
    }
    foreach ($root in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall')) {
        if (Test-Path $root) {
            foreach ($entry in Get-ChildItem $root | Get-ItemProperty -ErrorAction SilentlyContinue) {
                if ($entry.DisplayName -like 'Obsidian*') {
                    if ($entry.InstallLocation) { $candidates += (Join-Path $entry.InstallLocation 'Obsidian.exe') }
                    if ($entry.DisplayIcon) { $candidates += ($entry.DisplayIcon -replace ',\d+$','').Trim('"') }
                    if ($entry.UninstallString -match '^"?(.+?\.exe)"?(?:\s|$)') {
                        $candidates += (Join-Path (Split-Path -Parent $Matches[1]) 'Obsidian.exe')
                    }
                }
            }
        }
    }
    $candidates += (Join-Path $env:LOCALAPPDATA 'Obsidian\Obsidian.exe')
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe')
    $candidates += (Join-Path $env:ProgramFiles 'Obsidian\Obsidian.exe')
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return ''
}

function Install-Package([string]$Id) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw (Say '请从 Microsoft 安装“应用安装程序”，再运行 Start.cmd。当前系统未找到 Windows 包管理器。' 'Install Microsoft App Installer, then run Start.cmd again. Windows Package Manager is unavailable.') }
    & $winget.Source install --id $Id --exact --source winget --scope user --silent --no-upgrade --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw (Say "$Id 安装失败（退出码 $LASTEXITCODE）。请查看安装输出后重试。" "Installation failed for $Id (exit $LASTEXITCODE). Check the output and retry.") }
}

try {
    $python = Find-Python
    if (-not $python) {
        Write-Host (Say '正在为当前 Windows 用户安装 Python…' 'Installing Python for the current Windows user...')
        Install-Package 'Python.Python.3.12'
        $python = Find-Python
        if (-not $python) { throw (Say 'Python 已安装，但暂未找到。请重新打开 Start.cmd。' 'Python was installed but not detected. Reopen Start.cmd.') }
    }
    $obsidian = Find-Obsidian
    if (-not $obsidian) {
        Write-Host (Say '正在为当前 Windows 用户安装 Obsidian…' 'Installing Obsidian for the current Windows user...')
        Install-Package 'Obsidian.Obsidian'
        $obsidian = Find-Obsidian
        if (-not $obsidian) { throw (Say 'Obsidian 已安装，但暂未找到。请重新打开 Start.cmd。' 'Obsidian was installed but not detected. Reopen Start.cmd.') }
    }
    if (-not $SkipDependencies) {
        $venv = Join-Path $repo '.runtime\venv'
        $runtime = Join-Path $venv 'Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $runtime)) {
            & $python -m venv $venv
            if ($LASTEXITCODE -ne 0) { throw (Say '未能建立本地 Python 运行环境，请查看上方错误。' 'Could not create the local Python runtime; check the error above.') }
        }
        & $runtime -m pip install --disable-pip-version-check -r (Join-Path $repo 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw (Say '依赖安装失败，请检查网络后重试。' 'Dependency installation failed. Check network access and retry.') }
        $python = $runtime
    }
    $env:PYTHONUTF8 = '1'
    $pipeline = Join-Path $PSScriptRoot 'pipeline.py'
    if (Test-Path -LiteralPath $config) {
        & $python $pipeline refresh --config $config
    } else {
        if (-not $Source) {
            Add-Type -AssemblyName System.Windows.Forms
            $picker = New-Object System.Windows.Forms.FolderBrowserDialog
            $picker.Description = Say '选择你的资料文件夹：工作、学习、生活或研究资料都可以。原文件只读。' 'Choose a folder of work, learning, life or research material. Originals stay read-only.'
            $picker.ShowNewFolderButton = $false
            if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw (Say '尚未选择资料文件夹，可以稍后重新运行 Start.cmd。' 'No source folder selected. Run Start.cmd again when ready.') }
            $Source = $picker.SelectedPath
        }
        if (-not $Workspace) { $Workspace = Join-Path $repo '.runtime\workspace' }
        $setupArguments = @($pipeline, 'setup', '--source', $Source, '--workspace', $Workspace, '--obsidian', $obsidian, '--config', $config, '--language', $Language)
        if ($VaultName) { $setupArguments += @('--vault-name', $VaultName) }
        if ($TimeZone) { $setupArguments += @('--timezone', $TimeZone) }
        & $python @setupArguments
    }
    if ($LASTEXITCODE -ne 0) { throw (Say '知识工作台整理失败，请查看上方错误。' 'Knowledge workspace build failed; see the error above.') }
    if (-not $SkipOpen) {
        & $python $pipeline open --config $config
        if ($LASTEXITCODE -ne 0) { throw (Say '资料已整理好，Obsidian 打开入口需要处理，请查看上方提示。' 'Material is ready, but opening Obsidian needs attention; see the message above.') }
    }
    Write-Host (Say '完成。你的个人知识工作台已准备好：项目导航、来源入口、个人笔记和覆盖报告。' 'Done. Your personal knowledge workspace is ready: navigation, source links, personal notes and coverage report.') -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
