param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & $Python tools/check_public_tree.py
    if ($LASTEXITCODE -ne 0) { throw 'Privacy audit failed.' }
    & $Python -m PyInstaller --noconfirm --onedir --windowed --name 'VK03ControlCenter' --distpath dist --workpath build --specpath build --paths . --hidden-import pystray._win32 --hidden-import vk03_monitor --hidden-import vk03_config --hidden-import vk03_device_setup vk03_app.py
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
    # Construct the localized file name without non-ASCII PowerShell source.
    $localized = 'VK03' + [char]0x63A7 + [char]0x5236 + [char]0x4E2D + [char]0x5FC3 + '.exe'
    Move-Item -LiteralPath 'dist/VK03ControlCenter/VK03ControlCenter.exe' -Destination (Join-Path 'dist/VK03ControlCenter' $localized) -Force
    Write-Host 'Control center built in dist.'
} finally { Pop-Location }
