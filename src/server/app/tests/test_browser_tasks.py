"""Browser waits remain separate from API collection and merchant writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services import store_artifacts
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    monkeypatch.setenv('IVYEA_OPS_BROWSER_STORE_ID', 'sample-ro')
    monkeypatch.setenv('IVYEA_OPS_BROWSER_ACCOUNT', 'Sample Shop')
    store_artifacts.import_snapshot({'store_id':'sample-ro','platform':'emag','marketplace':'RO',
        'captured_at':datetime.now(timezone.utc).isoformat(), 'source':'synthetic',
        'coverage':['offers'], 'limitations':['Synthetic test'], 'data':{'offers':[{'id':1,'general_stock':4}]}})
    return tmp_path


def test_wait_resume_retains_success(setup):
    from app.services import browser_tasks as b, automation_control
    t = b.request('sample-ro', None, 'test')
    assert b.request('sample-ro', None, 'test')['task_id'] == t['task_id']
    b.run('sample-ro', t['task_id'], reader=lambda: {'state':'waiting_verification'})
    wait = b.view('sample-ro')
    assert wait['state'] == 'waiting_verification'
    assert automation_control.view('sample-ro')['paused'] is False
    resumed = b.request('sample-ro', wait['revision'], 'test')
    with pytest.raises(ValueError): b.request('sample-ro', wait['revision'], 'test')
    b.run('sample-ro', resumed['task_id'], reader=lambda: {'state':'complete','rows':[{'id':'1','stock':4}], 'coverage':'visible_page'})
    done = b.view('sample-ro')
    assert done['state'] == 'complete' and done['observed_rows'] == 1
    assert done['last_success_at'] and done['evidence_id']
    b.request('sample-ro', done['revision'], 'test')
    b.run('sample-ro', done['task_id'], reader=lambda: {'state':'waiting_login'})
    assert b.view('sample-ro')['evidence_id'] == done['evidence_id']


def test_single_claim_and_pause_before_publication(setup):
    from app.services import browser_tasks as b, automation_control
    t = b.request('sample-ro', None, 'test')
    calls = []
    def reader():
        calls.append(1)
        automation_control.set_paused('sample-ro', True, 0, 'test')
        return {'state':'complete','rows':[{'id':'1','stock':4}], 'coverage':'visible_page'}
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda _: b.run('sample-ro',t['task_id'],reader=reader), range(2)))
    assert len(calls) == 1
    assert b.view('sample-ro')['state'] == 'paused'
    assert b.view('sample-ro')['last_success_at'] is None
    with pytest.raises(ValueError): b.request('sample-ro', b.view('sample-ro')['revision'], 'test')


@pytest.mark.parametrize('result', [
    {'state':'complete','rows':[], 'coverage':'visible_page'},
    {'state':'complete','rows':[{'id':'1','stock':-1}], 'coverage':'visible_page'},
    {'state':'complete','rows':[{'id':'1','stock':True}], 'coverage':'visible_page'},
    {'state':'complete','rows':[{'id':'1','stock':4}]*2, 'coverage':'visible_page'},
    {'state':'complete','rows':[{'id':'1','stock':4}], 'coverage':'all_inventory'},
    {'state':'complete','rows':[{'id':'1','stock':4}], 'coverage':'visible_page','token':'secret'},
])
def test_invalid_observation_does_not_publish(setup, result):
    from app.services import browser_tasks as b
    t=b.request('sample-ro',None,'test')
    b.run('sample-ro', t['task_id'], reader=lambda:result)
    assert b.view('sample-ro')['state'] == 'needs_review'
    assert b.view('sample-ro')['last_success_at'] is None


def test_binding_and_authentication(setup, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import require_admin
    import importlib
    from app.routers import platform_operations
    router = importlib.reload(platform_operations).router
    from app.services import browser_tasks as b
    monkeypatch.setattr(b,'launch',lambda *args:None)
    app=FastAPI();app.include_router(router,prefix='/api/operations')
    path='/api/operations/stores/sample-ro/browser-check'
    with TestClient(app) as client:
        assert client.post(path,json={}).status_code == 401
        app.dependency_overrides[require_admin]=lambda:'operator'
        assert client.post(path,json={'kind':'arbitrary'}).status_code == 422
        assert client.post(path,json={}).status_code == 200
        assert client.get('/api/operations/stores/sample-ro/overview').json()['browser_check']['kind']=='fbe_inventory'
        assert client.post('/api/operations/stores/missing/browser-check',json={}).status_code == 404
    monkeypatch.setenv('IVYEA_OPS_BROWSER_STORE_ID','another-store')
    with pytest.raises(ValueError): b.request('sample-ro', None, 'test')


def test_restart_requires_review(setup):
    from app.services import browser_tasks as b
    t=b.request('sample-ro',None,'test')
    with b._db() as conn:
        conn.execute("UPDATE tasks SET state='running' WHERE task_id=?",(t['task_id'],))
    recovered=b.view('sample-ro')
    assert recovered['state']=='needs_review'
    assert b.request('sample-ro',recovered['revision'],'test')['state']=='queued'


def test_daily_hook_never_retries_human_waits(setup, monkeypatch):
    from app.services import browser_tasks as b
    monkeypatch.setenv('IVYEA_OPS_BROWSER_AUTO_CHECK','1')
    launched=[]
    monkeypatch.setattr(b,'launch',lambda store,tid:launched.append((store,tid)))
    b.schedule('sample-ro')
    assert len(launched)==1
    t=b.view('sample-ro')
    b.run('sample-ro',t['task_id'],reader=lambda:{'state':'waiting_verification'})
    b.schedule('sample-ro')
    assert len(launched)==1
    assert b.view('sample-ro')['state']=='waiting_verification'


def test_bridge_busy_yields_without_changing_api_pause(setup):
    from app.services import browser_tasks as b, automation_control
    t=b.request('sample-ro',None,'test')
    with b._lease('bridge') as owned:
        assert owned
        b.run('sample-ro',t['task_id'],reader=lambda:pytest.fail('Bridge is busy'))
    assert b.view('sample-ro')['state']=='waiting_browser'
    assert automation_control.view('sample-ro')['paused'] is False


def test_acknowledged_pause_is_serialized_with_publication(setup, monkeypatch):
    from concurrent.futures import TimeoutError
    from threading import Event
    from app.services import browser_tasks as b, automation_control
    task=b.request('sample-ro',None,'test')
    original=b._save
    futures=[]
    entered=Event()
    with ThreadPoolExecutor(1) as pool:
        def pause():
            entered.set()
            return automation_control.set_paused('sample-ro',True,0,'test')
        def save(conn,t,state):
            if state=='complete':
                future=pool.submit(pause);futures.append(future)
                assert entered.wait(2)
                with pytest.raises(TimeoutError): future.result(timeout=.1)
            return original(conn,t,state)
        monkeypatch.setattr(b,'_save',save)
        b.run('sample-ro',task['task_id'],reader=lambda:{'state':'complete','rows':[{'id':'1','stock':4}],'coverage':'visible_page'})
    assert futures[0].result()['paused'] is True
    assert b.view('sample-ro')['state']=='complete'
