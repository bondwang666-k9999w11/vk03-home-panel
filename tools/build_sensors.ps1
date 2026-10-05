param([string]$LibraryDirectory = '', [string]$OutputFile = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $LibraryDirectory) { $LibraryDirectory = Join-Path $projectRoot 'sensors' }
$library = Join-Path $LibraryDirectory 'LibreHardwareMonitorLib.dll'
$compiler = Join-Path $env:SystemRoot 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if (-not (Test-Path -LiteralPath $library)) { throw 'Missing official LHM library; see docs/CPU-SENSORS.md.' }
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Missing .NET Framework x64 compiler.' }
if (-not $OutputFile) { $OutputFile = Join-Path $projectRoot 'dist/sensors/VK03Sensors.exe' }
$output = [System.IO.Path]::GetFullPath($OutputFile)
New-Item -ItemType Directory -Path (Split-Path -Parent $output) -Force | Out-Null
$source = Join-Path $projectRoot 'sensors/VK03Sensors.cs'
& $compiler /nologo /target:winexe /platform:x64 ('/out:' + $output) ('/reference:' + $library) /reference:System.Web.Extensions.dll $source
if ($LASTEXITCODE -ne 0) { throw 'CPU helper compilation failed.' }
Copy-Item -LiteralPath (Join-Path $projectRoot 'sensors/VK03Sensors.exe.config') -Destination ($output + '.config') -Force
Write-Host 'CPU helper compiled. No driver was installed or hardware accessed.'
