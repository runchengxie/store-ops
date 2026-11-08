from datetime import datetime, timezone
from io import BytesIO
import pytest
from openpyxl import Workbook
from app.services import store_artifacts as artifacts, emag_commerce as commerce
from app.services import emag_promotion as promotion, emag_preflight as preflight, emag_decision_support as decision

@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'data_dir',tmp_path)
    return artifacts.import_snapshot({'store_id':'demo-ro','platform':'emag','marketplace':'RO','captured_at':datetime.now(timezone.utc).isoformat(),'source':'synthetic','coverage':['offers'],'limitations':[],'data':{'offers':[{'id':1,'name':'Synthetic','sale_price':'100','general_stock':5}]}})

def workbook(rows=None):
    book=Workbook();sheet=book.active
    for row in [['Synthetic'],[],['part_number','ext_id','category_id','sale_price','family_id','family_name'],['Required','Required','Required','Required','',''],['SKU','ID','Category','Price','Family','Family name']]+(rows or [['sku',1,42,100,'f','name']]):sheet.append(row)
    out=BytesIO();book.save(out);return out.getvalue()

def test_promotion(snapshot):
    sid=snapshot['snapshot_id']
    assert promotion.check('demo-ro',sid,'1',{})['status']=='incomplete'
    costs={key:('10' if key=='commission_pct' else '1' if key=='cny_to_ron' else '0') for key in commerce.COSTS}
    commerce.save('demo-ro',sid,'1',0,costs,'admin')
    assert 'extra_cost_ron' in promotion.check('demo-ro',sid,'1',{})['missing']
    result=promotion.check('demo-ro',sid,'1',{'extra_cost_ron':'0','discount_pct':'10','voucher_pct':'20','commission_reduction_pct':'30','support_ex_vat_ron':'5'})
    assert result['knowledge_query']=='优惠券'
    assert [s['kind'] for s in result['scenarios']]==['baseline','discount','voucher']
    assert result['scenarios'][0]['economics']['commission_ron']=='7.00'
    assert result['scenarios'][0]['economics']['contribution_ron']=='93.00'
    assert result['scenarios'][0]['contribution_with_assumed_support_ron']=='98.00'
    assert promotion.check('demo-ro',sid,'1',{'extra_cost_ron':'0','stacking':'sequential','discount_pct':'10','voucher_pct':'20'})['scenarios'][-1]['sale_price_ex_vat_ron']=='72.00'

@pytest.mark.parametrize('payload',[{'extra_cost_ron':0},{'discount_pct':'NaN'},{'discount_pct':'101'},{'unknown':'1'},{'stacking':'automatic'}])
def test_invalid(snapshot,payload):
    with pytest.raises(ValueError):promotion.check('demo-ro',snapshot['snapshot_id'],'1',payload)

def test_identity(snapshot):
    with pytest.raises(ValueError,match='stale'):promotion.check('demo-ro','old','1',{})
    with pytest.raises(FileNotFoundError):promotion.check('demo-ro',snapshot['snapshot_id'],'2',{})
    with pytest.raises(ValueError,match='stale'):preflight.check('demo-ro','old','test.xlsx',workbook())

def test_preflight(snapshot):
    result=preflight.check('demo-ro',snapshot['snapshot_id'],'products.xlsx',workbook([['sku',1,None,'=1+1','f','one'],['sku',2,42,100,'f','two']]))
    assert result['status']=='needs_review'
    assert result['knowledge_query']=='模板'
    assert result['layout']['header_row']==3
    assert result['row_count']==2
    assert {'required_blank','duplicate_identity','formula_requires_review','family_metadata_mismatch'} <= {i['code'] for i in result['issues']}

def test_unknown(snapshot):
    sid=snapshot['snapshot_id']
    assert preflight.check('demo-ro',sid,'training-guide.xlsx',workbook())['status']=='unsupported'
    book=Workbook();out=BytesIO();book.save(out)
    assert preflight.check('demo-ro',sid,'unknown.xlsx',out.getvalue())['status']=='unsupported'
    with pytest.raises(ValueError):preflight.check('demo-ro',sid,'bad.xlsx',b'bad')

def test_decision(snapshot):
    result=decision.view('demo-ro')
    assert result['snapshot_id']==snapshot['snapshot_id']
    assert result['products']==[{'id':'1','name':'Synthetic'}]
    assert result['marketplace_writes'] is False
    assert len(result['cards'])<=100


def test_stale_saved_costs(snapshot):
    sid=snapshot['snapshot_id']
    commerce.save('demo-ro',sid,'1',0,{key:('1' if key=='cny_to_ron' else '0') for key in commerce.COSTS},'admin')
    newer=artifacts.import_snapshot({key:value for key,value in snapshot.items() if key not in ('snapshot_id',)})
    result=promotion.check('demo-ro',newer['snapshot_id'],'1',{'extra_cost_ron':'0'})
    assert result['status']=='incomplete'
    assert 'current_cost_record' in result['missing']
    assert not result['scenarios']


def test_zip_limits_and_unsafe_content(snapshot):
    from zipfile import ZipFile
    sid=snapshot['snapshot_id']
    for path,body in [('../bad.xml',b'<xml/>'),('xl/vbaProject.bin',b'active'),('xl/bad.xml',b'<!DOCTYPE test>')]:
        out=BytesIO()
        with ZipFile(out,'w') as archive:archive.writestr(path,body)
        with pytest.raises(ValueError):preflight.check('demo-ro',sid,'unsafe.xlsx',out.getvalue())
    out=BytesIO()
    with ZipFile(out,'w') as archive:
        for i in range(501):archive.writestr(str(i),b'')
    with pytest.raises(ValueError,match='limit'):preflight.check('demo-ro',sid,'large.xlsx',out.getvalue())
    with pytest.raises(OverflowError):preflight.check('demo-ro',sid,'large.xlsx',b'x'*(preflight.MAX_BYTES+1))


def test_issue_and_row_limits(snapshot):
    result=preflight.check('demo-ro',snapshot['snapshot_id'],'rows.xlsx',workbook([['same',None,None,None] for _ in range(1002)]))
    assert result['row_count']==1000
    assert len(result['issues'])==200
    assert result['truncated'] is True


def test_admin_http_boundary(snapshot):
    import asyncio
    import httpx
    from fastapi import FastAPI
    from app.routers.emag_assistance import router, require_admin
    app=FastAPI();app.include_router(router,prefix='/api/emag')
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            path='/api/emag/stores/demo-ro'
            assert (await client.get(path+'/decision-support')).status_code in (401,403)
            app.dependency_overrides[require_admin]=lambda:'admin'
            assert (await client.get(path+'/decision-support')).status_code==200
            assert (await client.post(path+'/promotion-check/1',json={'snapshot_id':'old'})).status_code==409
            assert (await client.post(path+'/promotion-check/2',json={'snapshot_id':snapshot['snapshot_id']})).status_code==404
            assert (await client.post(path+'/promotion-check/1',json={'snapshot_id':snapshot['snapshot_id'],'extra_cost_ron':0})).status_code==422
            response=await client.post(path+'/preflight',data={'snapshot_id':snapshot['snapshot_id']},files={'file':('test.xlsx',workbook(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
            assert response.status_code==200
    asyncio.run(run())


def test_observed_stock_prioritized_and_unknown_retained(snapshot):
    offers=[{'id':i,'name':str(i),'offer_validation_status':[{'value':2}],'general_stock':None if i==1 else 0 if i==2 else 5} for i in range(1,5)]
    artifacts.import_snapshot({**{k:v for k,v in snapshot.items() if k!='snapshot_id'},'data':{'offers':offers}})
    result=decision.view('demo-ro')
    assert result['cards']
    assert result['cards'][0]['stock']==5
    assert all(c['knowledge_query'] in ('价格','商品') for c in result['cards'])
    assert any(c['stock'] is None for c in result['cards'])
    assert all(any(check['key']=='confirmed_root_cause' and check['status']=='unknown' for check in c['checks']) for c in result['cards'])


@pytest.mark.parametrize('late_row,late_column',[(1007,1),(6,301)])
def test_unexamined_cells_are_explicit_even_with_underreported_dimensions(snapshot,late_row,late_column):
    from zipfile import ZipFile
    import re
    book=__import__('openpyxl').load_workbook(BytesIO(workbook()))
    book.active.cell(late_row,late_column,'unexamined')
    raw=BytesIO();book.save(raw)
    modified=BytesIO()
    with ZipFile(BytesIO(raw.getvalue())) as original,ZipFile(modified,'w') as archive:
        for name in original.namelist():
            content=original.read(name)
            if name=='xl/worksheets/sheet1.xml':content=re.sub(br'<dimension ref="[^"]+"/>',b'<dimension ref="A1:F6"/>',content)
            archive.writestr(name,content)
    result=preflight.check('demo-ro',snapshot['snapshot_id'],'sparse.xlsx',modified.getvalue())
    assert result['truncated'] is True
    assert any(i['code']=='unexamined_cells' for i in result['issues'])
    assert result['status']=='needs_review'


def test_empty_template_requires_explicit_review(snapshot):
    book=__import__('openpyxl').load_workbook(BytesIO(workbook()))
    book.active.delete_rows(6)
    raw=BytesIO();book.save(raw)
    result=preflight.check('demo-ro',snapshot['snapshot_id'],'empty.xlsx',raw.getvalue())
    assert result['row_count']==0
    assert any(i['code']=='no_product_rows' for i in result['issues'])
    assert result['status']=='needs_review'
