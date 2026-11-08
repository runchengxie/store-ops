"""Pause acknowledgement must reflect the worker, not just a UI flag."""
import sqlite3
import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services import store_artifacts
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    store_artifacts.import_snapshot({'store_id':'control-ro','platform':'emag','marketplace':'RO','captured_at':'2026-11-08T00:00:00Z','source':'synthetic','coverage':['offers'],'limitations':['Test only'],'data':{'offers':[{'id':1,'name':'Test'}]}})
    return 'control-ro'


def test_pause_blocks_collection_and_resume_allows_work(store):
    from app.services import automation_control as control, emag_jobs
    initial = control.view(store)
    result = control.set_paused(store, True, initial['revision'], 'operator')
    assert result['state'] == 'paused'
    called = []
    assert emag_jobs.run(store, lambda: called.append(True))['status'] == 'paused'
    assert not called
    assert control.view(store)['paused'] is True
    with pytest.raises(ValueError):
        control.set_paused(store, False, initial['revision'], 'stale tab')
    control.set_paused(store, False, result['revision'], 'operator')
    assert emag_jobs.run(store)['status'] == 'complete'


def test_inflight_pause_waits_for_worker_exit_without_publishing(store, monkeypatch):
    from app.services import automation_control as control, emag_jobs, emag_business
    published = []
    monkeypatch.setattr(emag_business, 'publish', lambda *args: published.append(args))
    def collect():
        assert control.set_paused(store, True, 0, 'operator')['state'] == 'pausing'
        return {}
    assert emag_jobs.run(store, collect)['status'] == 'paused'
    assert published == []
    assert control.view(store)['state'] == 'paused'


def test_checkpoint_stops_before_next_network_request(store):
    from app.services import automation_control as control, emag_jobs, emag_readonly
    class Client:
        def post(self, *args, **kwargs):
            raise AssertionError('Paused worker must not send a request')
    def collect():
        control.set_paused(store, True, 0, 'operator')
        return emag_readonly.collect(Client(), None, delay=0)
    assert emag_jobs.run(store, collect)['status'] == 'paused'


def test_busy_worker_is_not_reported_as_fully_paused(store):
    from app.services import automation_control as control, emag_jobs
    root = emag_jobs._root(store)
    root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(root / 'run-lock.sqlite3', timeout=0) as conn:
        conn.execute('BEGIN IMMEDIATE')
        assert control.set_paused(store, True, 0, 'operator')['state'] == 'pausing'
    assert control.view(store)['state'] == 'paused'


def test_paused_invocation_skips_even_while_previous_worker_is_draining(store):
    from app.services import automation_control as control, emag_jobs, store_artifacts
    root = emag_jobs._root(store)
    root.mkdir(parents=True, exist_ok=True)
    store_artifacts._write_new(root / 'latest.json', {'active_worker':'preserve'})
    with sqlite3.connect(root / 'run-lock.sqlite3', timeout=0) as conn:
        conn.execute('BEGIN IMMEDIATE')
        control.set_paused(store, True, 0, 'operator')
        result = emag_jobs.run(store, lambda: pytest.fail('Paused worker collected data'))
        assert result['status'] == 'paused'
        assert emag_jobs.latest(store) == {'active_worker':'preserve'}
        assert (root / (result['run_id']+'.json')).is_file()


def test_paused_cli_exits_successfully_without_reading_credentials(store, monkeypatch, capsys):
    import json
    from app import emag_job_cli
    from app.services import automation_control as control
    monkeypatch.setattr(emag_job_cli, 'read_emag_credentials', lambda: pytest.fail('Paused invocation read credentials'))
    control.set_paused(store, True, 0, 'operator')
    assert emag_job_cli.main(['--store-id',store]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'paused'
