param([switch]$EnableActions)
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
Add-Type -Path (Join-Path $PSScriptRoot 'windows-native.cs')
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$script:manager=$null
$script:taskMethod=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 -and $_.GetGenericArguments().Count -eq 1 } | Select-Object -First 1
function Await-Operation($Operation,[Type]$ResultType) {
 $task=$script:taskMethod.MakeGenericMethod($ResultType).Invoke($null,@($Operation))
 if(-not $task.Wait(3000)){throw 'Windows media operation timed out'}
 return $task.GetAwaiter().GetResult()
}
function Get-MediaSession {
 if($null -eq $script:manager){$script:manager=Await-Operation ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media,ContentType=WindowsRuntime]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media,ContentType=WindowsRuntime])}
 return $script:manager.GetCurrentSession()
}
function Get-Snapshot {
 $result=@{volume=$null;muted=$null;media=$null;errors=@();actionsEnabled=[bool]$EnableActions}
 try{$result.volume=[VK03RE.Audio]::GetVolume();$result.muted=[VK03RE.Audio]::GetMute()}catch{$result.errors+=@{component='volume';message=$_.Exception.GetBaseException().Message}}
 try{
  $session=Get-MediaSession
  if($null -eq $session){$result.media=@{available=$false;reason='no_active_session'}}
  else{
   $props=Await-Operation ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties,Windows.Media,ContentType=WindowsRuntime])
   $info=$session.GetPlaybackInfo();$controls=$info.Controls
   $result.media=@{available=$true;title=$props.Title;artist=$props.Artist;status=$info.PlaybackStatus.ToString();source=$session.SourceAppUserModelId;capabilities=@{play=$controls.IsPlayEnabled;pause=$controls.IsPauseEnabled;previous=$controls.IsPreviousEnabled;next=$controls.IsNextEnabled}}
  }
 }catch{$script:manager=$null;$result.errors+=@{component='media';message=$_.Exception.GetBaseException().Message}}
 try{
  $smi=Join-Path $env:SystemRoot 'System32\nvidia-smi.exe'
  if(Test-Path -LiteralPath $smi){
   $info=New-Object Diagnostics.ProcessStartInfo;$info.FileName=$smi;$info.Arguments='--query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader,nounits --id=0';$info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
   $proc=[Diagnostics.Process]::Start($info)
   if($proc.WaitForExit(1000)){$fields=$proc.StandardOutput.ReadToEnd().Trim().Split(',');if($proc.ExitCode -eq 0 -and $fields.Count -ge 2){$result.gpu_temp=[double]$fields[0].Trim();$result.gpu=[double]$fields[1].Trim()}}else{$proc.Kill()}
   $proc.Dispose()
  }
 }catch{}
 try{
  $temps=Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -OperationTimeoutSec 1 -ErrorAction Stop | Where-Object {$_.SensorType -eq 'Temperature' -and $_.Identifier -match 'cpu' -and $_.Name -match 'Package|Tctl|Tdie|Core Max'}
  if($temps){$result.cpu_temp=($temps | Measure-Object -Property Value -Maximum).Maximum}
 }catch{}
 return $result
}
while($null -ne ($line=[Console]::ReadLine())){
 $request=$null
 try{
  if($line.Length -gt 8192){throw 'Request too large'}
  $request=$line | ConvertFrom-Json
  if($request.id -isnot [string] -or $request.id.Length -gt 80){throw 'Invalid request id'}
  $payload=$request.payload;$value=$null
  switch -Exact ($request.action){
   'health' {$value=@{protocol=1;actionsEnabled=[bool]$EnableActions;usb=$false}}
   'state.get' {$value=Get-Snapshot}
   'volume.muteToggle' {
    if(-not $EnableActions){throw 'Actions disabled in read-only mode'}
    $value=@{muted=[VK03RE.Audio]::ToggleMute();volume=[VK03RE.Audio]::GetVolume()}
   }
   {$_ -in @('system.shutdown','system.restart')} {
    if(-not $EnableActions){throw 'Actions disabled in read-only mode'}
    if($payload.confirmed -isnot [bool] -or -not $payload.confirmed){throw 'Explicit power confirmation required'}
    $powerInfo=[Diagnostics.ProcessStartInfo]::new();$powerInfo.FileName=Join-Path $env:SystemRoot 'System32\shutdown.exe';$powerInfo.UseShellExecute=$false;$powerInfo.CreateNoWindow=$true
    $powerInfo.Arguments=if($request.action -eq 'system.shutdown'){'/s /t 0'}else{'/r /t 0'}
    $powerProcess=[Diagnostics.Process]::Start($powerInfo);try{$powerProcess.WaitForExit();if($powerProcess.ExitCode -ne 0){throw ('Windows power request failed: '+$powerProcess.ExitCode)}}finally{$powerProcess.Dispose()}
    $value=@{accepted=$true}
   }
   'volume.set' {
    if(-not $EnableActions){throw 'Actions disabled in read-only mode'}
    if($payload.value -isnot [ValueType] -or $payload.value -is [bool]){throw 'Volume must be a number'}
    $value=@{volume=[VK03RE.Audio]::SetVolume([double]$payload.value)}
   }
   {$_ -in @('media.play','media.pause','media.previous','media.next')} {
    if(-not $EnableActions){throw 'Actions disabled in read-only mode'}
    $session=Get-MediaSession;if($null -eq $session){throw 'No active Windows media session'}
    $controls=$session.GetPlaybackInfo().Controls
    switch -Exact ($request.action){
     'media.play' {if(-not $controls.IsPlayEnabled){throw 'Player does not support play'};$op=$session.TryPlayAsync()}
     'media.pause' {if(-not $controls.IsPauseEnabled){throw 'Player does not support pause'};$op=$session.TryPauseAsync()}
     'media.previous' {if(-not $controls.IsPreviousEnabled){throw 'Player does not support previous'};$op=$session.TrySkipPreviousAsync()}
     'media.next' {if(-not $controls.IsNextEnabled){throw 'Player does not support next'};$op=$session.TrySkipNextAsync()}
    }
    $done=Await-Operation $op ([bool]);if(-not $done){throw 'Player declined media operation'};$value=@{accepted=$true}
   }
   default {throw 'Unsupported native action'}
  }
  $response=@{id=$request.id;ok=$true;value=$value}
 }catch{$response=@{id=if($null -eq $request){$null}else{$request.id};ok=$false;error=$_.Exception.GetBaseException().Message}}
 [Console]::WriteLine(($response | ConvertTo-Json -Depth 8 -Compress))
}
