"""Real subprocess/SQLite delivery tests; no live Feishu requests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from app.services import emag_digest_delivery as delivery
from app.services.emag_digest import build


NOW = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)


@pytest.fixture
def configured(tmp_path):
    report = build(None, 'daily', NOW, locale='zh-CN', store_id='test-ro')
    (tmp_path / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    # The executable models only the external protocol; the real ledger,
    # schedule, report validation and subprocess dispatch run unmocked.
    fake = tmp_path / 'external.py'
    fake.write_text('''import json,sys,time
from pathlib import Path
root=Path(__file__).parent
mode=(root/'mode').read_text() if (root/'mode').exists() else 'success'
args=sys.argv[1:]
if args==['source']:
    print((root/'report.json').read_text());sys.exit(0)
if args==['whoami','--as','bot']:
    print(json.dumps({'appId':'wrong' if mode=='wrong_app' else 'cli_test','identity':'bot','available':True}));sys.exit(0)
assert args[:2]==['im','+messages-send']
assert args[args.index('--as')+1]=='bot'
assert args[args.index('--user-id')+1]=='ou_test'
assert args[args.index('--markdown')+1]=='-'
text=sys.stdin.read()
with (root/'sends').open('a',encoding='utf-8') as f:f.write(json.dumps({'text':text,'argv':args})+'\\n')
if mode=='timeout':time.sleep(2)
if mode=='bad_json':print('oops');sys.exit(0)
if mode=='nonzero':print(json.dumps({'ok':True,'data':{'message_id':'om_test'}}));sys.exit(1)
if mode=='rejected':print(json.dumps({'ok':False,'error':{'type':'authorization'}}),file=sys.stderr);sys.exit(1)
if mode=='no_id':print(json.dumps({'ok':True,'identity':'bot','data':{}}));sys.exit(0)
if mode=='wrong_identity':print(json.dumps({'ok':True,'identity':'user','data':{'message_id':'om_test'}}));sys.exit(0)
print(json.dumps({'ok':True,'identity':'bot','data':{'message_id':'om_test'}}))
''', encoding='utf-8')
    config = {'enabled': True, 'store_id': 'test-ro', 'app_id': 'cli_test',
              'recipient_open_id': 'ou_test', 'timezone': 'Europe/Bucharest', 'locale': 'zh-CN',
              'state_dir': str(tmp_path / 'state'), 'cli_command': [sys.executable, str(fake)],
              'source_commands': {'daily': [sys.executable, str(fake), 'source'],
                                  'weekly': [sys.executable, str(fake), 'source']},
              'timeout_seconds': 1}
    return config, tmp_path


def sends(root):
    p = root / 'sends'
    return [json.loads(row) for row in p.read_text().splitlines()] if p.exists() else []


def test_receipt_requires_message_id_and_second_invocation_cannot_resend(configured):
    config, root = configured
    first = delivery.run(config, NOW, kind='daily')
    second = delivery.run(config, NOW, kind='daily')
    assert first[0]['status'] == 'delivered'
    assert first[0]['message_id'] == 'om_test'
    assert second[0]['status'] == 'delivered'
    assert len(sends(root)) == 1
    assert '暂' in sends(root)[0]['text']


def test_preview_does_not_send_or_create_a_delivery_ledger(configured):
    config, root = configured
    result = delivery.run(config, NOW, kind='daily', preview=True)
    assert result[0]['status'] == 'preview'
    assert sends(root) == []
    assert not Path(config['state_dir']).exists()


@pytest.mark.parametrize('mode', ['bad_json', 'nonzero', 'timeout', 'no_id', 'wrong_identity'])
def test_uncertain_send_is_terminal_and_never_automatically_retried(configured, mode):
    config, root = configured
    (root / 'mode').write_text(mode)
    assert delivery.run(config, NOW, kind='daily')[0]['status'] == 'unknown'
    delivery.run(config, NOW, kind='daily')
    assert len(sends(root)) == 1


def test_explicit_rejection_is_not_success_or_silently_retried(configured):
    config, root = configured
    (root / 'mode').write_text('rejected')
    assert delivery.run(config, NOW, kind='daily')[0]['status'] == 'rejected'
    delivery.run(config, NOW, kind='daily')
    assert len(sends(root)) == 1


def test_wrong_app_blocks_submission(configured):
    config, root = configured
    (root / 'mode').write_text('wrong_app')
    with pytest.raises(ValueError):
        delivery.run(config, NOW, kind='daily')
    assert sends(root) == []


@pytest.mark.parametrize(('key', 'value'), [('store_id', 'other'), ('locale', 'en'),
                                        ('period', {'start': '2026-11-01', 'end': '2026-11-02'})])
def test_remote_report_contract_mismatch_is_never_sent(configured, key, value):
    config, root = configured
    report = json.loads((root / 'report.json').read_text())
    report[key] = value
    (root / 'report.json').write_text(json.dumps(report))
    with pytest.raises(ValueError):
        delivery.run(config, NOW, kind='daily')
    assert sends(root) == []


def test_concurrent_invocations_claim_a_period_only_once(configured):
    config, root = configured
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: delivery.run(config, NOW, kind='daily'), range(2)))
    assert len(sends(root)) == 1
    assert all(r[0]['status'] in ('delivered', 'unknown') for r in results)


def test_interrupted_intent_stays_unknown(configured):
    config, root = configured
    delivery.run(config, NOW, kind='daily')
    with sqlite3.connect(Path(config['state_dir']) / 'delivery.sqlite3') as conn:
        conn.execute("UPDATE deliveries SET status='sending', message_id=NULL")
    assert delivery.run(config, NOW, kind='daily')[0]['status'] == 'unknown'
    assert len(sends(root)) == 1


def test_due_skips_daily_before_nine_and_catches_up_week_once(configured):
    config, root = configured
    early = datetime(2026, 11, 9, 6, 59, tzinfo=timezone.utc)
    assert delivery.run(config, early) == []
    # Tuesday before 09:00: only the latest due weekly period is eligible.
    tuesday = datetime(2026, 11, 10, 6, tzinfo=timezone.utc)
    report = build(None, 'weekly', tuesday, locale='zh-CN', store_id='test-ro')
    (root / 'report.json').write_text(json.dumps(report))
    assert delivery.run(config, tuesday)[0]['status'] == 'delivered'
    assert len(sends(root)) == 1


def test_disabled_due_has_no_external_side_effects(configured):
    config, root = configured
    config['enabled'] = False
    assert delivery.run(config, NOW) == []
    assert sends(root) == []


def test_explicit_correction_preserves_original_and_deduplicates_its_own_send(configured):
    config, root = configured
    original = delivery.run(config, NOW, kind='daily')[0]
    corrected = delivery.run(config, NOW, kind='daily', correction_id='calendar-metrics')[0]
    repeated = delivery.run(config, NOW, kind='daily', correction_id='calendar-metrics')[0]
    assert corrected['status'] == repeated['status'] == 'delivered'
    assert corrected['delivery_id'] != original['delivery_id']
    assert repeated['delivery_id'] == corrected['delivery_id']
    assert len(sends(root)) == 2
    assert '更正版' in sends(root)[1]['text']
    with sqlite3.connect(Path(config['state_dir']) / 'delivery.sqlite3') as conn:
        records = [json.loads(row[0]) for row in conn.execute('SELECT payload FROM deliveries ORDER BY rowid')]
    assert '更正版' not in records[0]['report']['markdown']
    assert records[1]['correction_of'] == original['delivery_id']


@pytest.mark.parametrize('state', ['missing', 'unknown'])
def test_correction_cannot_resend_an_unconfirmed_original(configured, state):
    config, root = configured
    if state == 'unknown':
        (root / 'mode').write_text('bad_json')
        delivery.run(config, NOW, kind='daily')
    before = len(sends(root))
    with pytest.raises(ValueError):
        delivery.run(config, NOW, kind='daily', correction_id='calendar-metrics')
    assert len(sends(root)) == before


def test_scheduled_invocation_cannot_enable_correction_mode(configured):
    config, root = configured
    with pytest.raises(ValueError):
        delivery.run(config, NOW, correction_id='calendar-metrics')
    assert sends(root) == []
