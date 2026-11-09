"""Deliver prepared digests with the owner's CLI; no credentials or listener."""
from datetime import datetime, time, timedelta
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from zoneinfo import ZoneInfo

from app.services.emag_digest import period, _aware


def _command(argv):
    if (not isinstance(argv, list) or not argv or len(argv) > 32
            or any(not isinstance(arg, str) or not arg or '\0' in arg for arg in argv)
            or not Path(argv[0]).is_absolute()):
        raise ValueError('Commands require a bounded argv with an absolute executable')
    return list(argv)


def validate_config(config):
    from app.services.store_artifacts import validate_id
    if not isinstance(config, dict) or type(config.get('enabled')) is not bool:
        raise ValueError('An explicit enabled flag is required')
    validate_id(config.get('store_id'))
    for key, prefix in (('app_id', 'cli_'), ('recipient_open_id', 'ou_')):
        if not isinstance(config.get(key), str) or not re.fullmatch(prefix + r'[A-Za-z0-9_]{1,100}', config[key]):
            raise ValueError('Invalid application or recipient identity')
    ZoneInfo(config['timezone'])
    if config.get('locale') not in ('en', 'zh-CN') or not Path(config['state_dir']).is_absolute():
        raise ValueError('An absolute private state path and supported locale are required')
    if type(config.get('image_enabled', False)) is not bool:
        raise ValueError('image_enabled must be boolean')
    if config.get('font_path') is not None and (not isinstance(config['font_path'], str) or not Path(config['font_path']).is_absolute()):
        raise ValueError('font_path requires an absolute local path')
    _command(config['cli_command'])
    for kind in ('daily', 'weekly'):
        _command(config['source_commands'][kind])
    timeout = config.get('timeout_seconds', 90)
    if type(timeout) not in (int, float) or not 0 < timeout <= 120:
        raise ValueError('Timeout must be within 0–120 seconds')
    return config


def _execute(argv, timeout, text=None):
    # Keep diagnostic output private and memory bounded, including malformed CLI output.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        result = subprocess.run(argv, input=text if isinstance(text, bytes) else None if text is None else text.encode('utf-8'),
                                stdout=output, stderr=errors, timeout=timeout, check=False)
        output.seek(0)
        raw = output.read(65537)
        if not raw and result.returncode != 0:
            errors.seek(0)
            raw = errors.read(65537)
    if len(raw) > 65536:
        raise ValueError('Command output exceeds the protocol bound')
    return result.returncode, json.loads(raw.decode('utf-8-sig'))


def _report(config, kind, now):
    code, report = _execute(_command(config['source_commands'][kind]), config.get('timeout_seconds', 90))
    expected = {'schema_version': 1, 'store_id': config['store_id'], 'kind': kind,
                'period': period(kind, now, config['timezone']), 'timezone': config['timezone'],
                'locale': config['locale']}
    if code != 0 or not isinstance(report, dict) or any(report.get(k) != v for k, v in expected.items()):
        raise ValueError('Source report does not match the configured delivery')
    generated = _aware(report.get('generated_at'))
    if generated is None or abs((generated - now).total_seconds()) > 900:
        raise ValueError('Source generation clock is stale or inconsistent')
    markdown = report.get('markdown')
    if (not isinstance(markdown, str) or not markdown.strip() or len(markdown.encode('utf-8')) > 16000
            or len(json.dumps(report, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 32000):
        raise ValueError('Invalid bounded report body')
    return report


def _verify_bot(config):
    code, identity = _execute(_command(config['cli_command']) + ['whoami', '--as', 'bot'],
                              config.get('timeout_seconds', 90))
    if (code != 0 or not isinstance(identity, dict) or identity.get('appId') != config['app_id']
            or identity.get('identity') != 'bot' or identity.get('available') is not True):
        raise ValueError('Configured bot application is unavailable or mismatched')


def _due(kind, now, zone):
    local = now.astimezone(ZoneInfo(zone))
    if kind == 'daily':
        return local.time() >= time(9)
    monday = local.date() - timedelta(days=local.weekday())
    return local >= datetime.combine(monday, time(9, 10), local.tzinfo)


def _key(config, kind, now, correction_id=None):
    identity = [config[k] for k in ('app_id', 'recipient_open_id', 'store_id', 'timezone', 'locale')]
    if correction_id is not None:
        identity += ['correction', correction_id]
    return hashlib.sha256(json.dumps(identity + [kind, period(kind, now, config['timezone'])],
                                      sort_keys=True).encode()).hexdigest()[:48]


def _receipt(row):
    return {'delivery_id': row[0], 'status': 'unknown' if row[1] == 'sending' else row[1],
            'message_id': row[2]}


def _run_text(config, now, kind=None, preview=False, *, correction_id=None):
    validate_config(config)
    if kind not in (None, 'daily', 'weekly'):
        raise ValueError('Unsupported report kind')
    if correction_id is not None:
        from app.services.store_artifacts import validate_id
        validate_id(correction_id)
        if kind is None:
            raise ValueError('Corrections require an explicit report kind')
    if not config['enabled'] and not preview:
        return []
    kinds = [kind] if kind else [k for k in ('daily', 'weekly') if _due(k, now, config['timezone'])]
    results = []
    for selected in kinds:
        key = _key(config, selected, now, correction_id)
        def prepare():
            report = _report(config, selected, now)
            if correction_id is not None:
                label = ('更正版：替代此前同一统计区间的报告。' if config['locale'] == 'zh-CN' else
                         'Correction: replaces the earlier report for this same period.')
                report = {**report, 'markdown': label + '\n\n' + report['markdown']}
                if (len(report['markdown'].encode('utf-8')) > 16000
                        or len(json.dumps(report, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 32000):
                    raise ValueError('Correction exceeds report bounds')
            return report
        if preview:
            results.append({'delivery_id': key, 'status': 'preview', 'report': prepare()})
            continue
        root = Path(config['state_dir'])
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with sqlite3.connect(root / 'delivery.sqlite3', timeout=30) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, status TEXT NOT NULL, '
                         'message_id TEXT, created_at TEXT NOT NULL, finished_at TEXT, payload TEXT NOT NULL)')
            original_key = _key(config, selected, now)
            if correction_id is not None:
                original = conn.execute('SELECT status,message_id FROM deliveries WHERE id=?', (original_key,)).fetchone()
                if not original or original[0] != 'delivered' or not original[1]:
                    raise ValueError('Correction requires a confirmed delivered original')
            existing = conn.execute('SELECT id,status,message_id FROM deliveries WHERE id=?', (key,)).fetchone()
            if existing:
                results.append(_receipt(existing))
                continue
            report = prepare()
            _verify_bot(config)
            payload = {'app_id': config['app_id'], 'recipient_open_id': config['recipient_open_id'], 'report': report}
            if correction_id is not None:
                payload.update(correction_id=correction_id, correction_of=original_key)
            # Commit intent before any submission. A crash leaves a terminal
            # unknown outcome: another process must never try this key again.
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute('SELECT id,status,message_id FROM deliveries WHERE id=?', (key,)).fetchone()
            if existing:
                conn.rollback()
                results.append(_receipt(existing))
                continue
            conn.execute('INSERT INTO deliveries VALUES (?,?,NULL,?,NULL,?)',
                         (key, 'sending', now.isoformat(), json.dumps(payload, ensure_ascii=False, allow_nan=False)))
            conn.commit()
            status, message_id = 'unknown', None
            try:
                code, response = _execute(_command(config['cli_command']) + [
                    'im', '+messages-send', '--as', 'bot', '--user-id', config['recipient_open_id'],
                    '--markdown', '-', '--idempotency-key', key],
                    config.get('timeout_seconds', 90), report['markdown'])
                if isinstance(response, dict):
                    data = response.get('data')
                    candidate = data.get('message_id') if isinstance(data, dict) else None
                    if (code == 0 and response.get('ok') is True and response.get('identity') == 'bot'
                            and isinstance(candidate, str) and re.fullmatch(r'om_[A-Za-z0-9_-]+', candidate)):
                        status, message_id = 'delivered', candidate
                    elif response.get('ok') is False:
                        status = 'rejected'
            except (OSError, ValueError, subprocess.TimeoutExpired):
                # No exception strings: CLI errors may contain private paths/content.
                status = 'unknown'
            conn.execute('UPDATE deliveries SET status=?,message_id=?,finished_at=? WHERE id=?',
                         (status, message_id, datetime.now(now.tzinfo).isoformat(), key))
            conn.commit()
            results.append({'delivery_id': key, 'status': status, 'message_id': message_id})
    return results


def _deliver_image(config, now, receipt):
    """Claim an independent image once, using the already delivered text's payload."""
    if receipt['status'] != 'delivered':
        return receipt
    root = Path(config['state_dir'])
    key = receipt['delivery_id']
    with sqlite3.connect(root / 'delivery.sqlite3', timeout=30) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS images (id TEXT PRIMARY KEY,status TEXT NOT NULL, '
                     'image_key TEXT,message_id TEXT,finished_at TEXT)')
        conn.execute('BEGIN IMMEDIATE')
        existing = conn.execute('SELECT status,message_id FROM images WHERE id=?',(key,)).fetchone()
        if existing:
            return {**receipt,'image_status':'unknown' if existing[0]=='sending' else existing[0],
                    'image_message_id':existing[1]}
        stored = conn.execute('SELECT payload FROM deliveries WHERE id=? AND status=?',(key,'delivered')).fetchone()
        if not stored:
            raise ValueError('Image requires confirmed text and retained source payload')
        report = json.loads(stored[0])['report']
        if 'visual' not in report:
            return {**receipt,'image_status':'skipped_legacy','image_message_id':None}
        visual = report.get('visual')
        if (not isinstance(visual, dict) or visual.get('schema_version') != 1
                or visual.get('snapshot_id') != report.get('snapshot_id')):
            return {**receipt,'image_status':'unavailable','image_message_id':None}
        # Rendering is local and retryable. No upload/send intent exists on render failure.
        from app.services.emag_digest_visual import render
        destination = root / 'images' / (key + '.png')
        try:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if destination.parent.is_symlink() or destination.is_symlink():
                raise ValueError('Image artifact symlinks are forbidden')
            render(report, destination, font_path=config.get('font_path'))
        except (ValueError, OSError, KeyError, TypeError, ImportError):
            return {**receipt,'image_status':'render_failed','image_message_id':None}
        _verify_bot(config)
        conn.execute('INSERT INTO images VALUES (?,?,NULL,NULL,NULL)',(key,'sending'))
        conn.commit()
        status, image_key, message_id = 'unknown', None, None
        try:
            code, response = _execute(_command(config['cli_command']) + [
                'im','images','create','--as','bot','--data','{"image_type":"message"}','--file','-'],
                config.get('timeout_seconds',90), destination.read_bytes())
            if code == 0 and response.get('ok') is True and response.get('identity') == 'bot':
                candidate = response.get('data',{}).get('image_key')
                if isinstance(candidate,str) and re.fullmatch(r'img_[A-Za-z0-9_-]+',candidate):
                    image_key = candidate
                    # Persist uploaded identity before attempting exactly one message.
                    conn.execute('UPDATE images SET image_key=? WHERE id=?',(image_key,key));conn.commit()
                    code,response = _execute(_command(config['cli_command']) + [
                        'im','+messages-send','--as','bot','--user-id',config['recipient_open_id'],
                        '--image',image_key,'--idempotency-key',key+'i'],config.get('timeout_seconds',90))
                    candidate=response.get('data',{}).get('message_id')
                    if (code == 0 and response.get('ok') is True and response.get('identity')=='bot'
                            and isinstance(candidate,str) and re.fullmatch(r'om_[A-Za-z0-9_-]+',candidate)):
                        status,message_id='delivered',candidate
                    elif response.get('ok') is False:
                        status='rejected'
            elif response.get('ok') is False:
                status='rejected'
        except (OSError,ValueError,AttributeError,TypeError,subprocess.TimeoutExpired):
            status='unknown'
        conn.execute('UPDATE images SET status=?,image_key=?,message_id=?,finished_at=? WHERE id=?',
                     (status,image_key,message_id,datetime.now(now.tzinfo).isoformat(),key));conn.commit()
        return {**receipt,'image_status':status,'image_message_id':message_id}


def run(config, now, kind=None, preview=False, *, correction_id=None):
    results = _run_text(config, now, kind, preview, correction_id=correction_id)
    if preview or not config.get('image_enabled',False):
        return results
    return [_deliver_image(config,now,result) for result in results]
