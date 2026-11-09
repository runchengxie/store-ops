"""Source financial evidence is not an instruction to pay."""
from copy import deepcopy
import pytest
from app.services import emag_reconciliation as service

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(service.artifacts,'_root',lambda:tmp_path)

def batch():
    return {'schema_version':1,'company':'merchant','counterparty':'platform','marketplace':'RO','currency':'RON',
            'captured_at':'2026-11-10T10:00:00Z','source_ref':'export-1','source_kind':'manual',
            'review_status':'reviewed','coverage':'partial','records':[
                {'kind':'document','id':'fee-1','revision':'v1','document_type':'fee','amount':'100.00','vat_basis':'inclusive'},
                {'kind':'payout','id':'estimate-1','revision':'v1','status':'estimated','payout_date':'2026-11-17',
                 'components':{'receipts':'150.00','fees':'-100.00'},'net_amount':'50.00'}]}

def alloc(id='a1',amount='40.00',confirmed=True):
    return {'kind':'allocation','id':id,'revision':'v1','document_id':'fee-1','document_type':'fee',
            'document_revision':'v1','payout_id':'estimate-1','payout_revision':'v1','amount':amount,
            'confirmed':confirmed,'source_ref':'allocation-export'}

def test_idempotency_net_not_double_deducted_and_partial_coverage():
    b=batch();b['records'].append(alloc());receipt=service.import_batch('shop',b)
    assert service.import_batch('shop',b)['duplicate']
    r=service.reconcile('shop')['scopes'][0]
    assert r['documents'][0]['unallocated_amount']=='60.00'
    assert r['payouts'][0]['net_amount']=='50.00'
    assert r['outstanding_to_pay'] is None
    assert r['batch_ids']==[receipt['batch_id']]

def test_many_to_many_partial_allocations_and_suggestions():
    b=batch();b['records'] += [{**b['records'][0],'id':'fee-2','amount':'20.00'},
                              {**deepcopy(b['records'][1]),'id':'estimate-2'},alloc(),
                              {**alloc('a2','60.00'),'payout_id':'estimate-2'},
                              {**alloc('a3','20.00'),'document_id':'fee-2'},alloc('suggest','100.00',False)]
    service.import_batch('shop',b);r=service.reconcile('shop')['scopes'][0]
    assert [d['unallocated_amount'] for d in r['documents']]==['0.00','0.00']
    assert r['confirmed_allocations']==3 and r['suggested_allocations']==1

def test_overallocation_and_unknown_reference_roll_back():
    b=batch();b['records'].append(alloc(amount='101.00'))
    with pytest.raises(ValueError):service.import_batch('shop',b)
    assert service.reconcile('shop')['scopes']==[]
    b['records'][-1]['amount']='1.00';b['records'][-1]['payout_id']='missing'
    with pytest.raises(ValueError):service.import_batch('shop',b)

def test_revision_history_and_stale_allocations():
    b=batch();b['records'].append(alloc());service.import_batch('shop',b)
    c=batch();c['records']=[{**b['records'][0],'revision':'v2','supersedes':'v1','amount':'120.00'}]
    service.import_batch('shop',c);r=service.reconcile('shop')['scopes'][0]
    assert r['documents'][0]['unallocated_amount']=='120.00'
    assert any(i['code']=='stale_allocation' for i in r['issues'])
    assert len(service.history('shop'))==4
    assert service.import_batch('shop',b)['duplicate']
    assert service.reconcile('shop')['scopes'][0]['documents'][0]['revision']=='v2'

@pytest.mark.parametrize('rev,parent',[('v1',None),('v2',None),('v2','wrong')])
def test_revision_mutation_and_missing_chain_rejected(rev,parent):
    service.import_batch('shop',batch());c=batch();c['records']=[{**c['records'][0],'revision':rev,'amount':'200.00'}]
    if parent:c['records'][0]['supersedes']=parent
    with pytest.raises(ValueError):service.import_batch('shop',c)

def test_scopes_and_document_types_do_not_collide():
    b=batch();service.import_batch('shop',b)
    for field,value in [('company','other'),('currency','EUR')]:
        c=deepcopy(b);c[field]=value;service.import_batch('shop',c)
    c=batch();c['records']=[{**c['records'][0],'document_type':'credit','amount':'-10.00'}]
    service.import_batch('shop',c)
    assert len(service.reconcile('shop')['scopes'])==3
    assert service.reconcile('other-shop')['scopes']==[]

def test_estimate_to_processed_is_linked_not_replaced_or_bank_receipt():
    b=batch();service.import_batch('shop',b);c=batch()
    c['records']=[{**b['records'][1],'id':'actual-1','status':'processed','estimate_id':'estimate-1'}]
    service.import_batch('shop',c);ps=service.reconcile('shop')['scopes'][0]['payouts']
    assert len(ps)==2
    assert next(p for p in ps if p['id']=='estimate-1')['superseded_by_processed']=='actual-1'
    assert all(p['bank_received'] is None for p in ps)

@pytest.mark.parametrize('value',[1.1,True,'NaN','1e5','0.001','99999999999999999999'])
def test_invalid_money(value):
    b=batch();b['records'][0]['amount']=value
    with pytest.raises(ValueError):service.import_batch('shop',b)

def test_unknown_fields_currency_and_missing_source():
    for change in [lambda b:b.update(secret='x'),lambda b:b['records'][0].update(currency='EUR'),
                   lambda b:b.update(source_ref=''),lambda b:b.update(captured_at='2026-11-10')]:
        b=batch();change(b)
        with pytest.raises(ValueError):service.import_batch('shop',b)

def test_credit_not_netted_and_missing_event_date_not_invented():
    b=batch();b['records'].append({'kind':'document','id':'credit','revision':'v1','document_type':'credit',
                                  'amount':'-30.00','vat_basis':'inclusive','observed_at':'2026-11-10T10:00:00Z'})
    service.import_batch('shop',b);r=service.reconcile('shop')['scopes'][0]
    c=next(d for d in r['documents'] if d['id']=='credit')
    assert c.get('occurred_at') is None and c['unallocated_amount']=='-30.00'
    assert r['outstanding_to_pay'] is None
    assert 'Partial' in service.render(service.reconcile('shop'),'en')

def test_invalid_component_total_and_allocation_sign():
    b=batch();b['records'][1]['net_amount']='49.00'
    with pytest.raises(ValueError):service.import_batch('shop',b)
    b=batch();b['records'].append(alloc(amount='-1.00'))
    with pytest.raises(ValueError):service.import_batch('shop',b)

def test_optional_digest_absent_evidence_is_exactly_unchanged():
    original={'markdown':'old','details_markdown':'details'}
    assert service.attach_digest(original,'shop','en')==original
    assert 'reconciliation' not in original


def test_optional_digest_bounded_partial_and_estimate_labels():
    service.import_batch('shop',batch())
    original={'markdown':'old','details_markdown':'details'}
    r=service.attach_digest(original,'shop','zh-CN')
    assert '预计结算' in r['markdown'] and '部分资料' in r['markdown']
    assert r['reconciliation']['scopes'][0]['payouts'][0]['net_amount']=='50.00'
    assert original['markdown']=='old'
    assert len(__import__('json').dumps(r,ensure_ascii=False).encode())<32000


def test_optional_digest_corrupt_database_keeps_operations(tmp_path):
    folder=tmp_path/'reconciliation';folder.mkdir();(folder/'evidence.sqlite3').write_text('corrupt')
    r=service.attach_digest({'markdown':'old','details_markdown':'details'},'shop','en')
    assert r['markdown'].startswith('old') and 'unavailable' in r['markdown']
    assert r['reconciliation']['status']=='unavailable'


def test_cli_duplicate_json_key_and_size_errors(tmp_path,capsys):
    from app import emag_reconciliation_cli as cli
    p=tmp_path/'bad.json';p.write_text('{"schema_version":1,"schema_version":1}')
    assert cli.main(['--store-id','shop','import','--file',str(p)])==2
    assert __import__('json').loads(capsys.readouterr().out)['error']=='reconciliation_unavailable'
    p.write_text(__import__('json').dumps(batch()))
    assert cli.main(['--store-id','shop','import','--file',str(p)])==0
    capsys.readouterr()
    assert cli.main(['--store-id','shop','report','--locale','zh-CN'])==0
    assert '费用与结算' in __import__('json').loads(capsys.readouterr().out)['markdown']

def test_confirmed_links_cannot_exceed_payout_charge_capacity_or_unknown_vat():
    b=batch();b['records'][1]['components']={'receipts':'150.00','fees':'-10.00'}
    b['records'][1]['net_amount']='140.00';b['records'].append(alloc())
    with pytest.raises(ValueError):service.import_batch('shop',b)
    b=batch();b['records'][0]['vat_basis']='exclusive';b['records'].append(alloc())
    with pytest.raises(ValueError):service.import_batch('shop',b)


def test_processed_link_is_order_independent_and_document_line_identity_survives():
    b=batch();p=deepcopy(b['records'][1]);p.update(id='actual-1',status='processed',estimate_id='estimate-1')
    b['records'].insert(0,p)
    b['records'][1]['lines']=[{'id':'storage','amount':'80.00'},{'id':'shipping','amount':'20.00'}]
    service.import_batch('shop',b);r=service.reconcile('shop')['scopes'][0]
    assert next(p for p in r['payouts'] if p['id']=='estimate-1')['superseded_by_processed']=='actual-1'
    assert r['documents'][0]['lines'][0]['id']=='storage'


def test_large_optional_evidence_does_not_break_operating_message_limit():
    service.import_batch('shop',batch())
    original={'markdown':'a'*14990,'details_markdown':'b'*14990}
    r=service.attach_digest(original,'shop','en')
    assert r['markdown']==original['markdown']
    assert r['reconciliation']['status']=='omitted_size_limit'

def test_reversal_cycles_rejected():
    b=batch();b['records']=[{**b['records'][0],'reverses_id':'credit','reverses_type':'credit','reverses_revision':'v1'},
        {'kind':'document','id':'credit','revision':'v1','document_type':'credit','amount':'-100.00',
         'vat_basis':'inclusive','reverses_id':'fee-1','reverses_type':'fee','reverses_revision':'v1'}]
    with pytest.raises(ValueError):service.import_batch('shop',b)


def test_line_allocation_capacity_and_missing_identity():
    b=batch();b['records'][0]['lines']=[{'id':'storage','amount':'30.00'},{'id':'shipping','amount':'70.00'}]
    b['records'].append({**alloc(),'document_line_id':'storage'})
    with pytest.raises(ValueError):service.import_batch('shop',b)
    b['records'][-1]['amount']='20.00';service.import_batch('shop',b)
    c=batch();c['records']=[{**alloc('bad','10.00'),'document_line_id':'missing'}]
    with pytest.raises(ValueError):service.import_batch('shop',c)

def test_sign_changing_revision_stales_links_instead_of_applying_old_sign():
    b=batch();b['records'].append(alloc());service.import_batch('shop',b)
    c=batch();c['records']=[{**c['records'][0],'revision':'v2','supersedes':'v1','amount':'-100.00'}]
    service.import_batch('shop',c)
    r=service.reconcile('shop')['scopes'][0]
    assert r['documents'][0]['unallocated_amount']=='-100.00'
    assert any(i['code']=='stale_allocation' for i in r['issues'])
