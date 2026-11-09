"""Durable, fixed read-only browser checks; independent of API scheduler slots."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
from app.services import automation_control, store_artifacts

WAITING = {'waiting_verification', 'waiting_login', 'waiting_browser', 'waiting_retry', 'needs_review', 'paused'}
_ID = re.compile(r'[a-f0-9]{32}\Z')


def _settings():
    from app.core.config import settings
    return settings


def _root():
    return _settings().data_dir / 'browser-checks'


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    root = _root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    db_path = root / 'tasks.sqlite3'
    os.close(os.open(db_path, os.O_CREAT | os.O_RDWR, 0o600))
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, store_id TEXT UNIQUE NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL)')
        conn.execute('BEGIN IMMEDIATE')
        with conn:
            yield conn
    finally:
        conn.close()


@contextmanager
def _lease(name):
    _root().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_root() / (name + '.lock.sqlite3'), timeout=0)
    try:
        try:
            conn.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as exc:
            if getattr(exc, 'sqlite_errorcode', None) not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise
            yield False
        else:
            yield True
            conn.rollback()
    finally:
        conn.close()


def _get(conn, store_id):
    row = conn.execute('SELECT * FROM tasks WHERE store_id=?', (store_id,)).fetchone()
    return {**json.loads(row['payload']), **{k:row[k] for k in ('task_id','store_id','state','revision')}} if row else None


def _save(conn, task, state):
    task = {**task, 'state':state, 'revision':task['revision'] + 1, 'updated_at':_now()}
    conn.execute('INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?)',
                 (task['task_id'], task['store_id'], state, task['revision'], json.dumps(task)))
    return task


def view(store_id):
    store_artifacts.validate_id(store_id)
    with _db() as conn:
        task = _get(conn, store_id)
        if task and task['state'] == 'running':
            with _lease(task['task_id']) as free:
                if free:
                    task = _save(conn, task, 'needs_review')
        return task


def _binding(store_id):
    if (os.environ.get('IVYEA_OPS_BROWSER_STORE_ID') != store_id
            or not os.environ.get('IVYEA_OPS_BROWSER_ACCOUNT', '').strip()):
        raise ValueError('Browser account binding is unavailable for this store')


def available(store_id):
    return (os.environ.get('IVYEA_OPS_BROWSER_STORE_ID') == store_id
            and bool(os.environ.get('IVYEA_OPS_BROWSER_ACCOUNT', '').strip()))


def request(store_id, revision, actor):
    store_artifacts.validate_id(store_id)
    snapshot = store_artifacts.read_snapshot(store_id)
    if snapshot['platform'] != 'emag' or snapshot['marketplace'] != 'RO':
        raise ValueError('Browser check is only available for eMAG RO')
    _binding(store_id)
    if automation_control.view(store_id)['paused']:
        raise ValueError('Automatic monitoring is paused')
    # Reconcile orphaned reads before considering resume. Unknown external writes
    # never use this protocol: the only worker is a fixed read-only FBE reader.
    view(store_id)
    with _db() as conn:
        task = _get(conn, store_id)
        if task:
            if revision is None:
                return task
            if type(revision) is not int or revision != task['revision'] or task['state'] == 'running':
                raise ValueError('Browser task changed; reload before continuing')
            if task['state'] == 'queued':
                return task
            task['resume_from'] = task['state']
            task['attempts'] += 1
            task['actor'] = str(actor)
            task['snapshot_id'] = snapshot['snapshot_id']
            return _save(conn, task, 'queued')
        if revision is not None:
            raise ValueError('Browser task is missing')
        task = {'task_id':secrets.token_hex(16), 'store_id':store_id, 'kind':'fbe_inventory',
                'revision':-1, 'state':'queued', 'attempts':1, 'actor':str(actor),
                'snapshot_id':snapshot['snapshot_id'], 'checkpoint':'inventory_page',
                'last_success_at':None, 'evidence_id':None, 'observed_rows':None,
                'coverage':'visible_page', 'created_at':_now()}
        return _save(conn, task, 'queued')


def _read(task):
    node = Path(os.environ.get('IVYEA_OPS_BROWSER_NODE', ''))
    sdk = Path(os.environ.get('IVYEA_OPS_BROWSER_SDK_ROOT', ''))
    if not node.is_absolute() or not node.is_file() or not sdk.is_absolute() or not sdk.is_dir():
        return {'state':'waiting_browser'}
    # Source and frozen layouts share the existing repository-root resolver.
    script = _settings().root_dir / 'scripts' / 'browser-fbe-reader.mjs'
    try:
        completed = subprocess.run([str(node), str(script), task['task_id']], capture_output=True,
                                   env={**os.environ, 'IVYEA_OPS_BROWSER_RESUME_FROM':task.get('resume_from','')},
                                   timeout=150, check=False, encoding='utf-8', errors='strict')
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return {'state':'waiting_browser'}
    if completed.returncode or len(completed.stdout) > 200000:
        return {'state':'needs_review'}
    try:
        return json.loads(completed.stdout)
    except ValueError:
        return {'state':'needs_review'}


def _validate(result):
    if not isinstance(result, dict):
        raise ValueError('Invalid browser result')
    state = result.get('state')
    if state in WAITING and set(result) == {'state'}:
        return result
    if state != 'complete' or set(result) != {'state','rows','coverage'} or result['coverage'] != 'visible_page':
        raise ValueError('Invalid browser coverage')
    rows = result['rows']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('No verified browser rows')
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id','stock'}
                or not isinstance(row['id'], str) or not re.fullmatch(r'[0-9]{1,20}', row['id'])
                or row['id'] in seen or (row['stock'] is not None and (type(row['stock']) is not int or not 0 <= row['stock'] <= 100000000))):
            raise ValueError('Invalid browser row')
        seen.add(row['id'])
    return result


def run(store_id, task_id, *, reader=None):
    store_artifacts.validate_id(store_id)
    if not isinstance(task_id, str) or not _ID.fullmatch(task_id):
        raise ValueError('Invalid task ID')
    with _lease(task_id) as acquired:
        if not acquired:
            return
        with _db() as conn:
            task = _get(conn, store_id)
            if not task or task['task_id'] != task_id or task['state'] != 'queued':
                return
            task = _save(conn, task, 'running')
        try:
            _binding(store_id)
            if automation_control.view(store_id)['paused']:
                result = {'state':'paused'}
            else:
                # Serialize all browser clients without using the Go API slots.
                with _lease('bridge') as bridge_free:
                    result = (reader() if reader else _read(task)) if bridge_free else {'state':'waiting_browser'}
                result = _validate(result)
            if automation_control.view(store_id)['paused']:
                result = {'state':'paused'}
        except Exception:
            # Exception strings and MCP transcripts may contain private URLs.
            result = {'state':'needs_review'}
        with automation_control.publication_guard(store_id) as paused:
            if paused:
                result = {'state':'paused'}
            with _db() as conn:
                current = _get(conn, store_id)
                if current['task_id'] != task_id or current['revision'] != task['revision']:
                    return
                if result['state'] == 'complete':
                    evidence_id = secrets.token_hex(16)
                    now = _now()
                    evidence = {**result, 'evidence_id':evidence_id, 'store_id':store_id,
                                'task_id':task_id, 'snapshot_id':task['snapshot_id'], 'observed_at':now,
                                'source':'emag_fbe_browser', 'marketplace_writes':False}
                    path = _root() / 'evidence'
                    path.mkdir(exist_ok=True)
                    with (path / (evidence_id + '.json')).open('x', encoding='utf-8') as stream:
                        json.dump(evidence, stream, allow_nan=False)
                    current.update(last_success_at=now, evidence_id=evidence_id, observed_rows=len(result['rows']))
                _save(conn, current, result['state'])


def launch(store_id, task_id):
    """Spawn only the fixed worker, never a user-supplied command."""
    store_artifacts.validate_id(store_id)
    if not isinstance(task_id, str) or not _ID.fullmatch(task_id):
        raise ValueError('Invalid task ID')
    from app.core.layout import code_root
    try:
        subprocess.Popen([sys.executable, '-m', 'app.browser_worker', store_id, task_id],
                         cwd=code_root(_settings().root_dir) / 'server',
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        with _db() as conn:
            task = _get(conn, store_id)
            if task and task['task_id'] == task_id and task['state'] == 'queued':
                _save(conn, task, 'waiting_browser')


def schedule(store_id):
    """An optional post-success hook, not another API collection scheduler."""
    if os.environ.get('IVYEA_OPS_BROWSER_AUTO_CHECK') != '1' or not available(store_id):
        return
    try:
        task = view(store_id)
        if task:
            if task['state'] != 'complete':
                return
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(task['last_success_at'])).total_seconds()
            if age < 86400:
                return
        task = request(store_id, task['revision'] if task else None, 'supervisor')
        launch(store_id, task['task_id'])
    except (OSError, ValueError, sqlite3.Error):
        # Browser availability must never change a successful API receipt.
        return
