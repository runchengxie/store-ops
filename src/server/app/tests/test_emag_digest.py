"""Behavioral contracts for evidence-bound periodic reports."""
from datetime import datetime, timezone
import json

import pytest

from app.services import emag_digest as digest


NOW = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)


def snapshot():
    return {'store_id': 'test-ro', 'snapshot_id': 'snap-1', 'platform': 'emag', 'marketplace': 'RO',
            'source': 'https://marketplace-api.emag.ro/api-3/', 'captured_at': '2026-11-09T09:00:00Z',
            'limitations': [], 'coverage': ['order/read types 2 and 3', 'rma/read types 2 and 3'],
            'data': {'offers': [{'id': 1, 'general_stock': 3}, {'id': 2}],
                     'commercial_summary': {'window': {'start': '2026-10-10T00:00:00Z',
                                                       'end': '2026-11-09T08:00:00Z', 'timezone_note': 'verified UTC'}},
                     'commercial_evidence': {'orders_fbe': [{'id': 1, 'date': '2026-11-08T12:00:00Z'}],
                                             'orders_seller': [], 'returns_fbe': [], 'returns_seller': []}}}


@pytest.mark.parametrize(('kind', 'now', 'start', 'end'), [
    ('daily', '2026-10-26T10:00:00+00:00', '2026-10-25', '2026-10-26'),
    ('weekly', '2026-11-09T10:00:00+00:00', '2026-11-02', '2026-11-09'),
    ('weekly', '2026-11-08T10:00:00+00:00', '2026-10-26', '2026-11-02'),
])
def test_calendar_periods_do_not_use_fixed_utc_day_lengths(kind, now, start, end):
    p = digest.period(kind, datetime.fromisoformat(now), 'Europe/Bucharest')
    assert (p['start'], p['end']) == (start, end)


def test_counts_raw_records_once_and_preserves_missing_inventory():
    s = snapshot()
    s['data']['commercial_evidence']['orders_seller'] = [{'id': 1, 'date': '2026-11-08T12:00:00Z'}]
    r = digest.build(s, 'daily', NOW, locale='zh-CN')
    assert r['metrics']['orders']['current'] == 1
    assert r['metrics']['orders']['previous'] == 0
    assert r['metrics']['stock_known_total'] == 3
    assert r['metrics']['stock_unknown_rows'] == 1
    assert r['snapshot_id'] == 'snap-1'
    assert '暂未核实' not in r['markdown']
    assert len(json.dumps(r, ensure_ascii=False).encode()) < 32000


@pytest.mark.parametrize('date', ['2026-11-08 12:00:00', None, 'bad'])
def test_ambiguous_order_time_never_becomes_yesterday_sales(date):
    s = snapshot()
    s['data']['commercial_evidence']['orders_fbe'][0]['date'] = date
    r = digest.build(s, 'daily', NOW)
    assert r['metrics']['orders']['current'] is None
    assert r['metrics']['orders']['window_count'] == 1
    assert 'unavailable' in r['markdown'].lower()


def test_unverified_naive_collection_window_blocks_precise_period_counts():
    s = snapshot()
    s['data']['commercial_summary']['window'] = {'start': '2026-10-10 00:00:00',
        'end': '2026-11-09 08:00:00', 'timezone_note': 'UTC filters; platform timezone unverified'}
    r = digest.build(s, 'weekly', NOW, locale='zh-CN')
    assert r['metrics']['orders']['current'] is None
    assert '时区' in r['markdown']


def test_incomplete_window_does_not_claim_complete_week_or_comparison():
    s = snapshot()
    s['data']['commercial_summary']['window']['start'] = '2026-11-05T00:00:00Z'
    r = digest.build(s, 'weekly', NOW)
    assert r['metrics']['orders']['current'] is None
    assert r['metrics']['orders']['previous'] is None


def test_conflicting_duplicate_identity_does_not_produce_a_count():
    s = snapshot()
    s['data']['commercial_evidence']['orders_seller'] = [{'id': 1, 'date': '2026-11-07T12:00:00Z'}]
    assert digest.build(s, 'daily', NOW)['metrics']['orders']['window_count'] is None


def test_rendering_excludes_customer_source_text_and_detects_staleness():
    s = snapshot()
    s['captured_at'] = '2026-11-01T00:00:00Z'
    s['limitations'] = ['private-customer-text']
    s['data']['offers'][0]['name'] = 'private-customer-text'
    s['data']['commercial_evidence']['orders_fbe'][0]['customer'] = 'private-customer-text'
    r = digest.build(s, 'daily', NOW, locale='zh-CN')
    assert r['freshness'] == 'stale'
    assert '过期' in r['markdown']
    assert 'private-customer-text' not in json.dumps(r)


def test_missing_source_produces_an_unavailable_report_not_zero_sales():
    r = digest.build(None, 'daily', NOW, store_id='test-ro')
    assert r['freshness'] == 'missing'
    assert r['snapshot_id'] is None
    assert 'unavailable' in r['markdown'].lower()


def test_unknown_and_zero_stock_are_distinct():
    s = snapshot()
    s['data']['offers'] = [{'id': 1}, {'id': 2, 'general_stock': 0}]
    r = digest.build(s, 'daily', NOW)
    assert r['metrics']['stock_known_total'] == 0
    assert r['metrics']['stock_unknown_rows'] == 1
    assert r['metrics']['out_of_stock_rows'] == 1


def test_non_emag_snapshot_is_rejected():
    s = snapshot()
    s['platform'] = 'other'
    with pytest.raises(ValueError):
        digest.build(s, 'daily', NOW)
