"""Bounded, offline private evidence index. Imported text is untrusted data."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

from app.core.config import settings

MAX_IMPORT_BYTES = 32 * 1024 * 1024
MAX_SOURCES = 1000
MAX_CHUNKS = 20000
MAX_EXCERPT = 1200
MAX_SOURCE_CHUNKS = 100


def _path():
    return settings.data_dir / 'emag' / 'knowledge.sqlite3'


def _connect():
    descriptor = os.open(_path(), os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)
    db = sqlite3.connect(_path())
    db.row_factory = sqlite3.Row
    return db


def _safe(value, limit=MAX_EXCERPT):
    if not isinstance(value, str):
        raise ValueError('invalid_text')
    # Paths and bearer/share URLs are never useful citation locators.
    value = re.sub(r'https?://\S+|(?:[A-Za-z]:[\\/]|/)[^\s,;，；]+', '[private reference]', value)
    return value[:limit]


def _chunks(item):
    chunks = []
    if item.get('summary'):
        chunks.append(('summary', _safe(item['summary']), 0))
    points = item.get('key_points', [])
    if not isinstance(points, list):
        raise ValueError('invalid_key_points')
    for n, point in enumerate(points):
        if isinstance(point, str):
            text, locator = point, f'key_points[{n}]'
        elif isinstance(point, dict):
            text = point.get('text', '')
            start, end = point.get('start_seconds'), point.get('end_seconds')
            locator = f'key_points[{n}]'
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                locator += f' seconds:{start}-{end}'
            elif point.get('page') is not None:
                locator += ' page:' + _safe(str(point['page']), 40)
            elif point.get('pages') is not None:
                pages = point['pages']
                locator += ' pages:' + _safe(','.join(map(str, pages)) if isinstance(pages, list) else str(pages), 120)
            elif point.get('location') is not None:
                locator += ' location:' + _safe(str(point['location']), 160)
        else:
            raise ValueError('invalid_key_point')
        if text:
            chunks.append((locator, _safe(text), 1))
    text = item.get('search_text', '')
    if not isinstance(text, str):
        raise ValueError('invalid_search_text')
    # The generated pack has already filtered unusable ASR. Do not read originals.
    pending = []
    pending_size = 0
    start_line = 1

    def flush(end_line):
        if pending:
            excerpt = _safe('\n'.join(pending))
            if excerpt.strip():
                chunks.append((f'search_text lines:{start_line}-{end_line}', excerpt, 2))
            pending.clear()

    lines = text.splitlines()
    for line_no, line in enumerate(lines, 1):
        if len(line) > MAX_EXCERPT:
            flush(line_no - 1)
            pending_size = 0
            for offset in range(0, len(line), MAX_EXCERPT):
                piece = line[offset:offset + MAX_EXCERPT]
                excerpt = _safe(piece)
                if excerpt.strip():
                    chunks.append((f'search_text line:{line_no} chars:{offset + 1}-{offset + len(piece)}', excerpt, 2))
            continue
        addition = len(line) + (1 if pending else 0)
        if pending and pending_size + addition > MAX_EXCERPT:
            flush(line_no - 1)
            pending_size = 0
        if not pending:
            start_line = line_no
            addition = len(line)
        pending.append(line)
        pending_size += addition
    flush(len(lines))
    return chunks


def import_library(path):
    """Owner-only CLI operation; validate completely before transactional activation."""
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(MAX_IMPORT_BYTES + 1)
        if len(raw) > MAX_IMPORT_BYTES:
            raise ValueError('library_too_large')
        pack = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise ValueError('invalid_library_json') from exc
    if not isinstance(pack, dict) or not isinstance(pack.get('sources'), list):
        raise ValueError('invalid_sources')
    if not 1 <= len(pack['sources']) <= MAX_SOURCES:
        raise ValueError('invalid_source_count')
    revision = hashlib.sha256(raw).hexdigest()
    records, chunks, ids = [], [], set()
    guide = pack.get('guide', {})
    conflicts = guide.get('version_conflicts', []) if isinstance(guide, dict) else []
    if not isinstance(conflicts, list):
        raise ValueError('invalid_conflicts')
    for item in pack['sources']:
        if not isinstance(item, dict):
            raise ValueError('invalid_source')
        sid = item.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'[\w.-]{1,160}', sid) or sid in ids:
            raise ValueError('invalid_source_id')
        ids.add(sid)
        source_hash = item.get('sha256', '')
        if not isinstance(source_hash, str) or not re.fullmatch('[a-fA-F0-9]{64}', source_hash):
            raise ValueError('invalid_source_hash')
        related = []
        for conflict in conflicts:
            if not isinstance(conflict, dict) or not isinstance(conflict.get('refs', []), list):
                raise ValueError('invalid_conflict')
            if any(isinstance(ref, dict) and ref.get('id') == sid for ref in conflict.get('refs', [])):
                related.append({key: _safe(conflict[key], 600) for key in ('title', 'finding', 'action') if key in conflict})
        date = item.get('publication_date_from_content_or_null')
        if date is not None:
            date = _safe(date, 100)
        trust = 'historical_training_untrusted' + ('_asr_machine_transcription' if item.get('kind') == 'video' else '')
        records.append((revision, sid, _safe(item.get('title', sid), 300), source_hash, trust, date, json.dumps(related[:20])))
        for n, (locator, excerpt, rank) in enumerate(_chunks(item)):
            chunks.append((revision, sid, f'{sid}:{n}', locator, excerpt, rank))
            if len(chunks) > MAX_CHUNKS:
                raise ValueError('too_many_chunks')
    _path().parent.mkdir(parents=True, exist_ok=True)
    with _connect() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS active (singleton INTEGER PRIMARY KEY CHECK(singleton=1), revision TEXT);
            CREATE TABLE IF NOT EXISTS sources (revision TEXT, source_id TEXT, title TEXT, source_hash TEXT,
                trust TEXT, date TEXT, conflicts TEXT, PRIMARY KEY(revision, source_id));
            CREATE TABLE IF NOT EXISTS chunks (revision TEXT, source_id TEXT, chunk_id TEXT, locator TEXT,
                excerpt TEXT, rank INTEGER, PRIMARY KEY(revision, chunk_id));
        ''')
        db.executemany('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?,?,?)', records)
        db.executemany('INSERT OR IGNORE INTO chunks VALUES (?,?,?,?,?,?)', chunks)
        db.execute('INSERT OR REPLACE INTO active VALUES (1,?)', (revision,))
    return status()


def status():
    if not _path().exists():
        return {'available': False, 'revision': None, 'source_count': 0, 'chunk_count': 0}
    with _connect() as db:
        row = db.execute('SELECT revision FROM active WHERE singleton=1').fetchone()
        revision = row[0] if row else None
        return {'available': revision is not None, 'revision': revision,
                'source_count': db.execute('SELECT count(*) FROM sources WHERE revision=?', (revision,)).fetchone()[0],
                'chunk_count': db.execute('SELECT count(*) FROM chunks WHERE revision=?', (revision,)).fetchone()[0]}


def search(query, limit=5):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 500 or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('invalid_query_or_limit')
    state = status()
    result = {'available': state['available'], 'revision': state['revision'], 'results': [], 'marketplace_writes': False}
    if not state['available']:
        return result
    # instr is literal, unlike LIKE; Unicode lower handles both CJK and English.
    with _connect() as db:
        rows = db.execute('''SELECT s.*, c.chunk_id, c.locator, c.excerpt FROM chunks c
            JOIN sources s USING(revision, source_id) WHERE c.revision=?
            AND (instr(lower(c.excerpt), lower(?))>0 OR instr(lower(s.title), lower(?))>0)
            ORDER BY c.rank, c.source_id, c.rowid LIMIT ?''', (state['revision'], query.strip(), query.strip(), limit)).fetchall()
        result['results'] = [{**dict(row), 'conflicts': json.loads(row['conflicts'])} for row in rows]
    return result


def source(source_id, revision=None):
    revision = revision or status()['revision']
    if not _path().exists():
        raise FileNotFoundError('source_not_found')
    with _connect() as db:
        row = db.execute('SELECT * FROM sources WHERE revision=? AND source_id=?', (revision, source_id)).fetchone()
        if row is None:
            raise FileNotFoundError('source_revision_not_found')
        chunks = db.execute('SELECT chunk_id,locator,excerpt FROM chunks WHERE revision=? AND source_id=? ORDER BY rank,rowid LIMIT ?',
                            (revision, source_id, MAX_SOURCE_CHUNKS + 1)).fetchall()
        return {**dict(row), 'conflicts': json.loads(row['conflicts']),
                'chunks': [dict(chunk) for chunk in chunks[:MAX_SOURCE_CHUNKS]], 'truncated': len(chunks) > MAX_SOURCE_CHUNKS}
