param(
    [string]$MonitorDir,
    [string]$VbsPath
)

$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$VbsPath`"" -WorkingDirectory $MonitorDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -GroupId 'BUILTIN\Users' -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0 -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'WindowsMonitor' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'WindowsMonitor'
Write-Host "  OK - Task created"
Write-Host "  Execute:" $t.Actions[0].Execute $t.Actions[0].Arguments
