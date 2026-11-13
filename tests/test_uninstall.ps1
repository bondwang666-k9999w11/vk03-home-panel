$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
[Reflection.Assembly]::LoadFile((Join-Path $project 'uninstall.exe'))|Out-Null
$base=[IO.Path]::GetFullPath($PSScriptRoot)
function Fixture([string]$name,[bool]$extra){
 $root=Join-Path $base ($name+'-'+[Guid]::NewGuid().ToString('N'))
 if(-not $root.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Fixture outside workspace'}
 New-Item -ItemType Directory -Path (Join-Path $root '_internal') -Force|Out-Null
 [IO.File]::WriteAllText((Join-Path $root 'VK03Studio.exe'),'test fixture only')
 [IO.File]::WriteAllText((Join-Path $root '_internal\sample.dll'),'test fixture only')
 [IO.File]::WriteAllText((Join-Path $root 'studio-package.json'),'{"packageId":"ef41513d-174c-48d8-9ba6-9d5cc919c87f"}')
 $manifest=@{}
 foreach($name in @('VK03Studio.exe','_internal/sample.dll','studio-package.json')){$manifest[$name]=[VK03StudioRemoval.Removal]::Hash((Join-Path $root $name))}
 if($extra){[IO.File]::WriteAllText((Join-Path $root 'changed.txt'),'original');$manifest['changed.txt']=[VK03StudioRemoval.Removal]::Hash((Join-Path $root 'changed.txt'));[IO.File]::WriteAllText((Join-Path $root 'changed.txt'),'user changed');[IO.File]::WriteAllText((Join-Path $root 'user-notes.txt'),'keep personal data')}
 [IO.File]::WriteAllText((Join-Path $root 'files.sha256.json'),($manifest|ConvertTo-Json))
 return $root
}
$root=Fixture 'uninstall-test' $true
$original=[IO.File]::ReadAllText((Join-Path $root 'files.sha256.json'))
[IO.File]::WriteAllText((Join-Path $root 'files.sha256.json'),('{"../outside.txt":"'+('0'*64)+'"}'))
$rejected=$false;try{[VK03StudioRemoval.Removal]::Plan($root)|Out-Null}catch{$rejected=$true};if(-not $rejected){throw 'Traversal not rejected'}
if(-not (Test-Path -LiteralPath (Join-Path $root 'VK03Studio.exe'))){throw 'Rejection removed a file'}
[IO.File]::WriteAllText((Join-Path $root 'files.sha256.json'),$original)
$result=[VK03StudioRemoval.Removal]::RemoveManaged($root)
if($result.Removed -ne 3 -or $result.Retained -ne 1){throw 'Managed file removal mismatch'}
foreach($name in @('changed.txt','user-notes.txt')){if(-not (Test-Path -LiteralPath (Join-Path $root $name))){throw 'User file lost'}}
$clean=Fixture 'uninstall-clean-test' $false
$result=[VK03StudioRemoval.Removal]::RemoveManaged($clean)
if(-not $result.DirectoryRemoved -or (Test-Path -LiteralPath $clean)){throw 'Empty directory not removed'}
$rejected=$false;try{[VK03StudioRemoval.Removal]::Plan('C:\VK03')|Out-Null}catch{$rejected=$true};if(-not $rejected){throw 'Protected directory accepted'}
Write-Output 'PASS uninstall fixtures: owned files removed, user/modified files retained, traversal/protected roots rejected, no recursive deletion'
