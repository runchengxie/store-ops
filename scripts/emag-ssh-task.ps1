param(
    [Parameter(Mandatory)][ValidateSet('plan','install','run','status','uninstall','worker')][string]$Action,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')][string]$StoreId,
    [ValidateRange(1,29)][int]$Days = 29,
    [ValidateRange(1,900)][int]$TimeoutSeconds = 180
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$server = Join-Path $root 'src/server'
$python = Join-Path $server '.venv/Scripts/python.exe'
$taskName = "ivyeaops-emag-$StoreId"
$marker = 'ivyeaops managed eMAG SSH task v1'
if ($Action -notin @('plan','install','worker') -and $PSBoundParameters.ContainsKey('Days')) {
    throw 'Days is fixed when installing the task; reinstall to change it.'
}

function Get-OwnedTask {
    $task = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
    $expected = '-NoProfile -NonInteractive -File "{0}" -Action worker -StoreId "{1}" -Days ' -f $PSCommandPath,$StoreId
    $actions = @($task.Actions)
    $userSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    try { $taskSid = ([System.Security.Principal.NTAccount]::new($task.Principal.UserId)).Translate([System.Security.Principal.SecurityIdentifier]).Value }
    catch { throw 'Task account cannot be verified.' }
    $triggers = @($task.Triggers | Where-Object { $null -ne $_ })
    if ($task.Description -ne $marker -or $actions.Count -ne 1 -or
        $triggers.Count -ne 0 -or $task.Principal.LogonType -ne 'Interactive' -or
        $taskSid -ne $userSid -or
        -not $actions[0].Arguments.StartsWith($expected, [StringComparison]::OrdinalIgnoreCase) -or
        $actions[0].Arguments.Substring($expected.Length) -notmatch '^(?:[1-9]|1[0-9]|2[0-9])$' -or
        [IO.Path]::GetFileName($actions[0].Execute) -notin @('pwsh.exe','pwsh')) {
        throw 'Task ownership or action does not match this integration.'
    }
    return $task
}

if ($Action -eq 'plan') {
    @{task_name=$taskName; store_id=$StoreId; scheduled=$false; mode='fresh_collection'; days=$Days} |
        ConvertTo-Json -Compress
    exit 0
}
if (-not $IsWindows) { throw 'This integration requires Windows.' }
$receiptDir = Join-Path $env:LOCALAPPDATA "ivyeaops/emag-ssh-task/$StoreId"
$receiptPath = Join-Path $receiptDir 'last-run.json'

switch ($Action) {
    'install' {
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Server Python environment is unavailable.' }
        if (Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue) {
            throw 'Task already exists; refusing to overwrite it.'
        }
        $shell = (Get-Process -Id $PID).Path
        $arguments = '-NoProfile -NonInteractive -File "{0}" -Action worker -StoreId "{1}" -Days {2}' -f $PSCommandPath,$StoreId,$Days
        $taskAction = New-ScheduledTaskAction -Execute $shell -Argument $arguments
        $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
        Register-ScheduledTask -TaskName $taskName -TaskPath '\' -Action $taskAction -Principal $principal -Settings $settings -Description $marker | Out-Null
        Write-Output 'Installed manual task; no scheduled triggers were created.'
    }
    'worker' {
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Server Python environment is unavailable.' }
        New-Item -ItemType Directory -Path $receiptDir -Force | Out-Null
        $env:PYTHONIOENCODING = 'utf-8'
        Push-Location $server
        try {
            $output = & $python -m app.emag_job_cli --store-id $StoreId --days $Days
            $code = $LASTEXITCODE
        } finally { Pop-Location }
        $text = $output | Out-String
        try { $receipt = $text | ConvertFrom-Json } catch { $receipt = $null }
        if ($null -eq $receipt -and $code -ne 0) {
            $receipt = @{store_id=$StoreId; run_id=[guid]::NewGuid().ToString(); status='failed'; stage='task_runner'; error_type='JobUnavailable'}
            $text = $receipt | ConvertTo-Json -Compress
        }
        if ($receipt.store_id -ne $StoreId -or -not $receipt.run_id) { throw 'Invalid job receipt.' }
        $tmp = Join-Path $receiptDir ([guid]::NewGuid().ToString() + '.tmp')
        [System.IO.File]::WriteAllText($tmp,$text,[System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $tmp -Destination $receiptPath -Force
        exit $code
    }
    'status' {
        $task = Get-OwnedTask
        $info = Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\'
        $receipt = if (Test-Path -LiteralPath $receiptPath) { Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json } else { $null }
        @{task_name=$taskName; state=[string]$task.State; last_run_time=$info.LastRunTime; last_task_result=$info.LastTaskResult; receipt=$receipt} | ConvertTo-Json -Depth 20
    }
    'run' {
        New-Item -ItemType Directory -Path $receiptDir -Force | Out-Null
        try { $lock = [IO.File]::Open((Join-Path $receiptDir 'trigger.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
        catch { throw 'Another caller is triggering this task.' }
        try {
            $task = Get-OwnedTask
            if ($task.State -eq 'Running') { throw 'Task is already running.' }
            $before = Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\'
            $oldId = if (Test-Path -LiteralPath $receiptPath) { (Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json).run_id } else { '' }
            Start-ScheduledTask -TaskName $taskName -TaskPath '\'
            $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
            do {
                Start-Sleep -Seconds 1
                if (Test-Path -LiteralPath $receiptPath) {
                    $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
                    if ($receipt.run_id -ne $oldId) {
                        $receipt | ConvertTo-Json -Depth 20
                        if ($receipt.status -notin @('complete','paused')) { exit 1 }
                        exit 0
                    }
                }
                $task = Get-OwnedTask
                $info = Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\'
                if ($info.LastRunTime -gt $before.LastRunTime -and $task.State -eq 'Ready' -and $info.LastTaskResult -ne 267009) {
                    throw "Task finished without a new receipt (task result: $($info.LastTaskResult))."
                }
            } while ([DateTime]::UtcNow -lt $deadline)
            throw 'No new receipt before timeout; check task status before retrying.'
        } finally { $lock.Dispose() }
    }
    'uninstall' {
        $task = Get-OwnedTask
        if ($task.State -eq 'Running') { throw 'Task is running; wait before uninstalling.' }
        Unregister-ScheduledTask -TaskName $taskName -TaskPath '\' -Confirm:$false
        Write-Output 'Removed managed task; data and credentials were retained.'
    }
}
