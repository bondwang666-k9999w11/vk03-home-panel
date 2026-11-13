$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$python=Join-Path $root '.venv\Scripts\python.exe'
$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$uninstaller=Join-Path $root 'uninstall.exe'
$uninstallSource=Join-Path $root 'Uninstall.cs'
if((-not (Test-Path -LiteralPath $uninstaller)) -or ((Get-Item -LiteralPath $uninstallSource).LastWriteTimeUtc -gt (Get-Item -LiteralPath $uninstaller).LastWriteTimeUtc)){
& $csc /nologo /target:winexe ('/out:'+(Join-Path $root 'uninstall.exe')) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll (Join-Path $root 'Uninstall.cs')
if($LASTEXITCODE -ne 0){throw 'Uninstaller build failed'}
}
& $python -m PyInstaller --noconfirm --distpath (Join-Path $root 'dist-0.2.1') --workpath (Join-Path $root 'build') (Join-Path $root 'VK03Studio.spec')
if($LASTEXITCODE -ne 0){throw 'Application build failed'}
& $python (Join-Path $root 'package.py')
if($LASTEXITCODE -ne 0){throw 'Packaging failed'}
