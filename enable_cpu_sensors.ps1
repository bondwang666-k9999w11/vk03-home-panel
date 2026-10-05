$ErrorActionPreference = 'Stop'
$root = 'C:\VK03'
function Report-Step($state, $message) {
    $data = @{state=$state;message=$message;timestamp=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()}
    $data | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'vk03_cpu_setup_status.json') -Encoding UTF8
    Add-Content -LiteralPath (Join-Path $root 'vk03_cpu_setup.log') -Value ((Get-Date -Format s) + ' ' + $message) -Encoding UTF8
    Write-Host $message
}
try {
    Add-Type -AssemblyName System.Windows.Forms
    Report-Step 'starting' 'Setup script started. Checking administrator rights.'
    $owner = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $admin = ([System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) {
        Report-Step 'authorizing' 'Requesting administrator permission.'
        Start-Process powershell.exe -Verb RunAs -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '"') -WindowStyle Hidden -ErrorAction Stop
        exit
    }
    $helper = Join-Path $root 'sensors\VK03Sensors.exe'
    $setup = Join-Path $root 'sensors\PawnIO_setup.exe'
    if (-not (Test-Path -LiteralPath $helper)) { throw ('Missing CPU collector: ' + $helper) }
    if (-not (Get-Service -Name PawnIO -ErrorAction SilentlyContinue)) {
        if (-not (Test-Path -LiteralPath $setup)) { throw ('Missing driver installer: ' + $setup) }
        if ((Get-AuthenticodeSignature -LiteralPath $setup).Status -ne 'Valid') { throw 'PawnIO installer signature is invalid.' }
        Report-Step 'installing' 'Opening PawnIO installer. Please complete installation.'
        [System.Windows.Forms.MessageBox]::Show('Click OK to open the bundled PawnIO installer. No download is needed. Windows may skip the permission prompt if you already have administrator rights.','VK03 CPU temperature setup') | Out-Null
        $installer=Start-Process -FilePath $setup -WindowStyle Normal -Wait -PassThru -ErrorAction Stop
        if ($installer.ExitCode -notin @(0,3010)) { throw ('Driver installer exit code: ' + $installer.ExitCode) }
    }
    if (-not (Get-Service -Name PawnIO -ErrorAction SilentlyContinue)) { throw 'PawnIO driver was not detected. Complete the driver installation and try again.' }
    Report-Step 'configuring' 'Creating the CPU temperature collector task.'
    $action = New-ScheduledTaskAction -Execute $helper -WorkingDirectory (Join-Path $root 'sensors')
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $owner
    $principal = New-ScheduledTaskPrincipal -UserId $owner -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName 'VK03 CPU Sensors' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName 'VK03 CPU Sensors'
    Report-Step 'success' 'CPU collector task started. Temperature availability depends on driver and hardware support.'
    [System.Windows.Forms.MessageBox]::Show('CPU collector task started. If temperature still shows --, check C:\VK03\vk03_cpu_sensor.json.','VK03') | Out-Null
} catch {
    $message=$_.Exception.Message
    try { Report-Step 'error' $message } catch { }
    Write-Host $message -ForegroundColor Red
    try { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show($message,'VK03 CPU setup failed') | Out-Null } catch { }
    exit 1
}
