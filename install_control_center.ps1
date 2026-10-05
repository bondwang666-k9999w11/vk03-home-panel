$ErrorActionPreference = 'Stop'
try {
    $installDir = 'C:\VK03'
    $exePath = Join-Path $installDir 'VK03控制中心.exe'
    foreach ($name in @('VK03控制中心.exe','vk03_home_panel_daily.py','vk03_launcher.py','vk03_theme.py','vk03_media.py','vk03_monitor.py','vk03_config.py','vk03_device_setup.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $installDir $name))) { throw ('Missing file in C:\VK03: ' + $name) }
    }
    $shell = New-Object -ComObject WScript.Shell
    foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Startup'))) {
        $shortcut = $shell.CreateShortcut((Join-Path $folder 'VK03面板.lnk'))
        $shortcut.TargetPath = $exePath
        $shortcut.WorkingDirectory = $installDir
        $shortcut.Arguments = ''
        if ($folder -eq [Environment]::GetFolderPath('Startup')) { $shortcut.Arguments = '--background' }
        $shortcut.Save()
    }
    Write-Host 'Desktop shortcut and login startup now use C:\VK03\VK03 control center.'
    Write-Host 'Open the desktop shortcut to start the panel and edit its appearance.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
