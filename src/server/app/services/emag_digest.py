"""Bounded, deterministic period reports from saved eMAG evidence; no network."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def _aware(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo is not None and result.utcoffset() is not None else None
    except ValueError:
        return None


def period(kind, now, timezone_name='Europe/Bucharest'):
    if kind not in ('daily', 'weekly') or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('An aware clock and daily/weekly kind are required')
    today = now.astimezone(ZoneInfo(timezone_name)).date()
    end = today if kind == 'daily' else today - timedelta(days=today.weekday())
    start = end - timedelta(days=1 if kind == 'daily' else 7)
    return {'start': start.isoformat(), 'end': end.isoformat()}


def _records(evidence, prefix):
    rows = {}
    for key in (prefix + '_fbe', prefix + '_seller'):
        if not isinstance(evidence.get(key), list):
            return None
        for row in evidence[key]:
            if not isinstance(row, dict):
                return None
            identity = row.get('id', row.get('emag_id'))
            if type(identity) not in (str, int) or not str(identity).strip():
                return None
            identity = str(identity)
            if identity in rows and rows[identity] != row:
                return None
            rows[identity] = row
    return list(rows.values())


def _counts(evidence, prefix, window, start, end):
    rows = _records(evidence, prefix)
    result = {'current': None, 'previous': None, 'window_count': None if rows is None else len(rows)}
    if rows is None:
        return result
    window_start, window_end = _aware(window.get('start')), _aware(window.get('end'))
    dates = [_aware(row.get('date')) for row in rows]
    if (not window_start or not window_end or 'unverified' in str(window.get('timezone_note', '')).lower()
            or any(d is None for d in dates)):
        return result
    previous = start - (end - start)  # Calendar-aware local midnight arithmetic.
    for name, lower, upper in (('current', start, end), ('previous', previous, start)):
        if window_start <= lower and window_end >= upper:
            result[name] = sum(lower <= d < upper for d in dates)
    return result


def build(snapshot, kind, now, timezone_name='Europe/Bucharest', locale='en', *, store_id=None):
    if locale not in ('en', 'zh-CN'):
        raise ValueError('Unsupported report locale')
    from app.services.store_artifacts import validate_id
    store_id = validate_id(snapshot['store_id'] if snapshot else store_id)
    p = period(kind, now, timezone_name)
    zh = locale == 'zh-CN'
    title = ('经营日报' if kind == 'daily' else '经营周报') if zh else ('Daily store report' if kind == 'daily' else 'Weekly store report')
    lines = [f'# {title} · {store_id}', '',
             (f"统计区间：{p['start']} 至 {p['end']}（结束日不含，{timezone_name}）" if zh else
              f"Period: {p['start']} to {p['end']} (end exclusive, {timezone_name})")]
    result = {'schema_version': 1, 'store_id': store_id, 'kind': kind, 'period': p,
              'timezone': timezone_name, 'locale': locale, 'generated_at': now.isoformat(),
              'snapshot_id': None, 'captured_at': None, 'freshness': 'missing', 'metrics': {}}
    if snapshot is None:
        lines += ['', '暂无已保存的数据，经营指标不可用。请检查采集服务。' if zh else
                  'Saved evidence unavailable. Check the collector; business figures are unknown.']
    else:
        if snapshot.get('platform') != 'emag' or snapshot.get('marketplace') != 'RO':
            raise ValueError('An eMAG RO snapshot is required')
        validate_id(snapshot['snapshot_id'])
        captured = _aware(snapshot.get('captured_at'))
        if captured is None or captured > now + timedelta(minutes=5):
            raise ValueError('Invalid snapshot capture time')
        fresh = 'stale' if now - captured > timedelta(hours=24) else 'fresh'
        result.update(snapshot_id=snapshot['snapshot_id'], captured_at=captured.isoformat(), freshness=fresh)
        captured_display = captured.astimezone(ZoneInfo(timezone_name)).isoformat(timespec='seconds')
        lines += ['', ('数据已过期，以下仅为历史观测。' if zh else 'STALE evidence: historical observations only.')
                  if fresh == 'stale' else ('数据采集于最近 24 小时内。' if zh else 'Evidence captured within the last 24 hours.'),
                  f"{'采集时间' if zh else 'Captured'}: {captured_display}"]
        data = snapshot['data']
        window = data.get('commercial_summary', {}).get('window', {})
        evidence = data.get('commercial_evidence', {})
        zone = ZoneInfo(timezone_name)
        start, end = (datetime.combine(datetime.fromisoformat(p[k]).date(), time(), zone) for k in ('start', 'end'))
        orders = _counts(evidence, 'orders', window, start, end)
        returns = _counts(evidence, 'returns', window, start, end)
        offers = data.get('offers')
        if not isinstance(offers, list) or any(not isinstance(r, dict) for r in offers):
            raise ValueError('Invalid offer observations')
        known = [r['general_stock'] for r in offers if type(r.get('general_stock')) is int and r['general_stock'] >= 0]
        metrics = {'orders': orders, 'returns': returns, 'offer_rows': len(offers),
                   'stock_known_total': sum(known) if known else None,
                   'stock_unknown_rows': len(offers) - len(known), 'out_of_stock_rows': known.count(0)}
        result['metrics'] = metrics
        unavailable = '不可用' if zh else 'unavailable'
        def figure(value):
            return unavailable if value is None else str(value)
        lines += ['', '## 经营记录' if zh else '## Business records']
        for label, counts in ((('订单' if zh else 'Orders'), orders), (('退货' if zh else 'Returns'), returns)):
            lines += [(f"- {label}记录：本期 {figure(counts['current'])}；上期 {figure(counts['previous'])}；采集窗口内 {figure(counts['window_count'])}。" if zh else
                       f"- {label}: period {figure(counts['current'])}; previous period {figure(counts['previous'])}; captured window {figure(counts['window_count'])}.")]
        # Render only parseable window values, never arbitrary source annotations.
        window_labels = []
        for key in ('start', 'end'):
            value = window.get(key)
            try:
                window_labels.append(datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat())
            except (ValueError, AttributeError, TypeError):
                window_labels.append(unavailable)
        lines += [(f"采集窗口：{window_labels[0]} 至 {window_labels[1]}。" if zh else
                   f"Captured window: {window_labels[0]} to {window_labels[1]}."),
                  ('记录数包含取消等状态，不代表已结算销量。日期时区或覆盖范围未核实时，本期及上期指标显示不可用；窗口记录数不是昨日或本周销量。' if zh else
                   'Records include cancellations and other statuses, not settled sales. Period counts are unavailable when timestamp timezone or coverage is unverified; window counts are not yesterday/week sales.'),
                  '', '## 当前库存观测' if zh else '## Inventory at capture time',
                  (f"- 商品 {len(offers)}；已知库存合计 {figure(metrics['stock_known_total'])}；库存未知 {metrics['stock_unknown_rows']} 个；零库存 {metrics['out_of_stock_rows']} 个。" if zh else
                   f"- Offers {len(offers)}; known stock {figure(metrics['stock_known_total'])}; unknown stock rows {metrics['stock_unknown_rows']}; zero-stock rows {metrics['out_of_stock_rows']}.")]
        priorities = []
        if fresh == 'stale':
            priorities.append('检查采集服务和笔记本在线状态。' if zh else 'Check the collector and laptop availability.')
        if metrics['out_of_stock_rows']:
            priorities.append('复核零库存商品的可售状态与补货需求。' if zh else 'Review zero-stock offers and replenishment needs.')
        if metrics['stock_unknown_rows']:
            priorities.append('补查库存未知的商品，不按零库存处理。' if zh else 'Investigate unknown inventory without treating it as zero.')
        if orders['current'] is None or returns['current'] is None:
            priorities.append('核实平台时间口径与数据覆盖后，再比较按日／周业绩。' if zh else 'Verify source timezone and coverage before comparing day/week performance.')
        lines += ['', '## 优先检查' if zh else '## Priority checks']
        lines += ['- ' + text for text in priorities[:3]] or ['- ' + ('当前规则未发现上述待查项。' if zh else 'No checks triggered by these bounded rules.')]
        lines += ['', '未计算销售额、净利润或建议售价；库存变化不等于销量。' if zh else
                  'Revenue, net profit and recommended prices are not calculated; inventory changes are not sales.',
                  f"{'证据快照' if zh else 'Source snapshot'}: {snapshot['snapshot_id']}"]
    result['markdown'] = '\n'.join(lines)
    return result
