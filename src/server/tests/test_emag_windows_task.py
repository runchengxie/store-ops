"""Contract tests for the optional Windows eMAG task entry point."""
import json
from pathlib import Path
import shutil
import subprocess
import os

import pytest

ROOT = Path(__file__).resolve().parents[3]
PWSH = shutil.which('pwsh')
pytestmark = pytest.mark.skipif(not PWSH, reason='PowerShell unavailable')


def invoke(*args):
    return subprocess.run(
        [PWSH, '-NoProfile', '-File', str(ROOT / 'scripts/emag-ssh-task.ps1'), *args],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20,
    )


def test_plan_has_no_trigger_and_fixed_readonly_command():
    result = invoke('-Action', 'plan', '-StoreId', 'example-ro')
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan['task_name'] == 'ivyeaops-emag-example-ro'
    assert plan['store_id'] == 'example-ro'
    assert plan['scheduled'] is False
    assert plan['mode'] == 'fresh_collection'


@pytest.mark.parametrize('store', ['../outside', 'a b', 'x;echo'])
def test_rejects_unsafe_store_id(store):
    assert invoke('-Action', 'plan', '-StoreId', store).returncode != 0


def test_run_rejects_days_override():
    assert invoke('-Action', 'run', '-StoreId', 'example-ro', '-Days', '7').returncode != 0


@pytest.mark.skipif(os.name != 'nt', reason='Windows task behavior')
@pytest.mark.parametrize('behavior', ['fresh', 'paused', 'no_receipt', 'foreign', 'triggered'])
def test_task_receipt_and_ownership_boundaries(tmp_path, behavior):
    script = ROOT / 'scripts/emag-ssh-task.ps1'
    env = os.environ.copy()
    env.update(LOCALAPPDATA=str(tmp_path), TEST_SCRIPT=str(script), TEST_BEHAVIOR=behavior)
    code = r'''
$global:started = $false
function Get-ScheduledTask {
    param($TaskName,$TaskPath)
    $args = '-NoProfile -NonInteractive -File "{0}" -Action worker -StoreId "example-ro" -Days 29' -f $env:TEST_SCRIPT
    $description = if ($env:TEST_BEHAVIOR -eq 'foreign') { 'other task' } else { 'ivyeaops managed eMAG SSH task v1' }
    $triggers = if ($env:TEST_BEHAVIOR -eq 'triggered') { @('unexpected') } else { @() }
    [pscustomobject]@{Description=$description; State='Ready'; Triggers=$triggers; Principal=[pscustomobject]@{LogonType='Interactive'; UserId=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name}; Actions=@([pscustomobject]@{Execute='pwsh.exe'; Arguments=$args})}
}
function Get-ScheduledTaskInfo {
    param($TaskName,$TaskPath)
    $date = if ($global:started) { [datetime]'2026-01-02' } else { [datetime]'2026-01-01' }
    [pscustomobject]@{LastRunTime=$date; LastTaskResult=1}
}
function Start-ScheduledTask {
    param($TaskName,$TaskPath)
    $global:started = $true
    if ($env:TEST_BEHAVIOR -in @('fresh','paused')) {
        $dir=Join-Path $env:LOCALAPPDATA 'ivyeaops/emag-ssh-task/example-ro'
        @{store_id='example-ro';run_id='new';status=$(if($env:TEST_BEHAVIOR -eq 'paused'){'paused'}else{'complete'})} | ConvertTo-Json -Compress | Set-Content (Join-Path $dir 'last-run.json')
    }
}
& $env:TEST_SCRIPT -Action run -StoreId example-ro -TimeoutSeconds 3
'''
    result = subprocess.run([PWSH, '-NoProfile', '-Command', code], env=env, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=15)
    if behavior in ('fresh','paused'):
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['run_id'] == 'new'
    else:
        assert result.returncode != 0
        assert ('without a new receipt' if behavior == 'no_receipt' else 'ownership or action') in result.stderr
