"""Serialized manual read-only audits with immutable source/report references."""
import secrets
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from app.services import store_artifacts as artifacts, emag_operations, emag_business, emag_audit, automation_control


def _root(store_id):
    return artifacts._root() / 'jobs' / artifacts.validate_id(store_id)


def latest(store_id):
    import json
    return json.loads((_root(store_id) / 'latest.json').read_text('utf-8'))


def compare(before, after):
    def index(rows):
        result = {str(row['id']): row for row in rows}
        if len(result) != len(rows):
            raise ValueError('Duplicate product IDs')
        return result
    def normalized(value):
        if value is None: return None
        try:
            number = Decimal(str(value))
            return number if number.is_finite() else str(value)
        except InvalidOperation:
            return str(value)
    def has_details(value):
        values = value if isinstance(value, list) else [value]
        return any(isinstance(item, dict) and 'error_details' in item for item in values)
    def without_details(value):
        if isinstance(value, list): return [without_details(item) for item in value]
        if isinstance(value, dict): return {k: v for k, v in value.items() if k not in ('error_details', 'error_details_truncated')}
        return value
    old, new = index(before), index(after)
    result = []
    for key in sorted(old.keys() | new.keys()):
        if key not in old or key not in new:
            result.append({'id': key, 'field': 'observed_product', 'before': key in old, 'after': key in new})
            continue
        for field in ('sale_price','general_stock','offer_validation_status','validation_status'):
            a,b = old[key].get(field),new[key].get(field)
            if field in ('sale_price','general_stock'):
                equal = normalized(a) == normalized(b)
            elif has_details(a) != has_details(b):
                equal = without_details(a) == without_details(b)
            else:
                equal = a == b
            if not equal: result.append({'id': key,'field': field,'before': a,'after': b})
    return result


def run(store_id, collect_fn=None):
    root = _root(store_id)
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / 'run-lock.sqlite3', timeout=0)
    try:
        # Fail before collecting if another process holds this store's lock.
        try:
            conn.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as exc:
            if getattr(exc, 'sqlite_errorcode', None) not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or not automation_control.view(store_id)['paused']:
                raise
            # A paused invocation may skip while the active worker drains. It
            # gets its own receipt without replacing that worker's latest pointer.
            now = datetime.now(timezone.utc).isoformat()
            skipped = {'run_id':secrets.token_hex(16), 'store_id':store_id,
                       'started_at':now, 'finished_at':now, 'status':'paused', 'stage':'paused',
                       'mode':'fresh_collection' if collect_fn else 'existing_snapshot'}
            artifacts._write_new(root / (skipped['run_id']+'.json'), skipped)
            return skipped
        token = automation_control.current_store.set(store_id)
        receipt = {'run_id': secrets.token_hex(16),'store_id': store_id,
                       'started_at': datetime.now(timezone.utc).isoformat(),
                       'mode': 'fresh_collection' if collect_fn else 'existing_snapshot','stage': 'source','status': 'running'}
        try:
            automation_control.checkpoint()
            try: previous = artifacts.read_snapshot(store_id)
            except FileNotFoundError: previous = None
            if collect_fn:
                receipt['stage']='collection'
                evidence=collect_fn()
                automation_control.checkpoint()
                snapshot=emag_business.publish(store_id,evidence)
            elif previous:
                snapshot=previous
            else:
                raise FileNotFoundError('Collect evidence first')
            automation_control.checkpoint()
            receipt['snapshot_id']=snapshot['snapshot_id']
            issues=emag_operations._issues(snapshot)
            receipt['stage']='report'
            delta = compare(previous['data']['offers'],snapshot['data']['offers']) if collect_fn and previous else []
            receipt['baseline_snapshot_id']=previous['snapshot_id'] if collect_fn and previous else None
            receipt['delta_available']=bool(collect_fn and previous)
            receipt['change_count']=len(delta)
            # Two individually valid snapshots can produce a delta larger than
            # either source. Keep a bounded preview; full evidence stays in the
            # immutable baseline/current snapshots referenced by the receipt.
            preview=[]
            for change in delta[:200]:
                if len(json.dumps(preview+[change],ensure_ascii=False).encode('utf-8'))>64000:
                    break
                preview.append(change)
            receipt['changes']=preview
            receipt['changes_truncated']=len(preview)!=len(delta)
            history, history_incomplete = emag_audit.history(snapshot)
            from app.services import emag_decisions, emag_clearance
            clearance=emag_clearance.build(snapshot,history,history_incomplete)
            diagnostics = emag_decisions.diagnose(snapshot)
            diagnostic_lines=[]
            for finding in diagnostics['findings']:
                gate=emag_decisions.verify(finding,snapshot)
                if not gate['valid']:raise ValueError('Invalid diagnostic evidence')
                line=json.dumps(finding,ensure_ascii=False,allow_nan=False)
                if len((''.join(diagnostic_lines)+line).encode('utf-8'))>48000:break
                diagnostic_lines.append(line)
            receipt['decision_gate']={'included_findings_valid':True,'findings_checked':len(diagnostic_lines),
                'findings_total':len(issues),'truncated':len(diagnostic_lines)<len(issues),
                'all_findings_verified':len(diagnostic_lines)==len(issues),'model_used':False}
            issue_details = emag_audit.render_issues(snapshot, history, previous if collect_fn else None,
                                                      history_incomplete=history_incomplete)
            text = '\n'.join(['# eMAG manual audit',f"Source: {snapshot['snapshot_id']}",
                f"Captured: {snapshot['captured_at']}",f"Mode: {receipt['mode']}",
                f"Offers: {len(snapshot['data']['offers'])}; issue reasons: {len(issues)}",
                f"Observed field changes: {len(delta)} (baseline available: {receipt['delta_available']})",
                'Missing stock is unknown, not zero. Missing products are observations, not confirmed delistings.',
                'No marketplace writes. Costs must be supplied before pricing/profit decisions.',
                emag_clearance.render(clearance),
                issue_details,
                '## Issue references (first 200)',
                *[f"- Product {emag_audit._cell(i['id'], 100)}: {emag_audit._cell(i['reason'], 50)}" for i in issues[:200]],
                f"Issue references truncated: {len(issues)>200}",
                '## Change preview','', '    '+json.dumps(preview,ensure_ascii=False), '',
                f"Change preview truncated: {receipt['changes_truncated']}; compare the referenced source snapshots for complete evidence.",
                '## Structured diagnostic evidence (bounded)',*['    '+line for line in diagnostic_lines],
                f"Diagnostic evidence truncated: {diagnostics['findings_truncated'] or len(diagnostic_lines)<len(diagnostics['findings'])}",
                '## Source limitations',*['- '+emag_audit._cell(x, 500) for x in snapshot['limitations']]])
            automation_control.checkpoint()
            report=artifacts.save_report(store_id,snapshot['snapshot_id'],'eMAG manual audit',text)
            receipt.update(report_id=report['report_id'],status='complete',stage='complete')
        except automation_control.Paused:
            receipt.update(status='paused',stage='paused')
        except Exception as exc:
            # Never persist exception text: HTTP errors may contain credential-bearing URLs/payloads.
            receipt.update(status='failed',error_type=type(exc).__name__)
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        artifacts._write_new(root / (receipt['run_id']+'.json'),receipt)
        artifacts._write_new(root / 'latest.json',receipt)
        conn.commit()
        return receipt
    finally:
        if 'token' in locals():
            automation_control.current_store.reset(token)
        conn.close()
