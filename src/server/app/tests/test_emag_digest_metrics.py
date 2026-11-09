"""Product units and inventory risks from bounded saved evidence."""
import json

import pytest

from app.services import emag_digest_metrics as metrics


def order(status=4, quantity=2, product_id=1, line_status=1):
    return {'status': status, 'products': [{'product_id': product_id, 'status': line_status, 'quantity': quantity}]}


def test_units_exclude_canceled_returned_pending_and_inactive_lines():
    current = [order(), order(0, 99), order(5, 99), order(1, 99), order(line_status=0, quantity=99)]
    r = metrics.products(current, [order(quantity=1)], [{'id': 1, 'part_number': 'SKU-1'}])
    assert (r['current']['units'], r['previous']['units'], r['change']) == (2, 1, 1)
    assert r['current']['top'] == [{'product_id': '1', 'label': 'SKU-1', 'units': 2}]


@pytest.mark.parametrize('quantity', [None, True, -1, 1.5, 'bad'])
def test_invalid_active_quantity_keeps_complete_total_unknown(quantity):
    r = metrics.products([order(), order(quantity=quantity, product_id=2)], [], [])
    assert r['current']['units'] is None
    assert r['current']['known_units'] == 2
    assert r['current']['top'] is None
    assert r['change'] is None


@pytest.mark.parametrize('row', [{}, {'status': 4}, {'status': 4, 'products': []},
                               {'status': 4, 'products': [None]}, order(line_status=None), order(status=None)])
def test_missing_status_or_finalized_lines_never_produce_a_complete_zero(row):
    r = metrics.products([row], [], [])
    assert r['current']['units'] is None


def test_complete_empty_period_is_zero_but_missing_period_is_unknown():
    r = metrics.products([], None, [])
    assert r['current']['units'] == 0 and r['current']['top'] == []
    assert r['previous']['units'] is None and r['change'] is None


def test_missing_product_identity_does_not_fabricate_a_complete_ranking():
    r = metrics.products([order(product_id=None)], [], [])
    assert r['current']['units'] == 2
    assert r['current']['top'] is None


def test_ties_are_explicit_and_order_is_deterministic():
    rows = [order(quantity=1, product_id=i) for i in [5, 3, 1, 4, 2]]
    r = metrics.products(rows, [], [])['current']
    assert r['units'] == 5 and len(r['top']) == 3
    assert [p['product_id'] for p in r['top']] == ['1', '2', '3']
    assert r['cutoff_tied_products'] == 5
    assert r == metrics.products(list(reversed(rows)), [], [])['current']


def test_catalog_labels_cannot_inject_images_links_or_mentions():
    offers = [{'id': 1, 'part_number': '![image](https://bad.example/a) <at id="all"> @all\nSKU'}]
    label = metrics.products([order()], [], offers)['current']['top'][0]['label']
    assert not any(x in label for x in ['https://', '![', '<at', '@', '\n'])
    assert len(label) <= 48


def test_empty_sanitized_sku_uses_a_bounded_valid_identifier_fallback():
    identity = 'a' * 80
    r = metrics.products([order(product_id=identity)], [], [{'id': identity, 'part_number': '!!!'}])
    label = r['current']['top'][0]['label']
    assert label.startswith('ID ') and len(label) <= 48


def bands(old=0, new=0):
    return {'0-30': new, '31-60': 0, '61-90': 0, '91-180': 0, '181-270': 0, '271-365': 0, '365+': old}


def test_inventory_risks_only_use_positive_stock_and_reconciled_aging():
    snapshot = {'store_id': 'test-ro', 'snapshot_id': 'snap-1', 'platform': 'emag', 'marketplace': 'RO',
        'source': 'synthetic', 'coverage': ['offers'], 'limitations': [], 'captured_at': '2026-11-09T00:00:00Z',
        'data': {'offers': [
            {'id': 1, 'part_number': 'blocked', 'general_stock': 4, 'offer_validation_status': {'value': 2}, 'stock_2p_aging_bands': bands(4)},
            {'id': 2, 'general_stock': 3, 'stock_2p_aging_bands': bands(9)},
            {'id': 3, 'general_stock': 0, 'offer_validation_status': {'value': 2}, 'stock_2p_aging_bands': bands()}]}}
    r = metrics.inventory(snapshot)
    assert (r['blocked_products'], r['blocked_units']) == (1, 4)
    assert r['aged_181_plus_units'] == 4
    assert r['aging_unverified_products'] == 1
    assert r['aging_is_partial'] is True
    assert r['priorities'][0] == {'product_id': '1', 'label': 'blocked', 'stock': 4}
    assert 'Stock decrease' not in json.dumps(r)


def test_unknown_inventory_keeps_stocked_issue_total_explicitly_partial():
    snapshot = {'store_id': 'test-ro', 'snapshot_id': 'snap-1', 'platform': 'emag', 'marketplace': 'RO',
        'source': 'synthetic', 'coverage': ['offers'], 'limitations': [], 'captured_at': '2026-11-09T00:00:00Z',
        'data': {'offers': [{'id': 1, 'offer_validation_status': {'value': 2}}]}}
    r = metrics.inventory(snapshot)
    assert r['stock_unknown_products'] == 1
    assert r['blocked_products'] == 0
    assert '已知部分' in '\n'.join(metrics.render_inventory(r, 'zh-CN'))
