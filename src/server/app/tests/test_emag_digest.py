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
                                                       'end': '2026-11-09T08:00:00Z', 'timezone_note': 'verified UTC',
                                                       'timezone_verified': True}},
                     'commercial_evidence': {'orders_fbe': [{'id': 1, 'date': '2026-11-08T12:00:00Z'}],
                                             'orders_seller': [], 'returns_fbe': [], 'returns_seller': []}}}


def calendar_snapshot():
    s = snapshot()
    s['data']['commercial_summary']['window'] = {
        'start': '2026-10-11 01:00:02', 'end': '2026-11-09 01:00:02',
        'timezone_note': 'UTC values sent as naive API filter strings; platform timezone unverified'}
    s['data']['commercial_evidence']['orders_fbe'] = [
        {'id': 1, 'date': '2026-11-08 12:00:00', 'status': 4},
        {'id': 2, 'date': '2026-11-07 23:59:59', 'status': 0},
        {'id': 3, 'date': '2026-11-04 00:00:00', 'status': 1},
        {'id': 4, 'date': '2026-10-29 12:00:00', 'status': 5},
        {'id': 5, 'date': '2026-11-09 00:00:00', 'status': 1}]
    return s


def test_api_calendar_dates_produce_daily_counts_without_claiming_verified_instants():
    r = digest.build(calendar_snapshot(), 'daily', NOW, locale='zh-CN')
    assert r['metrics']['orders']['current'] == 1
    assert r['metrics']['orders']['previous'] == 1
    assert r['metrics']['orders']['basis'] == 'platform_calendar'
    assert r['date_basis'] == 'platform_calendar'
    assert 'eMAG 平台日期' in r['markdown']
    assert '订单状态' in r['markdown']
    assert '时区尚未核实' in r['details_markdown']


def test_weekly_calendar_counts_and_status_codes_use_creation_period():
    s = calendar_snapshot()
    s['data']['commercial_evidence']['returns_fbe'] = [
        {'emag_id': 7, 'date': '2026-11-03 10:00:00', 'request_status': 7},
        {'emag_id': 8, 'date': '2026-10-30 10:00:00', 'request_status': 3}]
    r = digest.build(s, 'weekly', NOW)
    orders, returns = r['metrics']['orders'], r['metrics']['returns']
    assert (orders['current'], orders['previous'], orders['change']) == (3, 1, 2)
    assert orders['current_statuses'] == {'4': 1, '0': 1, '1': 1}
    assert (returns['current'], returns['previous']) == (1, 1)
    assert returns['current_statuses'] == {'7': 1}
    assert 'platform calendar' in r['markdown']


@pytest.mark.parametrize('mutation', ['wrong_source', 'missing_coverage', 'mixed_date', 'missing_date', 'outside_window'])
def test_calendar_counts_require_a_compatible_complete_source_contract(mutation):
    s = calendar_snapshot()
    if mutation == 'wrong_source':
        s['source'] = 'synthetic-import'
    elif mutation == 'missing_coverage':
        s['coverage'] = ['offers only']
    elif mutation == 'mixed_date':
        s['data']['commercial_evidence']['orders_fbe'][0]['date'] = '2026-11-08T12:00:00Z'
    elif mutation == 'missing_date':
        s['data']['commercial_evidence']['orders_fbe'][0].pop('date')
    elif mutation == 'outside_window':
        s['data']['commercial_evidence']['orders_fbe'][0]['date'] = '2026-10-01 12:00:00'
    r = digest.build(s, 'weekly', NOW)
    assert r['metrics']['orders']['current'] is None


def test_calendar_window_coverage_distinguishes_zero_from_unknown():
    s = calendar_snapshot()
    s['data']['commercial_evidence']['orders_fbe'] = []
    s['data']['commercial_summary']['window']['start'] = '2026-11-07 01:00:00'
    r = digest.build(s, 'daily', NOW)
    assert r['metrics']['orders']['current'] == 0
    assert r['metrics']['orders']['previous'] is None


def test_calendar_dates_on_fall_dst_day_are_counted_without_offset_assignment():
    s = calendar_snapshot()
    s['captured_at'] = '2026-10-26T09:00:00Z'
    s['data']['commercial_summary']['window']['end'] = '2026-10-26 01:00:00'
    s['data']['commercial_evidence']['orders_fbe'] = [
        {'id': 1, 'date': '2026-10-25 03:30:00', 'status': 4}]
    r = digest.build(s, 'daily', datetime(2026, 10, 26, 10, tzinfo=timezone.utc))
    assert r['metrics']['orders']['current'] == 1
    assert r['metrics']['orders']['basis'] == 'platform_calendar'


def test_malformed_status_text_is_not_copied_into_the_delivered_json():
    s = calendar_snapshot()
    s['data']['commercial_evidence']['orders_fbe'][0]['status'] = 'private-customer-text'
    r = digest.build(s, 'daily', NOW)
    assert r['metrics']['orders']['current_statuses'] == {'unknown': 1}
    assert 'private-customer-text' not in json.dumps(r)


@pytest.mark.parametrize('locale', ['en', 'zh-CN'])
def test_client_message_keeps_period_results_while_local_details_retain_provenance(locale):
    r = digest.build(calendar_snapshot(), 'weekly', NOW, locale=locale)
    assert r['metrics']['orders']['current'] == 3
    assert r['metrics']['orders']['window_count'] == 5
    assert '2026-11-08' in r['markdown']
    assert 'snap-1' not in r['markdown']
    for text in ('完整采集窗口', '未计算销售额', '库存变化不等于销量',
                 'Full captured window', 'Revenue, net profit', 'inventory changes are not sales'):
        assert text not in r['markdown']
    assert r['markdown'] in r['details_markdown']
    assert 'snap-1' in r['details_markdown']
    assert r['evidence']['window_counts'] == {'orders': 5, 'returns': 0}
    assert r['evidence']['date_basis'] == 'platform_calendar'


def test_missing_stock_and_stale_evidence_still_warn_in_the_client_message():
    s = calendar_snapshot()
    s['captured_at'] = '2026-11-01T00:00:00Z'
    r = digest.build(s, 'weekly', NOW, locale='zh-CN')
    assert '过期' in r['markdown']
    assert '库存未知 1' in r['markdown']


def test_invalid_window_evidence_remains_language_neutral():
    s = calendar_snapshot()
    s['data']['commercial_summary']['window']['start'] = 'not-a-date'
    s['data']['commercial_summary']['window']['end'] = None
    evidence = [digest.build(s, 'weekly', NOW, locale=locale)['evidence'] for locale in ('en', 'zh-CN')]
    assert evidence[0] == evidence[1]
    assert evidence[0]['window_start'] is None and evidence[0]['window_end'] is None


def test_saved_report_includes_details_while_delivery_markdown_stays_compact(monkeypatch, capsys):
    from app import emag_digest_cli
    from app.services import store_artifacts
    saved = {}
    source = snapshot()
    source['captured_at'] = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(store_artifacts, 'read_snapshot', lambda *args: source)
    def save(*args):
        saved['markdown'] = args[3]
        return {'report_id': 'report-1'}
    monkeypatch.setattr(store_artifacts, 'save_report', save)
    assert emag_digest_cli.main(['--store-id', 'test-ro', '--kind', 'daily', '--save']) == 0
    output = json.loads(capsys.readouterr().out)
    assert saved['markdown'] == output['details_markdown']
    assert output['markdown'] in saved['markdown']
    assert 'snap-1' not in output['markdown'] and 'snap-1' in saved['markdown']


def test_report_integrates_period_units_without_changing_order_record_counts():
    s = calendar_snapshot()
    rows = s['data']['commercial_evidence']['orders_fbe']
    rows[0]['products'] = [{'product_id': 1, 'status': 1, 'quantity': 2}]
    rows[3].update(status=4, products=[{'product_id': 1, 'status': 1, 'quantity': 1}])
    r = digest.build(s, 'weekly', NOW, locale='zh-CN')
    assert r['metrics']['orders']['current'] == 3
    assert r['metrics']['products']['current']['units'] == 2
    assert r['metrics']['products']['previous']['units'] == 1
    assert '已完成订单商品' in r['markdown'] and '2 件' in r['markdown']
    assert '库存关注' in r['markdown']


def test_period_source_failure_does_not_expose_unguarded_product_totals():
    s = calendar_snapshot()
    s['source'] = 'unsupported-import'
    s['data']['commercial_evidence']['orders_fbe'][0]['products'] = [{'product_id': 1, 'status': 1, 'quantity': 999}]
    r = digest.build(s, 'weekly', NOW)
    assert r['metrics']['products']['current']['units'] is None
    assert '999' not in r['markdown']


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


@pytest.mark.parametrize('note', [None, 'unknown', 'not verified', 'UTC'])
def test_absence_of_negative_note_is_not_positive_window_verification(note):
    s = snapshot()
    window = s['data']['commercial_summary']['window']
    window.pop('timezone_verified')
    window['timezone_note'] = note
    r = digest.build(s, 'daily', NOW)
    assert r['metrics']['orders']['current'] is None
    assert r['metrics']['orders']['previous'] is None


@pytest.mark.parametrize('verified', [False, 'true', 1])
def test_verification_marker_requires_explicit_boolean_true(verified):
    s = snapshot()
    s['data']['commercial_summary']['window']['timezone_verified'] = verified
    assert digest.build(s, 'daily', NOW)['metrics']['orders']['current'] is None


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
