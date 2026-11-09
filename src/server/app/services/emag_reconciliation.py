"""Local source-labelled fee/payout evidence. No network or accounting writes."""
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import re
import sqlite3
from app.services import store_artifacts as artifacts

BATCH_FIELDS = {'schema_version','company','counterparty','marketplace','currency','captured_at',
                'source_ref','source_kind','review_status','coverage','records'}
COMMON = {'kind','id','revision','supersedes'}
FIELDS = {
    'document': COMMON | {'document_type','amount','vat_basis','document_date','service_start','service_end',
                          'due_date','observed_at','occurred_at','reverses_id','reverses_type','reverses_revision','lines'},
    'payout': COMMON | {'status','payout_date','components','net_amount','estimate_id'},
    'allocation': COMMON | {'document_id','document_type','document_revision','payout_id','payout_revision',
                            'amount','confirmed','source_ref','document_line_id'},
}
SCOPE = ('company','counterparty','marketplace','currency')
MAX_BYTES = 1_000_000
MAX_RECORDS = 2000


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False)


def _text(value, maximum=160):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 for c in value):
        raise ValueError('Expected bounded nonblank text')
    return value


def _id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}',value):
        raise ValueError('Invalid external identity')
    return value


def _money(value):
    if not isinstance(value,str) or not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?',value):
        raise ValueError('Money requires a bounded decimal string with at most two fraction digits')
    return Decimal(value)


def _amount(value):
    return format(value.quantize(Decimal('0.01')),'f')


def _timestamp(value):
    _text(value,64)
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('Timestamp requires timezone')


def _validate(payload):
    if not isinstance(payload,dict) or set(payload)!=BATCH_FIELDS or type(payload['schema_version']) is not int or payload['schema_version']!=1:
        raise ValueError('Invalid manual evidence batch')
    if payload['source_kind']!='manual' or payload['review_status'] not in ('reviewed','unreviewed'):
        raise ValueError('Only explicitly labelled manual evidence is supported')
    if payload['coverage'] not in ('partial','complete'):
        raise ValueError('Coverage must be explicit')
    for field in SCOPE[:-1]: _id(payload[field])
    if not isinstance(payload['currency'],str) or not re.fullmatch('[A-Z]{3}',payload['currency']):
        raise ValueError('Invalid currency')
    _text(payload['source_ref'],500);_timestamp(payload['captured_at'])
    records=payload['records']
    if not isinstance(records,list) or not 1<=len(records)<=500 or len(_json(payload).encode())>MAX_BYTES:
        raise ValueError('Evidence batch exceeds bounds')
    seen=set()
    for r in records:
        if not isinstance(r,dict) or r.get('kind') not in FIELDS or set(r)-FIELDS[r['kind']]:
            raise ValueError('Unknown record or field')
        for f in ('id','revision'): _id(r.get(f))
        if 'supersedes' in r: _id(r['supersedes'])
        key=_key(r)
        if key in seen: raise ValueError('Repeated record identity in batch')
        seen.add(key)
        kind=r['kind']
        if kind=='document':
            _id(r.get('document_type'));_money(r.get('amount'))
            if r.get('vat_basis') not in ('inclusive','exclusive','unknown'):raise ValueError('VAT basis required')
            for f in ('document_date','service_start','service_end','due_date'):
                if f in r: date.fromisoformat(r[f])
            if 'service_start' in r and 'service_end' in r and r['service_start']>r['service_end']:
                raise ValueError('Service period reversed')
            for f in ('observed_at','occurred_at'):
                if f in r:_timestamp(r[f])
            reversal=('reverses_id','reverses_type','reverses_revision')
            if any(f in r for f in reversal):
                for f in reversal:_id(r.get(f))
            if 'lines' in r:
                lines=r['lines']
                if not isinstance(lines,list) or not 1<=len(lines)<=200:raise ValueError('Invalid fee lines')
                line_ids=set();total=Decimal(0)
                for line in lines:
                    if not isinstance(line,dict) or set(line)!={'id','amount'}:raise ValueError('Invalid fee line')
                    _id(line['id']);total+=_money(line['amount'])
                    if line['id'] in line_ids:raise ValueError('Repeated fee line')
                    line_ids.add(line['id'])
                if total!=_money(r['amount']):raise ValueError('Fee lines differ from document total')
        elif kind=='payout':
            if r.get('status') not in ('estimated','processed'):raise ValueError('Invalid payout status')
            date.fromisoformat(r.get('payout_date',''))
            components=r.get('components')
            if not isinstance(components,dict) or not 1<=len(components)<=30:raise ValueError('Missing components')
            total=Decimal(0)
            for k,v in components.items():_id(k);total+=_money(v)
            if total!=_money(r.get('net_amount')):raise ValueError('Payout components differ from net')
            if 'estimate_id' in r:
                _id(r['estimate_id'])
                if r['status']!='processed' or r['estimate_id']==r['id']:raise ValueError('Invalid estimate link')
        else:
            for f in ('document_id','document_type','document_revision','payout_id','payout_revision'):_id(r.get(f))
            _money(r.get('amount'))
            if type(r.get('confirmed')) is not bool:raise ValueError('Allocation confirmation must be boolean')
            _text(r.get('source_ref'),500)
            if 'document_line_id' in r:_id(r['document_line_id'])
    return payload


def _key(r):
    return _json([r['kind'],r.get('document_type') if r['kind']=='document' else None,r['id']])


@contextmanager
def _db(write=False):
    root=artifacts._root()/'reconciliation'
    if not write and not (root/'evidence.sqlite3').exists():
        yield None;return
    root.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(root/'evidence.sqlite3',timeout=30)
    try:
        if write:
            conn.execute('CREATE TABLE IF NOT EXISTS batches (store TEXT, scope TEXT, hash TEXT, payload TEXT, PRIMARY KEY(store,scope,hash))')
            conn.execute('CREATE TABLE IF NOT EXISTS versions (seq INTEGER PRIMARY KEY, store TEXT, scope TEXT, identity TEXT, revision TEXT, payload TEXT, batch TEXT, UNIQUE(store,scope,identity,revision))')
        if write:
            conn.commit()
            conn.execute('BEGIN IMMEDIATE')
        yield conn
        if write:conn.commit()
    finally:conn.close()


def _versions(conn,store,scope):
    return conn.execute('SELECT payload,batch FROM versions WHERE store=? AND scope=? ORDER BY seq',(store,scope)).fetchall()


def _latest(rows):
    result={}
    for raw,batch_id in rows:
        r=json.loads(raw);result[_key(r)]={**r,'batch_id':batch_id}
    return result


def _evaluate(current):
    docs={};payouts={};issues=[];allocs=[]
    for r in current.values():
        if r['kind']=='document':docs[(r['document_type'],r['id'])]=dict(r)
        elif r['kind']=='payout':payouts[r['id']]=dict(r)
        else:allocs.append(r)
    line_used={}
    used={k:Decimal(0) for k in docs};payout_allocated={k:Decimal(0) for k in payouts}
    charges={k:Decimal(0) for k in payouts};credits={k:Decimal(0) for k in payouts}
    confirmed=0;suggested=0
    for p in payouts.values():
        p['bank_received']=None;p['superseded_by_processed']=None
    for a in allocs:
        d=docs.get((a['document_type'],a['document_id']));p=payouts.get(a['payout_id'])
        if not d or not p:raise ValueError('Allocation references missing document/payout in its scope')
        if a['document_revision']!=d['revision'] or a['payout_revision']!=p['revision']:
            issues.append({'code':'stale_allocation','allocation_id':a['id']});continue
        value=_money(a['amount']);amount=_money(d['amount'])
        if not value or not amount or (value>0)!=(amount>0):raise ValueError('Invalid allocation sign')
        line=None
        if 'document_line_id' in a:
            line=next((v for v in d.get('lines',[]) if v['id']==a['document_line_id']),None)
            if line is None:raise ValueError('Unknown allocation line')
            if _money(line['amount'])*value<=0:raise ValueError('Invalid line allocation sign')
        if not a['confirmed']:
            suggested+=1;continue
        if d['vat_basis']!='inclusive':raise ValueError('Confirmed allocations require comparable VAT-inclusive document amounts')
        if any(v.get('review_status')!='reviewed' for v in (a,d,p)):
            raise ValueError('Confirmed allocations require reviewed endpoint and link evidence')
        if line is not None:
            lk=(a['document_type'],a['document_id'],a['document_line_id'])
            line_used[lk]=line_used.get(lk,Decimal(0))+value
            if abs(line_used[lk])>abs(_money(line['amount'])):raise ValueError('Fee line over-allocation')
        used[(a['document_type'],a['document_id'])]+=value
        if abs(used[(a['document_type'],a['document_id'])])>abs(amount):raise ValueError('Document over-allocation')
        payout_allocated[p['id']]+=value
        if value>0:charges[p['id']]+=value
        else:credits[p['id']]-=value
        confirmed+=1
    for p in payouts.values():
        charge_capacity=-sum((min(_money(v),Decimal(0)) for v in p['components'].values()),Decimal(0))
        credit_capacity=sum((max(_money(v),Decimal(0)) for v in p['components'].values()),Decimal(0))
        if charges[p['id']]>charge_capacity or credits[p['id']]>credit_capacity:
            raise ValueError('Payout component over-allocation')
        if p.get('estimate_id'):
            old=payouts.get(p['estimate_id'])
            if not old or old['status']!='estimated':raise ValueError('Processed payout requires an existing estimate')
            if old.get('superseded_by_processed'):raise ValueError('Estimate linked to multiple processed batches')
            old['superseded_by_processed']=p['id']
    for start in docs:
        seen=set();node=start
        while node in docs and docs[node].get('reverses_id'):
            if node in seen:raise ValueError('Reversal cycle')
            seen.add(node);source=docs[node];target=(source['reverses_type'],source['reverses_id'])
            if target in docs and docs[target]['revision']!=source['reverses_revision']:break
            node=target
    for key,d in docs.items():
        d['unallocated_amount']=_amount(_money(d['amount'])-used[key])
        if used[key]==0:issues.append({'code':'unmatched_document','document_id':d['id'],'document_type':d['document_type']})
        if d.get('reverses_id'):
            original=docs.get((d['reverses_type'],d['reverses_id']))
            if not original:raise ValueError('Unknown reversal source')
            if original['revision']!=d['reverses_revision']:
                issues.append({'code':'stale_reversal','document_id':d['id']})
            elif _money(original['amount'])*_money(d['amount'])>=0:raise ValueError('Reversal must have opposite sign')
    for p in payouts.values():p['allocated_document_amount']=_amount(payout_allocated[p['id']])
    return {'documents':sorted(docs.values(),key=lambda d:(d['document_type'],d['id'])),
            'payouts':sorted(payouts.values(),key=lambda p:p['id']), 'allocations':allocs,
            'confirmed_allocations':confirmed,'suggested_allocations':suggested,
            'outstanding_to_pay':None,'issues':issues}


def _validate_history(current,versions):
    """Unknown references differ from known historical observations that became stale."""
    def lookup(kind,identity,revision,document_type=None):
        key=_key({'kind':kind,'id':identity,'document_type':document_type})
        record=versions.get((key,revision))
        if record is None:raise ValueError('Referenced revision was never imported in this scope')
        return record
    for r in current.values():
        if r['kind']=='allocation':
            d=lookup('document',r['document_id'],r['document_revision'],r['document_type'])
            p=lookup('payout',r['payout_id'],r['payout_revision'])
            if r['confirmed'] and any(v.get('review_status')!='reviewed' for v in (r,d,p)):
                raise ValueError('Confirmed links require reviewed source revisions')
        elif r['kind']=='document' and r.get('reverses_id'):
            original=lookup('document',r['reverses_id'],r['reverses_revision'],r['reverses_type'])
            if _money(original['amount'])*_money(r['amount'])>=0:
                raise ValueError('Reversal must have opposite sign to its referenced revision')


def import_batch(store_id,payload):
    """Append validated manual observations atomically. Identical reimports are no-ops."""
    artifacts.validate_id(store_id)
    b=_validate(json.loads(_json(payload)))
    scope=_json({k:b[k] for k in SCOPE});digest=hashlib.sha256(_json(b).encode()).hexdigest()
    with _db(True) as conn:
        if conn.execute('SELECT 1 FROM batches WHERE store=? AND scope=? AND hash=?',(store_id,scope,digest)).fetchone():
            return {'batch_id':digest,'duplicate':True,'records_added':0}
        rows=_versions(conn,store_id,scope);current=_latest(rows)
        old={( _key(json.loads(raw)),json.loads(raw)['revision']):json.loads(raw) for raw,_ in rows}
        added=[]
        for record in b['records']:
            r={**record,'source_ref':record.get('source_ref',b['source_ref']),'captured_at':b['captured_at'],
               'review_status':b['review_status']}
            key=_key(r);prior=current.get(key);previous=old.get((key,r['revision']))
            # Provenance changes never mutate a previously imported revision.
            if previous:
                compare={k:v for k,v in previous.items() if k not in ('captured_at','source_ref','review_status')}
                original={k:v for k,v in r.items() if k not in ('captured_at','source_ref','review_status')}
                if compare!=original:raise ValueError('Existing source revision changed')
                continue
            if prior:
                if r['kind']=='payout' and r['status']!=prior['status']:
                    raise ValueError('Processed payout must use a separate identity and explicit estimate link')
                if r.get('supersedes')!=prior['revision']:raise ValueError('Changed evidence requires current supersedes revision')
            elif 'supersedes' in r:raise ValueError('First revision cannot supersede missing evidence')
            current[key]=r;added.append(r)
        if len(current)>MAX_RECORDS:raise ValueError('Scope exceeds record bound')
        _validate_history(current, {**old, **{(_key(r),r['revision']):r for r in added}})
        _evaluate(current)
        conn.execute('INSERT INTO batches VALUES (?,?,?,?)',(store_id,scope,digest,_json(b)))
        for r in added:
            conn.execute('INSERT INTO versions (store,scope,identity,revision,payload,batch) VALUES (?,?,?,?,?,?)',
                         (store_id,scope,_key(r),r['revision'],_json(r),digest))
    return {'batch_id':digest,'duplicate':False,'records_added':len(added)}


def history(store_id):
    artifacts.validate_id(store_id)
    with _db() as conn:
        if conn is None:return []
        return [{'scope':json.loads(s),'record':json.loads(p),'batch_id':b} for s,p,b in conn.execute(
            'SELECT scope,payload,batch FROM versions WHERE store=? ORDER BY seq',(store_id,))]


def reconcile(store_id):
    artifacts.validate_id(store_id);scopes=[]
    with _db() as conn:
        if conn is not None:
            for (scope,) in conn.execute('SELECT DISTINCT scope FROM batches WHERE store=? ORDER BY scope',(store_id,)):
                batches=conn.execute('SELECT hash,payload FROM batches WHERE store=? AND scope=? ORDER BY rowid',(store_id,scope)).fetchall()
                latest=json.loads(batches[-1][1]);result=_evaluate(_latest(_versions(conn,store_id,scope)))
                partial=any(json.loads(p)['coverage']!='complete' or json.loads(p)['review_status']!='reviewed' for _,p in batches)
                scopes.append({**json.loads(scope),**result,'coverage':'partial' if partial else 'complete',
                               'captured_at':latest['captured_at'],'batch_ids':[b for b,_ in batches]})
    return {'schema_version':1,'store_id':store_id,'scopes':scopes}


def render(result,locale='en'):
    """Bounded summary; identifiers remain only in structured evidence, not Markdown."""
    if locale not in ('en','zh-CN'):raise ValueError('Unsupported locale')
    if not result['scopes']:return ''
    zh=locale=='zh-CN'
    lines=['## 费用与结算' if zh else '## Fees and payouts']
    for scope in result['scopes'][:3]:
        currency=scope['currency']
        lines.append(('覆盖：部分资料。' if zh else 'Coverage: Partial evidence.') if scope['coverage']=='partial' else
                     ('覆盖：导入资料标记完整，尚非银行对账。' if zh else 'Coverage: imported evidence marked complete; not bank reconciliation.'))
        for p in scope['payouts'][:3]:
            label=('预计结算' if p['status']=='estimated' else '已处理结算') if zh else ('Estimated payout' if p['status']=='estimated' else 'Processed payout')
            suffix=('（已关联实际批次）' if zh else ' (linked to processed batch)') if p['superseded_by_processed'] else ''
            lines.append(f"- {label} {p['payout_date']}: {p['net_amount']} {currency}{suffix}")
        lines.append((f"- 已确认抵扣关联 {scope['confirmed_allocations']} 条；待核对项 {len(scope['issues'])} 项。" if zh else
                      f"- Confirmed allocation links: {scope['confirmed_allocations']}; issues: {len(scope['issues'])}."))
    lines.append('实际应付余额与银行到账尚未核实；结算净额不再重复扣减费用。' if zh else
                 'Amount payable and bank receipt remain unverified; fees are not deducted again from payout net.')
    if len(result['scopes'])>3:lines.append('仅展示前 3 个范围。' if zh else 'Showing only 3 scopes.')
    return '\n'.join(lines)


def attach_digest(report,store_id,locale):
    """Explicit local I/O boundary. Financial failures do not break operations reports."""
    try:
        evidence=reconcile(store_id)
        if not evidence['scopes']:return report
        section=render(evidence,locale)
        scopes=[]
        for scope in evidence['scopes'][:3]:
            fields=('company','counterparty','marketplace','currency','coverage','captured_at',
                    'confirmed_allocations','suggested_allocations','outstanding_to_pay')
            scopes.append({**{k:scope[k] for k in fields},'batch_ids':scope['batch_ids'][-3:],
                           'payouts':[{k:p[k] for k in ('id','revision','status','payout_date','components',
                                                      'net_amount','bank_received','superseded_by_processed','source_ref')}
                                      for p in scope['payouts'][:3]],
                           'document_count':len(scope['documents']),'issue_count':len(scope['issues']),
                           'payout_count':len(scope['payouts'])})
        structured={'schema_version':1,'store_id':store_id,'status':'available','scopes':scopes,
                    'scope_count':len(evidence['scopes']),
                    'truncated':len(evidence['scopes'])>3 or any(len(s['payouts'])>3 or len(s['batch_ids'])>3 for s in evidence['scopes'])}
    except (ValueError, sqlite3.Error, OSError, KeyError, TypeError):
        section='## 费用与结算\n财务证据暂不可用，需核对本地资料。' if locale=='zh-CN' else '## Fees and payouts\nFinancial evidence unavailable; review local records.'
        structured={'schema_version':1,'store_id':store_id,'status':'unavailable','scopes':[]}
    result={**report,'reconciliation':structured,'markdown':report['markdown']+'\n\n'+section,
            'details_markdown':report['details_markdown']+'\n\n'+section}
    # Existing operational delivery limits are authoritative; optional evidence cannot crowd it out.
    if len(result['markdown'].encode())>15000 or len(_json(result).encode())>31000:
        result={**report,'reconciliation':{'schema_version':1,'store_id':store_id,'status':'omitted_size_limit','scopes':[]}}
    return result
