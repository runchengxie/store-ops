"""Durable per-store automatic monitoring intent and cooperative checkpoints."""
from contextvars import ContextVar
from datetime import datetime, timezone
import sqlite3
from app.services import store_artifacts

current_store: ContextVar[str | None] = ContextVar('automation_store', default=None)
current_cancel: ContextVar = ContextVar('automation_job_cancel', default=None)


class Paused(RuntimeError):
    """A monitored worker reached a safe stopping boundary."""


def _connect(store_id):
    root = store_artifacts._root() / 'automation'
    root.mkdir(parents=True, exist_ok=True)
    path = root / (store_artifacts.validate_id(store_id) + '.sqlite3')
    conn = sqlite3.connect(path, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK(id=1), paused INTEGER NOT NULL, revision INTEGER NOT NULL, actor TEXT NOT NULL, updated_at TEXT NOT NULL)')
    conn.execute("INSERT OR IGNORE INTO control VALUES(1,0,0,'','')")
    conn.commit()
    return conn


def _busy(store_id):
    path = store_artifacts._root() / 'jobs' / store_artifacts.validate_id(store_id) / 'run-lock.sqlite3'
    if not path.exists():
        return False
    conn = sqlite3.connect(path, timeout=0)
    try:
        try:
            conn.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as exc:
            if getattr(exc, 'sqlite_errorcode', None) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                return True
            raise
        conn.rollback()
        return False
    finally:
        conn.close()


def view(store_id):
    conn = _connect(store_id)
    try:
        paused, revision, actor, updated_at = conn.execute('SELECT paused,revision,actor,updated_at FROM control WHERE id=1').fetchone()
        busy = _busy(store_id)
        return {'paused':bool(paused), 'revision':revision, 'state':('pausing' if busy else 'paused') if paused else 'enabled',
                'actor':actor, 'updated_at':updated_at, 'scope':'automatic_monitoring'}
    finally:
        conn.close()


def set_paused(store_id, paused, revision, actor):
    if type(paused) is not bool or type(revision) is not int or revision < 0:
        raise ValueError('Invalid monitoring control')
    conn = _connect(store_id)
    try:
        changed = conn.execute('UPDATE control SET paused=?, revision=revision+1, actor=?, updated_at=? WHERE id=1 AND revision=?',
                               (int(paused), str(actor), datetime.now(timezone.utc).isoformat(), revision)).rowcount
        if changed != 1:
            raise ValueError('Monitoring control changed; reload before retrying')
        conn.commit()
    finally:
        conn.close()
    return view(store_id)


def checkpoint():
    cancel = current_cancel.get()
    if cancel is not None and cancel():
        raise Paused('Automatic monitoring job cancelled')
    store_id = current_store.get()
    if store_id is not None and view(store_id)['paused']:
        raise Paused('Automatic monitoring paused')
