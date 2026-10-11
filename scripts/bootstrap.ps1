param(
    [string]$Source = '',
    [string]$Workspace = '',
    [string]$PythonExe = '',
    [string]$ObsidianExe = '',
    [switch]$SkipDependencies,
    [switch]$SkipOpen
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$config = Join-Path $repo 'settings.local.json'

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
    if (-not $winget) { throw 'Windows Package Manager is unavailable. Install App Installer from Microsoft, then run Start.cmd again.' }
    & $winget.Source install --id $Id --exact --source winget --scope user --silent --no-upgrade --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Installation failed for $Id (exit $LASTEXITCODE). Check the installer output and rerun." }
}

try {
    $python = Find-Python
    if (-not $python) {
        Write-Host 'Installing Python for the current Windows user...'
        Install-Package 'Python.Python.3.12'
        $python = Find-Python
        if (-not $python) { throw 'Python was installed but not detected. Reopen this launcher.' }
    }
    $obsidian = Find-Obsidian
    if (-not $obsidian) {
        Write-Host 'Installing Obsidian for the current Windows user...'
        Install-Package 'Obsidian.Obsidian'
        $obsidian = Find-Obsidian
        if (-not $obsidian) { throw 'Obsidian was installed but not detected.' }
    }
    if (-not $SkipDependencies) {
        $venv = Join-Path $repo '.runtime\venv'
        $runtime = Join-Path $venv 'Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $runtime)) {
            & $python -m venv $venv
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python runtime.' }
        }
        & $runtime -m pip install --disable-pip-version-check -r (Join-Path $repo 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network access and retry.' }
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
            $picker.Description = 'Choose your research SOURCE folder. Originals stay read-only.'
            $picker.ShowNewFolderButton = $false
            if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'No source folder selected.' }
            $Source = $picker.SelectedPath
        }
        if (-not $Workspace) { $Workspace = Join-Path $repo '.runtime\workspace' }
        & $python $pipeline setup --source $Source --workspace $Workspace --obsidian $obsidian --config $config
    }
    if ($LASTEXITCODE -ne 0) { throw 'Knowledge-base build failed; see output above.' }
    if (-not $SkipOpen) {
        & $python $pipeline open --config $config
        if ($LASTEXITCODE -ne 0) { throw 'Build succeeded, but opening Obsidian needs attention; see output above.' }
    }
    Write-Host 'Done. Your sources, generated navigation, personal notes and coverage report are ready.' -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
