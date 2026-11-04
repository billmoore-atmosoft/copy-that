<# Install or remove a per-user startup shortcut. No Administrator needed. #>
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder 'CopyThat.lnk'
if ($Remove) {
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
    Write-Host 'CopyThat startup removed.'
    exit
}
$projectFolder = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectFolder '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run Start-Dictation.ps1 -Setup first.' }
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $PSHOME 'powershell.exe'
if (-not (Test-Path -LiteralPath $shortcut.TargetPath)) { $shortcut.TargetPath = Join-Path $PSHOME 'pwsh.exe' }
$shortcut.Arguments = '-NoProfile -WindowStyle Hidden -File "' + (Join-Path $projectFolder 'Start-Dictation.ps1') + '"'
$shortcut.WorkingDirectory = $projectFolder
$shortcut.Description = 'Offline local dictation'
$shortcut.Save()
Write-Host 'CopyThat will start at the next Windows sign-in.'
