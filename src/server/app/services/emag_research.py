"""Traceable local market observations, never a market-wide sales feed."""
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit
from app.services import store_artifacts as artifacts, emag_commerce


@contextmanager
def database():
    from app.core.config import settings
    path = settings.data_dir / 'emag-research.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    path.chmod(0o600)
    conn = sqlite3.connect(path, timeout=20)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS research (sequence INTEGER PRIMARY KEY AUTOINCREMENT, store TEXT NOT NULL, record_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(store,record_id,revision))')
        with conn:
            yield conn
    finally:
        conn.close()


FIELDS = {'kind','pnk','name','market','currency','price_basis','price','seller','comparison_key','buy_button',
          'keyword','trend_region','source_url','source_type','observed_at','period_start','period_end','performance_label','status','note'}


def timestamp(value):
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError('Use an ISO timestamp with timezone')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except ValueError:
        raise ValueError('Use an ISO timestamp with timezone') from None


def validate(payload):
    if not isinstance(payload, dict) or set(payload) - FIELDS:
        raise ValueError('Unknown research field')
    p = dict(payload)
    for key, value in p.items():
        if value is not None and (not isinstance(value, str) or len(value) > (2000 if key == 'note' else 500)):
            raise ValueError('Research values must be bounded text')
        if isinstance(value, str):
            p[key] = value.strip()
    for key in (('name','source_url','observed_at') if p.get('kind') == 'pinterest_trend' else ('pnk','name','source_url','observed_at')):
        if not p.get(key):
            raise ValueError(f'Missing {key}')
    choices = {'kind':('opportunity','quote','pinterest_trend'), 'market':('RO','BG','HU'), 'currency':('RON','EUR','HUF'),
               'price_basis':('inclusive_vat','exclusive_vat','unknown'), 'source_type':('official','estimated','manual'),
               'buy_button':('yes','no','unknown'), 'status':('research','costing','hold','approved')}
    p.setdefault('buy_button','unknown')
    p.setdefault('status','research')
    for key, allowed in choices.items():
        if p.get(key) not in allowed:
            raise ValueError(f'Invalid {key}')
    u = urlsplit(p['source_url'])
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise ValueError('Source requires a public HTTPS link without credentials')
    if p['kind'] == 'pinterest_trend':
        if not p.get('keyword') or not p.get('trend_region') or u.hostname != 'trends.pinterest.com':
            raise ValueError('Trend requires keyword, source region and trends.pinterest.com URL')
        p.setdefault('pnk', '')
    if timestamp(p['observed_at']) > datetime.now(timezone.utc):
        raise ValueError('Observation cannot be in the future')
    for key in ('period_start','period_end'):
        if p.get(key):
            timestamp(p[key])
    if bool(p.get('period_start')) != bool(p.get('period_end')):
        raise ValueError('Provide both period boundaries')
    if p.get('period_end') and (timestamp(p['period_start']) > timestamp(p['period_end']) or timestamp(p['period_end']) > timestamp(p['observed_at'])):
        raise ValueError('Invalid observation period')
    p['price'] = str(emag_commerce.number(p['price'])) if p.get('price') not in (None,'') else None
    if p['kind'] == 'quote' and (not p.get('seller') or not p.get('comparison_key')):
        raise ValueError('Quote requires seller and comparable specification/delivery key')
    return p


def _insert(conn, store, snapshot_id, payload, actor, record_id=None, revision=0):
    if type(revision) is not int or revision < 0:
        raise ValueError('Invalid revision')
    if record_id is None:
        if revision != 0:
            raise ValueError('New record starts at revision zero')
        record_id = secrets.token_hex(16)
    old = conn.execute('SELECT revision,body FROM research WHERE store=? AND record_id=? ORDER BY revision DESC LIMIT 1', (store,record_id)).fetchone()
    if (old[0] if old else 0) != revision or (revision == 0 and old) or (revision > 0 and not old):
        raise ValueError('Record changed; reload first')
    if old:
        prior = json.loads(old[1])['payload']
        if any(prior.get(k) != payload.get(k) for k in (('kind','market') if prior['kind'] == 'pinterest_trend' else ('kind','pnk','market'))):
            raise ValueError('Record identity is immutable; create a new observation')
    body = {'record_id':record_id,'revision':revision+1,'snapshot_id':snapshot_id,'actor':actor,
            'created_at':datetime.now(timezone.utc).isoformat(),'payload':payload,'schema_version':1}
    conn.execute('INSERT INTO research(store,record_id,revision,body) VALUES (?,?,?,?)',(store,record_id,revision+1,json.dumps(body)))
    return body


def save(store, snapshot_id, payload, actor, record_id=None, revision=0):
    payload = validate(payload)
    with artifacts.snapshot_guard(), database() as conn:
        snap = emag_commerce.source(store)
        if snap['snapshot_id'] != snapshot_id:
            raise ValueError('Evidence is stale; reload first')
        conn.execute('BEGIN IMMEDIATE')
        return _insert(conn,store,snapshot_id,payload,actor,record_id,revision)


def import_rows(store, snapshot_id, rows, actor):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError('Import between 1 and 500 rows')
    checked = [validate(row) for row in rows]
    with artifacts.snapshot_guard(), database() as conn:
        snap = emag_commerce.source(store)
        if snap['snapshot_id'] != snapshot_id:
            raise ValueError('Evidence is stale; reload first')
        conn.execute('BEGIN IMMEDIATE')
        return {'records':[_insert(conn,store,snapshot_id,p,actor) for p in checked]}


def view(store):
    with artifacts.snapshot_guard():
        snap = emag_commerce.source(store)
        with database() as conn:
            rows = conn.execute('SELECT body FROM research WHERE store=? ORDER BY sequence DESC LIMIT 2001',(store,)).fetchall()
        history = [json.loads(r[0]) for r in rows[:2000]]
        latest = {}
        for row in history:
            latest.setdefault(row['record_id'],row)
        records = list(latest.values())
        for row in records:
            row['stale'] = row['snapshot_id'] != snap['snapshot_id']
            ids = [str(o['id']) for o in snap['data']['offers'] if row['payload'].get('pnk') and o.get('part_number_key') == row['payload']['pnk'] and row['payload']['market'] == 'RO']
            row['match'] = {'status':'matched' if len(ids)==1 else 'ambiguous' if ids else 'absent','product_ids':ids}
        groups = {}
        for row in records:
            p = row['payload']
            if p['kind'] != 'quote' or p['price'] is None or p['price_basis'] == 'unknown':
                continue
            key = tuple(p.get(k) for k in ('pnk','market','currency','price_basis','seller','comparison_key'))
            groups.setdefault(key,[]).append(p)
        comparisons = []
        conflicts = []
        for entries in groups.values():
            instants = {}
            for p in entries:
                instants.setdefault(timestamp(p['observed_at']), []).append(p)
            distinct = []
            for instant, samples in sorted(instants.items()):
                values = {(Decimal(p['price']), p['buy_button']) for p in samples}
                if len(values) > 1:
                    conflicts.append(samples[0]['pnk'])
                    continue
                distinct.append(samples[0])
            if len(distinct) < 2:
                continue
            before, after = distinct[-2:]
            comparisons.append({'pnk':after['pnk'],'seller':after['seller'],'currency':after['currency'],
                'market':after['market'],'comparison_key':after['comparison_key'],
                'price_basis':after['price_basis'],'before_at':before['observed_at'],'after_at':after['observed_at'],
                'price_change':f"{emag_commerce.number(after['price'])-emag_commerce.number(before['price']):.2f}",
                'buy_button_changed':after['buy_button'] != 'unknown' and before['buy_button'] != 'unknown' and after['buy_button'] != before['buy_button'],
                'source_url':after['source_url']})
        prompts = []
        costs = {str(p['offer']['id']):p for p in emag_commerce.view(store)['products']}
        for row in records:
            p = row['payload']
            reasons = []
            if row['stale']:
                reasons.append('review_snapshot')
            if row['match']['status'] == 'ambiguous':
                reasons.append('resolve_product_identity')
            own = costs.get(row['match']['product_ids'][0]) if row['match']['status'] == 'matched' else None
            if p['status'] == 'costing' or (own and (own['economics']['missing'] or own['record'] and own['record']['stale'])):
                reasons.append('confirm_costs')
            if (own and not row['stale'] and p['kind']=='quote' and p['market']=='RO' and p['currency']=='RON'
                    and p['price_basis']=='exclusive_vat' and p['price'] is not None):
                try:
                    if emag_commerce.number(own['offer'].get('sale_price')) > emag_commerce.number(p['price']):
                        reasons.append('review_own_price_gap')
                except ValueError:
                    pass
            prompts.extend({'record_id':row['record_id'],'pnk':p['pnk'],'reason':reason} for reason in reasons)
        for comparison in comparisons:
            for reason in (['review_price_change'] if Decimal(comparison['price_change']) != 0 else []) + (['review_buy_button_change'] if comparison['buy_button_changed'] else []):
                prompts.append({'record_id':'','pnk':comparison['pnk'],'reason':reason})
        prompts.extend({'record_id':'','pnk':pnk,'reason':'resolve_observation_conflict'} for pnk in sorted(set(conflicts)))
        return {'snapshot_id':snap['snapshot_id'],'records':records,'history':history,'truncated':len(rows)>2000,
                'comparisons':comparisons,'prompts':prompts,'marketplace_writes':False,
                'scope':'Observed samples only; historical changes do not establish current full-market conditions.'}
