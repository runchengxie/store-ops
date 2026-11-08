"""Only enabled adapters may expose source-labelled operations."""
from datetime import datetime,timezone
import pytest


@pytest.fixture
def snapshot(tmp_path,monkeypatch):
 from app.core.config import settings
 from app.services import store_artifacts
 monkeypatch.setattr(settings,'data_dir',tmp_path)
 return store_artifacts.import_snapshot({'store_id':'sample-ro','platform':'emag','marketplace':'RO','captured_at':datetime.now(timezone.utc).isoformat(),'source':'synthetic platform contract','coverage':['offers'],'limitations':['Synthetic test'],'data':{'offers':[{'id':1,'name':'Product','general_stock':None}]}})


def test_registry_only_enables_emag_and_fails_closed():
 from app.platforms.registry import descriptors,get_adapter,require_capability
 assert [d.platform_id for d in descriptors()]==['emag']
 assert get_adapter('emag').descriptor.version=='1'
 with pytest.raises(ValueError):get_adapter('amazon')
 with pytest.raises(ValueError):require_capability('emag','unsupported_action')
 with pytest.raises(ValueError):require_capability('emag','market_sales')
 assert require_capability('emag','overview').mode=='read'


def test_canonical_overview_preserves_unknowns_and_source(snapshot):
 from app.platforms.registry import get_adapter
 a=get_adapter('emag');r=a.overview('sample-ro')
 assert r['metrics']=={'products':1,'issues':0,'stock':None}
 assert r['snapshot_id']==snapshot['snapshot_id']
 assert r['platform']=='emag' and r['marketplace']=='RO'
 assert r['currency']=='RON' and r['timezone']=='Europe/Bucharest'
 assert r['source']=='synthetic platform contract'
 assert r['collection'] is None
 assert a.stores()[0]['platform']=='emag'


def test_generic_api_remains_admin_only(snapshot):
 import importlib
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.core.security import require_admin
 from app.routers import platform_operations
 module=importlib.reload(platform_operations)
 app=FastAPI();app.include_router(module.router,prefix='/api/operations')
 with TestClient(app) as client:
  assert client.get('/api/operations/stores').status_code==401
  app.dependency_overrides[require_admin]=lambda:'operator'
  assert client.get('/api/operations/platforms').json()[0]['platform_id']=='emag'
  response=client.get('/api/operations/stores/sample-ro/overview')
  assert response.status_code==200
  assert response.json()['snapshot_id']==snapshot['snapshot_id']
  assert client.get('/api/operations/stores/missing/overview').status_code==404


def test_monitoring_control_is_authenticated_versioned_and_store_scoped(snapshot):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.core.security import require_admin
 from app.routers.platform_operations import router
 app=FastAPI();app.include_router(router,prefix='/api/operations')
 path='/api/operations/stores/sample-ro/control'
 with TestClient(app) as client:
  assert client.post(path,json={'paused':True,'revision':0}).status_code==401
  app.dependency_overrides[require_admin]=lambda:'operator'
  assert client.post(path,json={'paused':'true','revision':0}).status_code==422
  assert client.post('/api/operations/stores/missing/control',json={'paused':True,'revision':0}).status_code==404
  paused=client.post(path,json={'paused':True,'revision':0})
  assert paused.status_code==200 and paused.json()['state']=='paused'
  assert client.get('/api/operations/stores/sample-ro/overview').json()['control']['paused'] is True
  assert client.post(path,json={'paused':False,'revision':0}).status_code==409
  assert client.post(path,json={'paused':False,'revision':paused.json()['revision']}).json()['state']=='enabled'
