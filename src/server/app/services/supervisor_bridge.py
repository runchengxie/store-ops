"""Fixed read-only worker protocol with durable, non-replayable job identities."""
from contextlib import contextmanager
import json
import os
import re
import secrets
import sqlite3

from app.core.config import settings
from app.services import automation_control, emag_jobs, store_artifacts

_JOB = re.compile(r'[a-f0-9]{32}\Z')
_STATES = {'running', 'unknown', 'complete', 'paused', 'failed'}


def _validate(store_id, job_id):
    store_artifacts.validate_id(store_id)
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError('Invalid job ID')


def _path(job_id):
    return settings.data_dir / 'emag' / 'supervisor-jobs' / (job_id + '.json')


def _sync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.' + secrets.token_hex(16) + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        _sync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def _read(store_id, job_id):
    path = _path(job_id)
    try:
        with path.open('rb') as stream:
            raw = stream.read(4097)
    except FileNotFoundError:
        return None
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('Invalid job record') from exc
    if (len(raw) > 4096 or not isinstance(record, dict)
            or set(record) - {'job_id', 'store_id', 'status', 'receipt_id'}
            or record.get('job_id') != job_id or record.get('store_id') != store_id
            or not isinstance(record.get('status'), str) or record['status'] not in _STATES
            or ('receipt_id' in record and not _JOB.fullmatch(str(record['receipt_id'])))
            or (record.get('status') in {'complete', 'paused', 'failed'} and 'receipt_id' not in record)):
        raise ValueError('Invalid job identity or record')
    return record


@contextmanager
def _lock(job_id, *, intent=False):
    path = _path(job_id).with_suffix('.intent.sqlite3' if intent else '.sqlite3')
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5 if intent else 0)
    acquired = False
    try:
        try:
            conn.execute('BEGIN IMMEDIATE')
            acquired = True
        except sqlite3.OperationalError as exc:
            if getattr(exc, 'sqlite_errorcode', None) not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise
        yield acquired
    finally:
        if acquired:
            conn.rollback()
        conn.close()


def receipt(store_id, job_id):
    _validate(store_id, job_id)
    record = _read(store_id, job_id)
    if record is None:
        return {'job_id': job_id, 'store_id': store_id, 'status': 'unknown'}
    if record['status'] == 'running':
        with _lock(job_id) as acquired:
            # Re-read after locking: completion may have raced the first read.
            record = _read(store_id, job_id)
            if acquired and record['status'] == 'running':
                record = {**record, 'status': 'unknown'}
    return record


def _cancelled(store_id, job_id):
    try:
        with _path(job_id).with_suffix('.cancel').open('rb') as stream:
            raw = stream.read(4097)
    except FileNotFoundError:
        return False
    try:
        marker = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('Invalid cancellation intent') from exc
    if len(raw) > 4096 or marker != {'job_id': job_id, 'store_id': store_id}:
        raise ValueError('Invalid cancellation identity')
    return True


def cancel(store_id, job_id):
    _validate(store_id, job_id)
    # Separate short lock permits cancellation while the worker holds its run
    # lock, and serializes first identity assignment before a worker starts.
    with _lock(job_id, intent=True) as acquired:
        if not acquired:
            raise ValueError('Cancellation intent is busy')
        _read(store_id, job_id)
        if not _cancelled(store_id, job_id):
            _write(_path(job_id).with_suffix('.cancel'), {'job_id': job_id, 'store_id': store_id})
    return {'job_id': job_id, 'store_id': store_id, 'cancel_requested': True}


def status(store_id):
    store_artifacts.validate_id(store_id)
    state = automation_control.view(store_id)
    return {'paused': state['paused'], 'state': state['state']}


def collect():
    """Reuse the manual read-only collector and its private credential boundary."""
    import httpx
    from app.services import emag_business, emag_readonly
    from app.services.windows_credentials import read_emag_credentials
    user, password = read_emag_credentials()
    try:
        with httpx.Client(timeout=35, follow_redirects=False) as client:
            evidence = emag_business.collect(client, httpx.BasicAuth(user, password), 29,
                                             secrets=(user, password))
        return emag_readonly.redact(evidence, (user, password))
    finally:
        del user, password


def run(store_id, job_id, *, run_fn=None, collect_fn=None):
    _validate(store_id, job_id)
    if run_fn is None and collect_fn is None:
        bound_store = os.environ.get('IVYEA_OPS_SUPERVISOR_ACCOUNT_STORE_ID', '')
        store_artifacts.validate_id(bound_store)
        if bound_store != store_id:
            raise ValueError('Store does not match the configured read-only account')
    with _lock(job_id) as acquired:
        if not acquired:
            return receipt(store_id, job_id)
        with _lock(job_id, intent=True) as intent_acquired:
            if not intent_acquired:
                raise ValueError('Cancellation intent is busy')
            _cancelled(store_id, job_id)
            previous = _read(store_id, job_id)
            if previous is not None:
                return {**previous, 'status': 'unknown'} if previous['status'] == 'running' else previous
            record = {'job_id': job_id, 'store_id': store_id, 'status': 'running'}
            _write(_path(job_id), record)
        token = automation_control.current_cancel.set(lambda: _cancelled(store_id, job_id))
        try:
            result = (run_fn or emag_jobs.run)(store_id, collect_fn or collect)
            if (not isinstance(result, dict) or result.get('store_id') != store_id
                    or result.get('status') not in {'complete', 'paused', 'failed'}
                    or not _JOB.fullmatch(str(result.get('run_id', '')))):
                raise ValueError('Invalid worker receipt')
            record.update(status=result['status'], receipt_id=result['run_id'])
        except Exception:
            # A worker exception can occur after publication. Never infer failure
            # or retry; exception strings may contain secrets.
            record['status'] = 'unknown'
        finally:
            automation_control.current_cancel.reset(token)
        _write(_path(job_id), record)
        if record['status'] == 'complete':
            from app.services import browser_tasks
            browser_tasks.schedule(store_id)
        return record
