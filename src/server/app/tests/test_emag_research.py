"""Research evidence must preserve provenance and refuse incomparable observations."""
from datetime import datetime, timezone
import pytest
from app.services import store_artifacts


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    def create(offers=None):
        return store_artifacts.import_snapshot({'store_id':'demo-ro','platform':'emag','marketplace':'RO',
            'captured_at':datetime.now(timezone.utc).isoformat(),'source':'synthetic','coverage':['offers'],
            'limitations':['test only'],'data':{'offers':offers or [{'id':1,'part_number_key':'PNK123','sale_price':'100'}]}})
    return create


def observation(**changes):
    return {'kind':'quote','pnk':'PNK123','name':'Product','market':'RO','currency':'RON',
            'price_basis':'inclusive_vat','price':'120','seller':'seller-A','comparison_key':'black-1pack-fbe',
            'buy_button':'yes','source_url':'https://www.emag.ro/product/pd/PNK123/',
            'source_type':'manual','observed_at':'2026-11-07T00:00:00Z','note':'Visible offer sample',**changes}


def service():
    from app.services import emag_research
    return emag_research


def test_ledger_revisions_and_snapshot_conflicts(snapshot):
    s=service(); snap=snapshot()
    row=s.save('demo-ro',snap['snapshot_id'],observation(), 'operator')
    assert row['revision']==1
    assert s.view('demo-ro')['records'][0]['actor']=='operator'
    updated=s.save('demo-ro',snap['snapshot_id'],observation(price='110'), 'other',row['record_id'],1)
    assert updated['revision']==2
    with pytest.raises(ValueError): s.save('demo-ro',snap['snapshot_id'],observation(),'a',row['record_id'],1)
    assert len(s.view('demo-ro')['history'])==2
    snapshot()
    assert s.view('demo-ro')['records'][0]['stale'] is True
    with pytest.raises(ValueError): s.save('demo-ro',snap['snapshot_id'],observation(),'a')


def test_only_exact_unambiguous_pnk_matches(snapshot):
    s=service(); snap=snapshot([{'id':1,'part_number_key':'PNK123'},{'id':2,'part_number_key':'PNK123'}])
    s.save('demo-ro',snap['snapshot_id'],observation(),'a')
    assert s.view('demo-ro')['records'][0]['match']['status']=='ambiguous'


def test_import_is_atomic_and_empty_prices_are_unknown(snapshot):
    s=service(); snap=snapshot()
    with pytest.raises(ValueError): s.import_rows('demo-ro',snap['snapshot_id'],[observation(),observation(source_url='javascript:alert(1)')],'a')
    assert s.view('demo-ro')['records']==[]
    s.import_rows('demo-ro',snap['snapshot_id'],[observation(price=''),observation(price='0')],'a')
    rows=s.view('demo-ro')['records']
    assert sorted(str(r['payload']['price']) for r in rows)==['0','None']


@pytest.mark.parametrize('change',[{'currency':'EUR'},{'market':'HU','currency':'HUF'},{'price_basis':'exclusive_vat'},{'comparison_key':'red-2pack'}])
def test_mixed_conditions_never_compare(snapshot,change):
    s=service();snap=snapshot()
    s.import_rows('demo-ro',snap['snapshot_id'],[observation(),observation(price='110',**change)],'a')
    assert s.view('demo-ro')['comparisons']==[]


def test_comparable_history_has_change_and_source(snapshot):
    s=service();snap=snapshot()
    s.import_rows('demo-ro',snap['snapshot_id'],[observation(),observation(price='110',observed_at='2026-11-07T01:00:00Z')],'a')
    change=s.view('demo-ro')['comparisons'][0]
    assert change['price_change']=='-10.00'
    assert change['market']=='RO'
    assert change['comparison_key']=='black-1pack-fbe'
    assert change['source_url'].startswith('https://')


@pytest.mark.parametrize('change',[{'price':'1e-999999'},{'observed_at':'yesterday'},{'source_type':'actual_sales'},{'buy_button':'maybe'},{'pnk':''}])
def test_invalid_evidence_is_rejected(snapshot,change):
    s=service();snap=snapshot()
    with pytest.raises(ValueError): s.save('demo-ro',snap['snapshot_id'],observation(**change),'a')


def test_research_api_auth_and_import_rollback(snapshot):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import require_admin
    from app.routers import emag_research
    import importlib
    importlib.reload(emag_research)
    snap=snapshot(); app=FastAPI();app.include_router(emag_research.router,prefix='/api/emag')
    with TestClient(app) as client:
        base='/api/emag/stores/demo-ro/research'
        assert client.get(base).status_code==401
        app.dependency_overrides[require_admin]=lambda:'operator'
        response=client.post(base,json={'snapshot_id':snap['snapshot_id'],'payload':observation()})
        assert response.status_code==200
        assert response.json()['actor']=='operator'
        assert client.post(base+'/import',json={'snapshot_id':snap['snapshot_id'],'rows':[observation(pnk='')]}).status_code==422
        assert len(client.get(base).json()['records'])==1


def test_same_instant_different_timezone_never_creates_change(snapshot):
    s=service();snap=snapshot()
    s.import_rows('demo-ro',snap['snapshot_id'],[observation(),observation(price='110',observed_at='2026-11-07T01:00:00+01:00')],'a')
    assert s.view('demo-ro')['comparisons']==[]


def test_ambiguous_latest_timestamp_does_not_choose_arbitrary_price(snapshot):
    s=service();snap=snapshot()
    s.import_rows('demo-ro',snap['snapshot_id'],[observation(),observation(price='110',observed_at='2026-11-07T01:00:00Z'),observation(price='105',observed_at='2026-11-07T01:00:00Z')],'a')
    assert any(p['reason']=='resolve_observation_conflict' for p in s.view('demo-ro')['prompts'])


def test_quote_changes_cost_gaps_and_comparable_own_price_make_prompts(snapshot):
    s=service();snap=snapshot()
    s.import_rows('demo-ro',snap['snapshot_id'],[observation(price='90',price_basis='exclusive_vat',buy_button='no'),observation(price='80',price_basis='exclusive_vat',buy_button='yes',observed_at='2026-11-07T01:00:00Z')],'a')
    reasons={p['reason'] for p in s.view('demo-ro')['prompts']}
    assert {'review_price_change','review_buy_button_change','review_own_price_gap','confirm_costs'} <= reasons


def test_pinterest_trend_without_pnk_can_link_candidate(snapshot):
    s = service()
    snap = snapshot()
    payload = observation(kind='pinterest_trend', pnk='', keyword='table decor',
                          trend_region='PL+RO+HU+SK+CZ', source_url='https://trends.pinterest.com/', price='')
    row = s.save('demo-ro', snap['snapshot_id'], payload, 'operator')
    assert s.view('demo-ro')['records'][0]['match']['status'] == 'absent'
    s.save('demo-ro', snap['snapshot_id'], {**payload, 'pnk': 'PNK123'}, 'operator', row['record_id'], 1)
    assert s.view('demo-ro')['records'][0]['match']['status'] == 'matched'
    for changes in ({'keyword': ''}, {'trend_region': ''}, {'source_url': 'https://example.com/'}):
        with pytest.raises(ValueError):
            s.validate({**payload, **changes})
