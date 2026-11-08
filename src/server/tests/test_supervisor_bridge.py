import json

import pytest

from app.services import automation_control
from app.services import supervisor_bridge as bridge

JOB = 'a' * 32


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    # Other suites reload config; patch both the worker's captured settings and
    # the current settings resolved by existing artifact services.
    from app.core.config import settings
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    monkeypatch.setattr(bridge.settings, 'data_dir', tmp_path)
    monkeypatch.setenv('IVYEA_OPS_SUPERVISOR_ACCOUNT_STORE_ID', 'shop')


def test_claim_precedes_work_and_replay_does_not_run():
    def worker(store, collect):
        assert json.loads(bridge._path(JOB).read_text())['status'] == 'running'
        return {'store_id': store, 'run_id': 'b' * 32, 'status': 'complete'}
    result = bridge.run('shop', JOB, run_fn=worker, collect_fn=lambda: {})
    assert result == {'job_id': JOB, 'store_id': 'shop', 'status': 'complete', 'receipt_id': 'b' * 32}
    assert bridge.run('shop', JOB, run_fn=lambda *_: pytest.fail('replayed')) == result


def test_unknown_execution_never_restarts():
    def crash(*args):
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        bridge.run('shop', JOB, run_fn=crash)
    assert bridge.receipt('shop', JOB)['status'] == 'unknown'
    assert bridge.run('shop', JOB, run_fn=lambda *_: pytest.fail('replayed'))['status'] == 'unknown'


def test_identity_and_malformed_record_fail_closed():
    bridge.run('shop', JOB, run_fn=lambda *_: {'store_id': 'shop', 'run_id': 'b' * 32, 'status': 'paused'})
    with pytest.raises(ValueError):
        bridge.cancel('other', JOB)
    bridge._path(JOB).write_text('{bad')
    with pytest.raises(ValueError):
        bridge.receipt('shop', JOB)


def test_cancellation_uses_checkpoint_without_store_pause():
    def worker(store, collect):
        bridge.cancel(store, JOB)
        with pytest.raises(automation_control.Paused):
            automation_control.checkpoint()
        assert not automation_control.view(store)['paused']
        return {'store_id': store, 'run_id': 'b' * 32, 'status': 'paused'}
    assert bridge.run('shop', JOB, run_fn=worker)['status'] == 'paused'
    automation_control.checkpoint()


@pytest.mark.parametrize('store,job', [('../x', JOB), ('shop', '../x'), ('shop', 'a' * 31), ('shop', 'A' * 32)])
def test_reject_invalid_identity(store, job):
    with pytest.raises(ValueError):
        bridge.run(store, job)


def test_missing_receipt_unknown_and_cancel_records_preclaim_intent():
    assert bridge.receipt('shop', JOB)['status'] == 'unknown'
    assert bridge.cancel('shop', JOB)['cancel_requested'] is True
    assert not bridge._path(JOB).exists()


def test_wrong_worker_identity_keeps_unknown():
    assert bridge.run('shop', JOB, run_fn=lambda *_: {'store_id': 'other', 'run_id': 'b'*32, 'status': 'complete'})['status'] == 'unknown'


def test_real_job_cancel_stops_before_publication(monkeypatch):
    from app.services import emag_business
    published = []
    monkeypatch.setattr(emag_business, 'publish', lambda *args: published.append(args))
    def collect():
        bridge.cancel('shop', JOB)
        return {}
    result = bridge.run('shop', JOB, collect_fn=collect)
    assert result['status'] == 'paused'
    assert published == []
    assert not automation_control.view('shop')['paused']
    assert bridge.receipt('shop', JOB) == result


def test_paused_real_job_never_collects():
    automation_control.set_paused('shop', True, 0, 'test')
    assert bridge.run('shop', JOB, collect_fn=lambda: pytest.fail('paused collection'))['status'] == 'paused'


def test_crossprocess_duplicate_and_cancel(tmp_path):
    import subprocess
    import sys
    import time
    code = '''
import sys, time
from pathlib import Path
from app.core.config import settings
from app.services import supervisor_bridge as b, automation_control as a
settings.data_dir = Path(sys.argv[1])
def worker(store, collect):
    while True:
        try: a.checkpoint()
        except a.Paused: return {'store_id': store, 'run_id': 'b'*32, 'status': 'paused'}
        time.sleep(.01)
b.run('shop', 'a'*32, run_fn=worker)
'''
    process = subprocess.Popen([sys.executable, '-c', code, str(tmp_path)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while not bridge._path(JOB).exists() and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(.01)
        assert bridge.receipt('shop', JOB)['status'] == 'running'
        assert bridge.run('shop', JOB, run_fn=lambda *_: pytest.fail('duplicate'))['status'] == 'running'
        bridge.cancel('shop', JOB)
        _, err = process.communicate(timeout=10)
        assert process.returncode == 0, err.decode()
        assert bridge.receipt('shop', JOB)['status'] == 'paused'
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def test_cli_bounds_output_and_hides_exception(monkeypatch, capsys):
    from app import supervisor_bridge as cli
    def worker(*args):
        print('secret credential noise')
        raise ValueError('secret credential exception')
    monkeypatch.setattr(bridge, 'run', worker)
    assert cli.main(['--action', 'run', '--store-id', 'shop', '--job-id', JOB]) == 2
    assert capsys.readouterr().out == '{"error":"bridge_unavailable"}\n'


@pytest.mark.parametrize('args', [
    ['--action', 'shell', '--store-id', 'shop'],
    ['--action', 'run', '--store-id', 'shop'],
    ['--action', 'status', '--store-id', 'shop', '--job-id', JOB],
    ['--action', 'status', '--store-id', 'shop', '--command', 'echo'],
])
def test_cli_rejects_arbitrary_arguments(args):
    from app import supervisor_bridge as cli
    with pytest.raises(SystemExit):
        cli.main(args)


@pytest.mark.parametrize('update', [{'status': []}, {'receipt_id': '../outside'}, {'extra': 'private'}, {'status': 'complete'}])
def test_malformed_record_never_allows_work(update):
    path = bridge._path(JOB)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'job_id': JOB, 'store_id': 'shop', 'status': 'running', **update}))
    with pytest.raises(ValueError):
        bridge.run('shop', JOB, run_fn=lambda *_: pytest.fail('invalid metadata executed'))


def test_cli_single_success_json_and_rejects_oversize(monkeypatch, capsys):
    from app import supervisor_bridge as cli
    def worker(*args):
        print('worker noise must be discarded')
        return {'job_id': JOB, 'store_id': 'shop', 'status': 'paused', 'receipt_id': 'b'*32}
    monkeypatch.setattr(bridge, 'run', worker)
    args = ['--action', 'run', '--store-id', 'shop', '--job-id', JOB]
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'paused'
    monkeypatch.setattr(bridge, 'run', lambda *args: {'status': 'complete', 'oversize': 'x'*65536})
    assert cli.main(args) == 2
    assert capsys.readouterr().out == '{"error":"bridge_unavailable"}\n'


@pytest.mark.parametrize('binding', [None, 'other', '../shop'])
def test_live_collector_requires_explicit_account_binding(binding, monkeypatch):
    if binding is None:
        monkeypatch.delenv('IVYEA_OPS_SUPERVISOR_ACCOUNT_STORE_ID', raising=False)
    else:
        monkeypatch.setenv('IVYEA_OPS_SUPERVISOR_ACCOUNT_STORE_ID', binding)
    monkeypatch.setattr(bridge, 'collect', lambda: pytest.fail('unbound account collected'))
    with pytest.raises(ValueError):
        bridge.run('shop', JOB)
    assert not bridge._path(JOB).exists()


def test_bound_live_collector_can_run(monkeypatch):
    from app.services import emag_jobs
    monkeypatch.setenv('IVYEA_OPS_SUPERVISOR_ACCOUNT_STORE_ID', 'shop')
    called = []
    monkeypatch.setattr(bridge, 'collect', lambda: called.append(True))
    def worker(store, collect):
        collect()
        return {'store_id': store, 'run_id': 'b'*32, 'status': 'complete'}
    monkeypatch.setattr(emag_jobs, 'run', worker)
    assert bridge.run('shop', JOB)['status'] == 'complete'
    assert called == [True]


def test_preclaim_cancel_stops_late_worker_before_collection():
    assert not automation_control.view('shop')['paused']
    bridge.cancel('shop', JOB)
    result = bridge.run('shop', JOB, collect_fn=lambda: pytest.fail('pre-cancelled job collected'))
    assert result['status'] == 'paused'
    assert bridge.receipt('shop', JOB) == result
    assert not automation_control.view('shop')['paused']


def test_preclaim_cancel_identity_cannot_be_reassigned():
    bridge.cancel('other', JOB)
    marker = bridge._path(JOB).with_suffix('.cancel')
    original = marker.read_bytes()
    with pytest.raises(ValueError):
        bridge.cancel('shop', JOB)
    with pytest.raises(ValueError):
        bridge.run('shop', JOB, collect_fn=lambda: pytest.fail('foreign cancelled identity ran'))
    assert not bridge._path(JOB).exists()
    assert marker.read_bytes() == original


def test_delayed_process_honors_preclaim_cancel(tmp_path):
    import subprocess
    import sys
    code = '''
import sys, time
from pathlib import Path
from app.core.config import settings
from app.services import supervisor_bridge as b
settings.data_dir = Path(sys.argv[1])
time.sleep(.2)
def collect(): raise AssertionError('Late worker collected after cancellation')
result = b.run('shop', 'a'*32, collect_fn=collect)
assert result['status'] == 'paused', result
'''
    process = subprocess.Popen([sys.executable, '-c', code, str(tmp_path)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        assert bridge.cancel('shop', JOB)['cancel_requested']
        _, err = process.communicate(timeout=10)
        assert process.returncode == 0, err.decode()
        assert bridge.receipt('shop', JOB)['status'] == 'paused'
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
