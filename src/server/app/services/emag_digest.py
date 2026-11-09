"""Bounded, deterministic period reports from saved eMAG evidence; no network."""
from datetime import datetime, time, timedelta
from collections import Counter
import re
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


def _calendar_time(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?', value):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _calendar_contract(snapshot, prefix, window):
    resource = 'order/read types 2 and 3' if prefix == 'orders' else 'rma/read types 2 and 3'
    return (snapshot.get('source', '').rstrip('/') == 'https://marketplace-api.emag.ro/api-3'
            and resource in snapshot.get('coverage', [])
            and window.get('timezone_note') == 'UTC values sent as naive API filter strings; platform timezone unverified')


def _counts(evidence, prefix, window, start, end, calendar_allowed=False):
    rows = _records(evidence, prefix)
    result = {'current': None, 'previous': None, 'change': None, 'current_statuses': None,
              'basis': 'unavailable', 'window_count': None if rows is None else len(rows)}
    if rows is None:
        return result
    window_start, window_end = _aware(window.get('start')), _aware(window.get('end'))
    dates = [_aware(row.get('date')) for row in rows]
    verified = (window.get('timezone_verified') is True and window_start and window_end
                and 'unverified' not in str(window.get('timezone_note', '')).lower()
                and all(d is not None for d in dates))
    if verified:
        result['basis'] = 'verified_timezone'
    elif calendar_allowed:
        window_start, window_end = (_calendar_time(window.get(k)) for k in ('start', 'end'))
        dates = [_calendar_time(row.get('date')) for row in rows]
        if (not window_start or not window_end or window_start >= window_end
                or any(d is None or not window_start <= d <= window_end for d in dates)):
            return result
        # Compare the API's calendar labels, without assigning a UTC offset or
        # claiming that those labels represent verified business-time instants.
        start, end = start.replace(tzinfo=None), end.replace(tzinfo=None)
        result['basis'] = 'platform_calendar'
    else:
        return result
    previous = start - (end - start)  # Calendar-aware local midnight arithmetic.
    for name, lower, upper in (('current', start, end), ('previous', previous, start)):
        if window_start <= lower and window_end >= upper:
            result[name] = sum(lower <= d < upper for d in dates)
            if name == 'current':
                field = 'status' if prefix == 'orders' else 'request_status'
                allowed = {str(n) for n in (range(6) if prefix == 'orders' else range(1, 8))}
                result['current_statuses'] = dict(Counter(
                    str(row.get(field)) if type(row.get(field)) in (int, str) and str(row.get(field)) in allowed else 'unknown'
                    for row, d in zip(rows, dates) if lower <= d < upper))
    if result['current'] is not None and result['previous'] is not None:
        result['change'] = result['current'] - result['previous']
    return result


def _order_period_rows(evidence, counts, start, end):
    rows = _records(evidence, 'orders')
    if rows is None or counts['basis'] == 'unavailable':
        return None, None
    parser = _aware
    if counts['basis'] == 'platform_calendar':
        parser = _calendar_time
        start, end = start.replace(tzinfo=None), end.replace(tzinfo=None)
    dated = [(row, parser(row.get('date'))) for row in rows]
    if any(date is None for _, date in dated):
        return None, None
    selected = []
    for key, lower, upper in (('current', start, end), ('previous', start - (end - start), start)):
        group = [row for row, date in dated if lower <= date < upper] if counts[key] is not None else None
        selected.append(group if group is not None and len(group) == counts[key] else None)
    return tuple(selected)


def build(snapshot, kind, now, timezone_name='Europe/Bucharest', locale='en', *, store_id=None):
    if locale not in ('en', 'zh-CN'):
        raise ValueError('Unsupported report locale')
    from app.services.store_artifacts import validate_id
    store_id = validate_id(snapshot['store_id'] if snapshot else store_id)
    p = period(kind, now, timezone_name)
    display_end = (datetime.fromisoformat(p['end']).date() - timedelta(days=1)).isoformat()
    display_dates = p['start'] if kind == 'daily' else p['start'] + ' 至 ' + display_end
    if locale == 'en' and kind == 'weekly':
        display_dates = p['start'] + ' to ' + display_end
    zh = locale == 'zh-CN'
    title = ('经营日报' if kind == 'daily' else '经营周报') if zh else ('Daily store report' if kind == 'daily' else 'Weekly store report')
    lines = [f'# {title} · {store_id}', '',
             (f"统计日期：{display_dates}（{timezone_name}）" if zh else
              f"Dates: {display_dates} ({timezone_name})")]
    detail_lines = []
    result = {'schema_version': 1, 'store_id': store_id, 'kind': kind, 'period': p,
              'timezone': timezone_name, 'locale': locale, 'generated_at': now.isoformat(),
              'snapshot_id': None, 'captured_at': None, 'freshness': 'missing', 'date_basis': 'unavailable',
              'metrics': {}, 'evidence': {}}
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
        if fresh == 'stale':
            lines += ['', '数据已过期，以下仅为历史观测。' if zh else 'STALE evidence: historical observations only.']
        lines += ['', f"{'数据更新' if zh else 'Updated'}: {captured_display}"]
        data = snapshot['data']
        window = data.get('commercial_summary', {}).get('window', {})
        evidence = data.get('commercial_evidence', {})
        zone = ZoneInfo(timezone_name)
        start, end = (datetime.combine(datetime.fromisoformat(p[k]).date(), time(), zone) for k in ('start', 'end'))
        orders = _counts(evidence, 'orders', window, start, end, _calendar_contract(snapshot, 'orders', window))
        returns = _counts(evidence, 'returns', window, start, end, _calendar_contract(snapshot, 'returns', window))
        bases = {counts['basis'] for counts in (orders, returns) if counts['basis'] != 'unavailable'}
        result['date_basis'] = next(iter(bases)) if len(bases) == 1 else 'mixed' if bases else 'unavailable'
        if 'platform_calendar' in bases:
            lines[2] = (f"统计日期：{display_dates}（eMAG 平台日期）" if zh else
                        f"Dates: {display_dates} (eMAG platform calendar dates)")
        offers = data.get('offers')
        if not isinstance(offers, list) or any(not isinstance(r, dict) for r in offers):
            raise ValueError('Invalid offer observations')
        known = [r['general_stock'] for r in offers if type(r.get('general_stock')) is int and r['general_stock'] >= 0]
        metrics = {'orders': orders, 'returns': returns, 'offer_rows': len(offers),
                   'stock_known_total': sum(known) if known else None,
                   'stock_unknown_rows': len(offers) - len(known), 'out_of_stock_rows': known.count(0)}
        result['metrics'] = metrics
        from app.services import emag_digest_metrics
        current_orders, previous_orders = _order_period_rows(evidence, orders, start, end)
        product_metrics = emag_digest_metrics.products(current_orders, previous_orders, offers)
        inventory_risks = emag_digest_metrics.inventory(snapshot)
        metrics.update(products=product_metrics, inventory_risks=inventory_risks)
        unavailable = '不可用' if zh else 'unavailable'
        def figure(value):
            return unavailable if value is None else str(value)
        lines += ['', '## 经营记录' if zh else '## Business records']
        previous_label = ('前一日' if kind == 'daily' else '再前一周') if zh else 'previous period'
        for label, counts in ((('订单' if zh else 'Order records'), orders), (('退货申请' if zh else 'Return requests'), returns)):
            change = (f"；变化 {counts['change']:+d}" if zh else f"; change {counts['change']:+d}") if counts['change'] is not None else ''
            lines += [(f"- {label}：本期 {figure(counts['current'])}；{previous_label} {figure(counts['previous'])}{change}。" if zh else
                       f"- {label}: period {figure(counts['current'])}; previous period {figure(counts['previous'])}{change}.")]
        if orders['current_statuses'] is not None:
            statuses = orders['current_statuses']
            labels = {'0': '取消' if zh else 'canceled', '1': '新订单' if zh else 'new',
                      '2': '处理中' if zh else 'in progress', '3': '已备货' if zh else 'prepared',
                      '4': '已完成' if zh else 'finalized', '5': '已退货' if zh else 'returned'}
            parts = [f'{label} {statuses[code]}' for code, label in labels.items() if statuses.get(code)]
            unknown = sum(v for k, v in statuses.items() if k not in labels)
            if unknown:
                parts.append(('状态未知 ' if zh else 'unknown ') + str(unknown))
            lines += [('本期订单状态：' if zh else 'Order statuses: ') +
                      ('；'.join(parts) if parts else '本期无订单。' if zh else 'No orders in this period.')]
        lines += emag_digest_metrics.render_products(product_metrics, locale)
        if 'platform_calendar' in bases:
            detail_lines += [('按 eMAG 返回的日期分组，时区尚未核实；未将其转换成精确的罗马尼亚时刻。' if zh else
                              'Grouped by eMAG platform calendar date labels; timezone is unverified. These are not converted into verified Romania-time instants.')]
        if orders['current'] is None or returns['current'] is None:
            lines += [('部分指标不可用：来源日期、时区或采集覆盖不兼容，不能据此填零。' if zh else
                       'Some figures are unavailable because source dates, timezone or coverage are incompatible; unknown is not zero.')]
        # Render only parseable window values, never arbitrary source annotations.
        window_labels = []
        window_values = []
        for key in ('start', 'end'):
            value = window.get(key)
            try:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat()
            except (ValueError, AttributeError, TypeError):
                parsed = None
            window_values.append(parsed)
            window_labels.append(parsed if parsed is not None else unavailable)
        result['evidence'] = {'window_start': window_values[0], 'window_end': window_values[1],
                              'window_counts': {'orders': orders['window_count'], 'returns': returns['window_count']},
                              'date_basis': result['date_basis'], 'snapshot_id': snapshot['snapshot_id'],
                              'product_known_units': {key: product_metrics[key]['known_units'] for key in ('current', 'previous')},
                              'product_invalid_records': {key: product_metrics[key]['invalid_records'] for key in ('current', 'previous')}}
        detail_lines += [(f"采集窗口：{window_labels[0]} 至 {window_labels[1]}。" if zh else
                   f"Captured window: {window_labels[0]} to {window_labels[1]}."),
                  (f"完整采集窗口共有订单 {figure(orders['window_count'])}、退货申请 {figure(returns['window_count'])}。窗口总数与本期指标分开；订单记录含取消等状态，不代表已结算销量。" if zh else
                   f"Full captured window: {figure(orders['window_count'])} orders, {figure(returns['window_count'])} return requests. Window totals are separate from period figures. Records include cancellations and are not settled sales."),
                  '订单状态为采集时状态，按下单日期归组。' if zh else 'Order statuses are observed at capture and grouped by creation date.']
        lines += ['', '## 当前库存观测' if zh else '## Inventory at capture time',
                  (f"- 商品 {len(offers)}；已知库存合计 {figure(metrics['stock_known_total'])}；库存未知 {metrics['stock_unknown_rows']} 个；零库存 {metrics['out_of_stock_rows']} 个。" if zh else
                   f"- Offers {len(offers)}; known stock {figure(metrics['stock_known_total'])}; unknown stock rows {metrics['stock_unknown_rows']}; zero-stock rows {metrics['out_of_stock_rows']}.")]
        lines += emag_digest_metrics.render_inventory(inventory_risks, locale)
        priorities = []
        if fresh == 'stale':
            priorities.append('检查采集服务和笔记本在线状态。' if zh else 'Check the collector and laptop availability.')
        if inventory_risks['blocked_products']:
            priorities.append('优先核对有库存商品的校验问题。' if zh else 'Review validation issues on stocked offers first.')
        if inventory_risks['aged_181_plus_units']:
            priorities.append('复核老库存的销售计划。' if zh else 'Review the sales plan for older inventory.')
        if inventory_risks['aging_unverified_products']:
            priorities.append('核对库存龄与总库存不一致或尚缺的数据。' if zh else 'Reconcile missing or inconsistent inventory aging.')
        if metrics['out_of_stock_rows'] and not inventory_risks['blocked_products'] and not inventory_risks['aged_181_plus_units']:
            priorities.append('复核零库存商品的可售状态与补货需求。' if zh else 'Review zero-stock offers and replenishment needs.')
        if metrics['stock_unknown_rows']:
            priorities.append('补查库存未知的商品，不按零库存处理。' if zh else 'Investigate unknown inventory without treating it as zero.')
        if orders['current'] is None or returns['current'] is None:
            priorities.append('核实平台时间口径与数据覆盖后，再比较按日／周业绩。' if zh else 'Verify source timezone and coverage before comparing day/week performance.')
        lines += ['', '## 优先检查' if zh else '## Priority checks']
        lines += ['- ' + text for text in priorities[:3]] or ['- ' + ('当前规则未发现上述待查项。' if zh else 'No checks triggered by these bounded rules.')]
        detail_lines += ['', '未计算销售额、净利润或建议售价；库存变化不等于销量。' if zh else
                  'Revenue, net profit and recommended prices are not calculated; inventory changes are not sales.',
                  ('商品件数取采集时已完成订单中的有效商品数量，按原下单日期归组；未完成或退货订单不计入，不等于当期出库或结算销量。' if zh else
                   'Product units use current active quantities on finalized orders, grouped by original creation date; pending/returned orders are excluded. This is not period fulfillment or settled sales.'),
                  (f"商品明细待核对记录：本期 {product_metrics['current']['invalid_records']}，上期 {product_metrics['previous']['invalid_records']}。" if zh else
                   f"Product records needing verification: current {product_metrics['current']['invalid_records']}, previous {product_metrics['previous']['invalid_records']}."),
                  (f"商品件数已确认小计：本期 {figure(product_metrics['current']['known_units'])}，上期 {figure(product_metrics['previous']['known_units'])}；明细不完整时该小计不作为完整总数。" if zh else
                   f"Known product-unit subtotal: current {figure(product_metrics['current']['known_units'])}, previous {figure(product_metrics['previous']['known_units'])}; an incomplete subtotal is not a complete total."),
                  f"{'证据快照' if zh else 'Source snapshot'}: {snapshot['snapshot_id']}"]
    result['markdown'] = '\n'.join(lines)
    result['details_markdown'] = result['markdown']
    if detail_lines:
        result['details_markdown'] += '\n\n' + ('## 口径与证据' if zh else '## Basis and evidence') + '\n\n' + '\n'.join(detail_lines)
    return result
