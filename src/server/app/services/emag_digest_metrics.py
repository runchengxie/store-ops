"""Pure product-unit and inventory summaries for saved operations reports."""
from collections import Counter
import re
import unicodedata


def label(offer, product_id):
    product_id = _product_id(product_id)
    if product_id is None:
        raise ValueError('A valid product identifier is required')
    fallback = ('ID ' + product_id)[:48]
    value = offer.get('part_number') or offer.get('part_number_key') or fallback
    if not isinstance(value, str):
        value = fallback
    value = re.sub(r'https?://\S+', ' ', value, flags=re.I)
    value = ''.join(' ' if unicodedata.category(c).startswith('C') or c in '[](){}<>!`*#|@\\' else c for c in value)
    return ' '.join(value.split())[:48] or fallback


def _code(value, choices):
    return str(value) if type(value) in (int, str) and str(value) in choices else None


def _quantity(value):
    if isinstance(value, str) and re.fullmatch(r'[0-9]{1,12}', value):
        value = int(value)
    return value if type(value) is int and value >= 0 else None


def _product_id(value):
    if type(value) not in (int, str):
        return None
    value = str(value)
    return value if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value) else None


def _units(rows, catalog):
    result = {'units': None, 'known_units': None, 'invalid_records': 0, 'top': None,
              'product_count': None, 'cutoff_tied_products': 0, 'all_tied': False}
    if rows is None:
        return result
    known, invalid, missing_identity = 0, 0, False
    grouped = Counter()
    for row in rows:
        status = _code(row.get('status'), {'0', '1', '2', '3', '4', '5'}) if isinstance(row, dict) else None
        if status is None:
            invalid += 1
            continue
        if status != '4':
            continue
        lines = row.get('products')
        if not isinstance(lines, list) or not lines:
            invalid += 1
            continue
        for line in lines:
            active = _code(line.get('status'), {'0', '1'}) if isinstance(line, dict) else None
            if active is None:
                invalid += 1
                continue
            if active == '0':
                continue
            quantity = _quantity(line.get('quantity'))
            if quantity is None:
                invalid += 1
                continue
            known += quantity
            product_id = _product_id(line.get('product_id'))
            if product_id is None and quantity:
                missing_identity = True
            elif quantity:
                grouped[product_id] += quantity
    result.update(known_units=known, invalid_records=invalid)
    if invalid:
        return result
    result['units'] = known
    if missing_identity:
        return result
    ranked = sorted(grouped.items(), key=lambda item: (-item[1], item[0]))
    result.update(product_count=len(ranked), top=[{'product_id': key, 'label': label(catalog.get(key, {}), key),
                                                 'units': units} for key, units in ranked[:3]])
    if len(ranked) > 3:
        result['cutoff_tied_products'] = sum(units == ranked[2][1] for _, units in ranked)
        result['all_tied'] = len({units for _, units in ranked}) == 1
    return result


def products(current_rows, previous_rows, offers):
    catalog = {str(offer.get('id')): offer for offer in offers}
    current, previous = _units(current_rows, catalog), _units(previous_rows, catalog)
    change = current['units'] - previous['units'] if current['units'] is not None and previous['units'] is not None else None
    return {'current': current, 'previous': previous, 'change': change}


def inventory(snapshot):
    from app.services import emag_clearance
    identities = [_product_id(offer.get('id')) for offer in snapshot['data']['offers']]
    if any(identity is None for identity in identities) or len(set(identities)) != len(identities):
        raise ValueError('Inventory requires valid unique product identifiers')
    result = emag_clearance.build(snapshot)
    summary = result['summary']
    catalog = {str(offer['id']): offer for offer in snapshot['data']['offers']}
    unverified = summary['aging_inconsistent_products'] + summary['aging_unknown_products']
    priorities = [row for row in result['rows'] if row['priority'] == 'restore_sales'][:3]
    return {'blocked_products': summary['blocked_with_stock_products'],
            'blocked_units': summary['blocked_with_stock_units'],
            'stock_unknown_products': summary['unknown_stock_products'],
            'aged_181_plus_units': summary['aged_181_plus_known'], 'aging_unverified_products': unverified,
            'aging_is_partial': unverified > 0,
            'priorities': [{'product_id': row['offer_id'], 'label': label(catalog[row['offer_id']], row['offer_id']),
                            'stock': row['stock']} for row in priorities]}


def render_products(result, locale):
    zh = locale == 'zh-CN'
    current, previous = result['current'], result['previous']
    unknown = '暂缺' if zh else 'unavailable'
    def value(n):
        return unknown if n is None else str(n)
    lines = ['', '## 商品表现' if zh else '## Product performance',
             (f"- 已完成订单商品：本期 {value(current['units'])} 件；上期 {value(previous['units'])} 件。" if zh else
              f"- Finalized-order product units: {value(current['units'])}; previous {value(previous['units'])}.")]
    if current['units'] is None:
        lines.append('商品件数待核对，明细不足时不按零计算。' if zh else 'Product-unit evidence needs verification; missing detail is not zero.')
    elif current['top'] is None:
        lines.append('商品排行待核对：部分商品标识不完整。' if zh else 'Product ranking needs verification: some product identities are missing.')
    elif current['top']:
        lines.append('商品件数前 3：' if zh else 'Top 3 products by units:')
        if current['all_tied']:
            lines.append((f"{current['product_count']} 款商品均为 {current['top'][0]['units']} 件，以下展示其中 3 款。" if zh else
                          f"All {current['product_count']} products tie at {current['top'][0]['units']} units; showing 3 of them."))
        elif current['cutoff_tied_products'] > 1:
            lines.append((f"末位有 {current['cutoff_tied_products']} 款并列 {current['top'][-1]['units']} 件，仅展示前 3 款。" if zh else
                          f"{current['cutoff_tied_products']} products tie at the cutoff of {current['top'][-1]['units']} units; showing 3 products."))
        lines += [f"- {row['label']}：{row['units']} 件" if zh else f"- {row['label']}: {row['units']} units" for row in current['top']]
    return lines


def render_inventory(result, locale):
    zh = locale == 'zh-CN'
    partial = ('（已知部分）' if zh else ' (known portion)') if result['stock_unknown_products'] else ''
    lines = ['', '## 库存关注' if zh else '## Inventory priorities',
             (f"- 有库存且校验异常{partial}：{result['blocked_products']} 款，涉及 {result['blocked_units']} 件。" if zh else
              f"- Stocked offers with validation issues{partial}: {result['blocked_products']} products / {result['blocked_units']} units.")]
    aged, pending = result['aged_181_plus_units'], result['aging_unverified_products']
    if aged is None:
        lines.append(f'- 库存龄待核对：{pending} 款。' if zh else f'- Inventory aging needs verification: {pending} products.')
    elif result['aging_is_partial']:
        lines.append(f'- 181 天以上库存（已核对部分）：{aged} 件；另有 {pending} 款待核对。' if zh else
                     f'- 181+ day stock (reconciled portion): {aged} units; {pending} other products need verification.')
    else:
        lines.append(f'- 181 天以上库存：{aged} 件。' if zh else f'- 181+ day stock: {aged} units.')
    if result['priorities']:
        lines.append('优先核对的库存商品：' if zh else 'Stocked products to review first:')
        lines += [f"- {row['label']}：库存 {row['stock']} 件" if zh else f"- {row['label']}: {row['stock']} units in stock"
                  for row in result['priorities']]
    return lines
