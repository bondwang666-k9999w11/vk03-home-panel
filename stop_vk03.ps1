$ErrorActionPreference = 'Stop'
function Get-VK03Processes {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @('python.exe', 'pythonw.exe') -and
        $_.CommandLine -match '(?i)(?:^|[\\/"\s])vk03_(?:launcher|home_panel_daily|home_panel)\.py(?:"|\s|$)'
    })
}
try {
    $processes = Get-VK03Processes
    $directories = @($PSScriptRoot, 'C:\VK03')
    foreach ($process in $processes) {
        $match = [regex]::Match($process.CommandLine, '(?i)"([^"\r\n]*[\\/]vk03_(?:launcher|home_panel_daily|home_panel)\.py)"')
        if (-not $match.Success) {
            $match = [regex]::Match($process.CommandLine, '(?i)([A-Z]:\\[^\s"]*[\\/]vk03_(?:launcher|home_panel_daily|home_panel)\.py)')
        }
        if ($match.Success) { $directories += Split-Path $match.Groups[1].Value }
    }
    foreach ($directory in ($directories | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $directory) {
            New-Item -ItemType File -Path (Join-Path $directory 'vk03_stop.flag') -Force | Out-Null
            New-Item -ItemType File -Path (Join-Path $directory 'vk03_sensors_stop.flag') -Force | Out-Null
        }
    }
    for ($count = 0; $count -lt 15; $count++) {
        if (-not (Get-VK03Processes).Count) { break }
        Start-Sleep -Seconds 1
    }
    $remaining = Get-VK03Processes
    # Stop launchers first, so they cannot restart the panel after termination.
    foreach ($process in ($remaining | Sort-Object @{ Expression = {
        if ($_.CommandLine -match 'vk03_launcher\.py') { 0 } else { 1 }
    }})) {
        $current = Get-VK03Processes | Where-Object { $_.ProcessId -eq $process.ProcessId -and $_.CreationDate -eq $process.CreationDate }
        if ($current) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-Host ('Stopped remaining VK03 process: ' + $process.ProcessId)
        }
    }
    if ((Get-VK03Processes).Count) { throw 'VK03 is still running. Please send this output.' }
    Write-Host 'VK03 stopped. The screen may retain its last image; touch controls should no longer respond.'
    Write-Host 'You can now start VK03 using the desktop shortcut pointing to C:\VK03.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
