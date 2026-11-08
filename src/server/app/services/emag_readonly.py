"""Read-only RO offers and source-labelled evidence; no marketplace write API."""
from datetime import datetime, timezone
import math
import re
import time
from app.services.automation_control import checkpoint

import httpx

ENDPOINT = 'https://marketplace-api.emag.ro/api-3/product_offer/read'


def collect(client, auth, *, page_size=100, delay=1, max_pages=100):
    if not 1 <= page_size <= 100 or not 1 <= max_pages <= 100 or delay < 0:
        raise ValueError('Invalid pagination limits')
    result = {'offers': [], 'pages': 0, 'complete': False, 'reason': 'page_limit'}
    seen = set()
    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(delay)
        try:
            checkpoint()
            response = client.post(ENDPOINT, json={'currentPage': page, 'itemsPerPage': page_size},
                                   auth=auth, follow_redirects=False)
            if not response.is_success:
                result['reason'] = f'http_{response.status_code}'
                break
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            result['reason'] = type(exc).__name__
            break
        if not isinstance(body, dict) or body.get('isError') is not False:
            result['reason'] = 'api_error'
            break
        rows = body.get('results')
        if not isinstance(rows, list) or len(rows) > page_size or any(not isinstance(r, dict) for r in rows):
            result['reason'] = 'invalid_results'
            break
        ids = [str(r['id']) for r in rows if type(r.get('id')) in (int, str) and str(r['id']).strip()]
        if len(ids) != len(rows) or len(set(ids)) != len(ids) or seen.intersection(ids):
            result['reason'] = 'missing_or_duplicate_ids'
            break
        seen.update(ids)
        result['offers'].extend(rows)
        result['pages'] += 1
        if len(rows) < page_size:
            result.update(complete=True, reason='end_of_pagination')
            break
    return result



def lookup_sku(client, auth, sku):
    """Read one SKU without creating a store snapshot or assuming availability."""
    if not isinstance(sku, str) or not sku.strip() or len(sku) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in sku):
        raise ValueError('Invalid SKU')
    def incomplete(reason):
        return {'status': 'incomplete', 'reason': reason, 'offer': None}
    try:
        checkpoint()
        response = client.post(ENDPOINT, json={'part_number': sku, 'currentPage': 1, 'itemsPerPage': 100},
                               auth=auth, follow_redirects=False)
        if not response.is_success:
            return incomplete(f'http_{response.status_code}')
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return incomplete(type(exc).__name__)
    if not isinstance(body, dict) or body.get('isError') is not False or not isinstance(body.get('results'), list):
        return incomplete('api_or_shape_error')
    rows = body['results']
    if not rows:
        return {'status': 'not_found', 'reason': 'no_results', 'offer': None}
    if (len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get('part_number') != sku
            or type(rows[0].get('id')) not in (int, str) or not str(rows[0]['id']).strip()):
        return incomplete('ambiguous_or_mismatched_results')
    row = dict(rows[0])
    status_keys = ('validation_status', 'translation_validation_status', 'offer_validation_status')
    truncated = any(isinstance(row.get(k), list) and len(row[k]) > 8 for k in status_keys)
    for key in status_keys:
        if isinstance(row.get(key), list):
            row[key] = row[key][:8]
    offer, more_truncated = _bounded_sku_offer(project_offer(row))
    return {'status': 'found', 'reason': 'exact_match', 'offer': offer,
            'evidence_truncated': truncated or more_truncated}



def _bounded_sku_offer(offer):
    """Omit malformed nested fields and limit data returned by a single lookup."""
    truncated = False
    def scalar(value):
        nonlocal truncated
        if isinstance(value, str):
            if len(value) > 256:
                truncated = True
            value = re.sub(r'https?://\S+', '[URL omitted]', value, flags=re.IGNORECASE)
            value = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '[email omitted]', value)
            return value[:256]
        if value is None or type(value) in (int, bool):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        return None
    def fields(item, keys):
        return {k: scalar(item[k]) for k in keys if k in item and
                (item[k] is None or scalar(item[k]) is not None)}
    status_keys = ('validation_status', 'translation_validation_status', 'offer_validation_status')
    result = fields(offer, [k for k in offer if k not in status_keys])
    for key in status_keys:
        if key not in offer:
            continue
        original = offer[key]
        statuses = original if isinstance(original, list) else [original]
        clean = []
        for status in statuses[:8]:
            if not isinstance(status, dict):
                continue
            item = fields(status, ('value', 'description', 'errors', 'error_details_truncated'))
            details = status.get('error_details')
            if status.get('error_details_truncated') is True:
                truncated = True
            if isinstance(details, list):
                item['error_details'] = [fields(d, ('code', 'section', 'message', 'extra_info'))
                                         for d in details[:8] if isinstance(d, dict)]
            clean.append(item)
        result[key] = clean if isinstance(original, list) else (clean[0] if clean else {})
    return result, truncated


def redact_values(value, secrets):
    """Redact string values while preserving stable machine field names."""
    if isinstance(value, dict):
        return {key: redact_values(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_values(item, secrets) for item in value]
    return redact(value, secrets)


def redact(value, secrets):
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, '[REDACTED]')
        return value
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, dict):
        return {redact(k, secrets): redact(v, secrets) for k, v in value.items()}
    return value


def _validation_details(errors):
    """Keep bounded platform messages, never the submitted document or URLs."""
    entries = errors.get('errors') if isinstance(errors, dict) else None
    if not isinstance(entries, list):
        return None, False
    details = []
    truncated = len(entries) > 64
    seen = set()
    for entry in entries[:64]:
        if not isinstance(entry, dict):
            truncated = True
            continue
        detail = {}
        for key in ('code', 'section'):
            value = entry.get(key)
            if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', value):
                detail[key] = value
        messages = entry.get('message')
        for key, value in (('message', messages.get('en_GB') if isinstance(messages, dict) else None),
                           ('extra_info', entry.get('extra_info'))):
            if not isinstance(value, str):
                continue
            value = re.sub(r'https?://\S+', '[URL omitted]', value, flags=re.IGNORECASE)
            value = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '[email omitted]', value)
            value = ' '.join(value.split())
            if len(value) > 256:
                truncated = True
                value = value[:256]
            if value:
                detail[key] = value
        if detail:
            identity = tuple(sorted(detail.items()))
            if identity in seen:
                truncated = True
                continue
            if len(details) == 8:
                truncated = True
                break
            seen.add(identity)
            details.append(detail)
    return details, truncated


def project_offer(row):
    fields = ('id', 'part_number', 'part_number_key', 'name', 'status', 'sale_price',
              'currency', 'vat_id', 'general_stock', 'estimated_stock', 'fulfillment_type',
              'auto_translated', 'category_id', 'brand', 'campaign_id', 'campaign_name')
    result = {key: row[key] for key in fields if key in row}
    # Validation errors may embed entire submitted product documents. Keep compact
    # status evidence, not those documents or potentially signed attachment URLs.
    for key in ('validation_status', 'translation_validation_status', 'offer_validation_status'):
        if key not in row:
            continue
        original = row[key]
        values = original if isinstance(original, list) else [original]
        compact = []
        for status in values:
            if not isinstance(status, dict):
                compact.append({})
                continue
            item = {k: status[k] for k in ('value', 'description') if k in status}
            errors = status.get('errors')
            if isinstance(errors, str):
                item['errors'] = errors[:2000]
            elif errors:
                item['errors'] = 'Structured validation details omitted; inspect seller portal.'
                details, truncated = _validation_details(errors)
                if details is not None:
                    item['error_details'] = details
                    if truncated:
                        item['error_details_truncated'] = True
            compact.append(item)
        result[key] = compact if isinstance(original, list) else (compact[0] if compact else {})
    return result


def _values(row, key):
    value = row.get(key)
    values = value if isinstance(value, list) else [value]
    return [v.get('value') if isinstance(v, dict) else None for v in values]


def summarize(rows):
    summary = dict.fromkeys(('offers', 'stock_positive', 'stock_zero', 'stock_unknown',
                            'documentation_status_unknown', 'price_status_unknown',
                            'invalid_price', 'invalid_price_with_stock', 'documentation_rejected', 'blocked'), 0)
    issues = []
    for row in rows:
        summary['offers'] += 1
        stock = row.get('general_stock')
        known = (type(stock) is int or (type(stock) is float and math.isfinite(stock))) and stock >= 0
        summary['stock_unknown' if not known else ('stock_positive' if stock > 0 else 'stock_zero')] += 1
        reasons = []
        for field, counter, allowed in (
                ('validation_status', 'documentation_status_unknown', {1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12}),
                ('offer_validation_status', 'price_status_unknown', {1, 2})):
            values = _values(row, field)
            if not values or any(type(v) is not int or v not in allowed for v in values):
                summary[counter] += 1
        if 2 in _values(row, 'offer_validation_status'):
            summary['invalid_price'] += 1
            summary['invalid_price_with_stock'] += int(known and stock > 0)
            reasons.append('invalid_price')
        for value, reason in ((8, 'documentation_rejected'), (10, 'blocked')):
            if value in _values(row, 'validation_status'):
                summary[reason] += 1
                reasons.append(reason)
        if reasons:
            issues.append({'id': row.get('id'), 'part_number': row.get('part_number'),
                           'part_number_key': row.get('part_number_key'), 'reasons': reasons,
                           'general_stock': stock if known else None})
    return {**summary, 'issues': issues}


def publish(store_id, result):
    from app.services import store_artifacts
    if not result['complete']:
        raise ValueError('Incomplete collections cannot be imported')
    rows = [project_offer(row) for row in result['offers']]
    summary = summarize(rows)
    snapshot = store_artifacts.import_snapshot({
        'store_id': store_id, 'platform': 'emag', 'marketplace': 'RO',
        'captured_at': datetime.now(timezone.utc).isoformat(), 'source': ENDPOINT,
        'coverage': ['product_offer/read: complete pagination'],
        'limitations': ['Sequential pages are not an atomic snapshot.',
                       'Store label is caller-supplied; account identity is not independently verified.',
                       'No orders, revenue, returns or separate FBE inventory reconciliation.',
                       'Missing stock is unknown; status=1 does not prove storefront availability.',
                       'Selected fields only; nested validation documents are omitted.'],
        'data': {'pages': result['pages'], 'offers': rows, 'summary': summary}})
    markdown = '\n'.join(['# eMAG RO offer audit', '',
        f"Snapshot: {snapshot['snapshot_id']}", f"Captured: {snapshot['captured_at']}", '',
        *[f'- {key}: {value}' for key, value in summary.items() if key != 'issues'], '',
        'Issue IDs, SKU references and compact platform errors are in the attached snapshot.',
        'Issue totals count observed flags only; unknown validation statuses are not confirmed healthy.',
        'Issue groups may overlap. Verify stock scope, VAT and platform price criteria before changing offers.',
        'This report does not establish storefront availability, revenue or losses. No store writes performed.'])
    report = store_artifacts.save_report(store_id, snapshot['snapshot_id'], 'eMAG RO offer audit', markdown)
    return {'complete': True, 'offers': len(rows), 'snapshot_id': snapshot['snapshot_id'],
            'report_id': report['report_id']}
