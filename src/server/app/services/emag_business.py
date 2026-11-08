"""Selected business evidence from fixed RO read-only endpoints. No PII fields."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import time
from app.services.automation_control import checkpoint
from app.services import emag_readonly, store_artifacts

BASE='https://marketplace-api.emag.ro/api-3/'
RESOURCES={'orders_fbe':'order/read','orders_seller':'order/read',
           'returns_fbe':'rma/read','returns_seller':'rma/read','invoices':'invoice/read','vat':'vat/read'}


def project(resource,row):
    if resource=='invoices':
        fields=('category','name','number','date','is_storno','total_without_vat','total_vat_value','total_with_vat','currency')
    elif resource=='vat':
        fields=('vat_id','vat_rate','is_default')
    else:
        fields=('id','emag_id','order_id','type','status','request_status','date','modified','payment_status','shipping_tax','currency','refunded_amount','refund_status')
    result={k:row[k] for k in fields if k in row}
    if resource.startswith(('orders','returns')):
        fields=('product_id','part_number','part_number_key','quantity','sale_price','vat','status','initial_qty','storno_qty','retained_amount','return_reason')
        products=row.get('products')
        if not isinstance(products,list) or any(not isinstance(p,dict) for p in products):
            raise ValueError('Business record has invalid product rows')
        result['products']=[{k:p[k] for k in fields if k in p} for p in products]
    return result


def read_resource(client,auth,resource,filters,*,delay=1,max_pages=100):
    endpoint=BASE+RESOURCES[resource]
    rows=[];seen=set();total=None
    for page in range(1,max_pages+1):
        time.sleep(delay)
        checkpoint()
        response=client.post(endpoint,json={**filters,'currentPage':page,'itemsPerPage':100},auth=auth,follow_redirects=False)
        if not response.is_success:
            raise ValueError(f'{resource}: HTTP {response.status_code}')
        try:body=response.json()
        except ValueError:raise ValueError(f'{resource}: invalid JSON') from None
        if not isinstance(body,dict) or body.get('isError') is not False:
            raise ValueError(f'{resource}: API rejected request')
        result=body.get('results')
        if resource=='invoices':
            if not isinstance(result,dict) or type(result.get('total_results')) is not int or result['total_results']<0:
                raise ValueError('Invoice result requires a documented nonnegative total')
            if total is not None and result['total_results']!=total:
                raise ValueError('Invoice total changed during pagination')
            total=result['total_results'];result=result.get('invoices')
        if not isinstance(result,list) or any(not isinstance(r,dict) for r in result):
            raise ValueError(f'{resource}: invalid result schema')
        for row in result:
            clean=project(resource,row)
            key=(clean.get('category'),clean.get('number')) if resource=='invoices' else (clean.get('vat_id'),) if resource=='vat' else (clean.get('id',clean.get('emag_id')),)
            if any(v is None for v in key) or key in seen:
                raise ValueError(f'{resource}: missing or repeated identity')
            seen.add(key);rows.append(clean)
        if resource=='vat' or len(result)<100:
            if total is not None and (type(total) is not int or total!=len(rows)):
                raise ValueError('Invoice total changed or pagination is incomplete')
            return rows
    raise ValueError(f'{resource}: page limit reached')


def summarize(data):
    stock_total=0;bands=Counter();unknown=0;differences=[];stock_known=0;aging_known=0
    for row in data['offers']:
        stock=row.get('general_stock');aging=row.get('stock_2p_aging_bands')
        if type(stock) is int and stock>=0:stock_total+=stock;stock_known+=1
        else:unknown+=1
        if isinstance(aging,dict) and aging and all(type(v) is int and v>=0 for v in aging.values()):
            aging_known+=1
            bands.update(aging)
            if type(stock) is int and sum(aging.values())!=stock:
                differences.append({'id':row['id'],'part_number':row.get('part_number'),'general_stock':stock,'aging_total':sum(aging.values())})
        else:unknown+=1
    totals=defaultdict(Decimal);invalid_invoices=0
    for row in data['invoices']:
        try:
            value=Decimal(str(row['total_with_vat']))
            if not value.is_finite() or not row.get('currency') or not row.get('category'):raise ValueError()
            totals[(row['category'],row['currency'])]+=value
        except (InvalidOperation,ValueError,KeyError):invalid_invoices+=1
    return {'orders_fbe_count':len(data['orders_fbe']),'orders_seller_count':len(data['orders_seller']),
            'order_status_counts':dict(Counter(str(r.get('status','unknown')) for r in data['orders_fbe']+data['orders_seller'])),
            'returns_fbe_count':len(data['returns_fbe']),'returns_seller_count':len(data['returns_seller']),
            'invoice_count':len(data['invoices']),'invoice_amount_unknown':invalid_invoices,
            'invoice_totals':[{'category':k[0],'currency':k[1],'amount_as_reported':str(v)} for k,v in sorted(totals.items())],
            'purchase_cost_status':'missing','profit':None,
            'inventory':{'general_stock_total':stock_total if stock_known else None,'aging_total':sum(bands.values()) if aging_known else None,'aging_bands':dict(bands),
                         'stock_rows_known':stock_known,'stock_rows_unknown':len(data['offers'])-stock_known,
                         'aging_rows_known':aging_known,'aging_rows_unknown':len(data['offers'])-aging_known,
                         'unknown_observations':unknown,'mismatched_skus':len(differences),'differences':differences,
                         'reserved_stock':None,'in_transit_stock':None}}


def collect(client,auth,days=29,*,secrets=()):
    if type(days) is not int or not 1<=days<=29:raise ValueError('Window must be 1–29 days')
    end=datetime.now(timezone.utc);start=end-timedelta(days=days)
    window={'start':start.strftime('%Y-%m-%d %H:%M:%S'),'end':end.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone_note':'UTC values sent as naive API filter strings; platform timezone unverified'}
    offers=emag_readonly.collect(client,auth)
    if not offers['complete']:raise ValueError('Offer collection incomplete')
    offers=emag_readonly.redact(offers,secrets)
    # Add only inventory/price evidence absent from the basic projection.
    data={'offers':[{**emag_readonly.project_offer(r),**{k:r[k] for k in ('stock_2p_aging_bands','main_offer_price','min_sale_price','max_sale_price') if k in r}} for r in offers['offers']]}
    for resource in RESOURCES:
        if resource.startswith('orders'):
            filters={'type':2 if resource.endswith('fbe') else 3,'createdAfter':window['start'],'createdBefore':window['end']}
        elif resource.startswith('returns'):
            filters={'type':2 if resource.endswith('fbe') else 3,'date_start':window['start'],'date_end':window['end']}
        elif resource=='invoices':filters={'date_start':start.date().isoformat(),'date_end':end.date().isoformat()}
        else:filters={}
        data[resource]=read_resource(client,auth,resource,filters)
    summary=summarize(data)
    summary['window']=window
    return {'data':data,'summary':summary,'window':window}


def publish(store_id,evidence):
    return store_artifacts.import_snapshot({'store_id':store_id,'platform':'emag','marketplace':'RO',
        'captured_at':datetime.now(timezone.utc).isoformat(),'source':BASE,
        'coverage':['product_offer/read with aging bands','order/read types 2 and 3','rma/read types 2 and 3','invoice/read','vat/read'],
        'limitations':['Sequential API reads are not atomic; collection time is consolidation time.',
            evidence['window']['timezone_note'], 'Invoice date window differs from order timestamp window and service period.',
            'Invoice signs preserved as reported; invoices are not proof of payment or SKU-level profit.',
            'Purchase costs missing; no profit or recommended selling price calculated.',
            'Aging bands and general_stock may differ; reserved and in-transit stock unverified.',
            'Customer identities, addresses, attachments and unstructured notes excluded.'],
        'data':{'offers':evidence['data']['offers'],'commercial_summary':evidence['summary'],
                'commercial_evidence':{k:v for k,v in evidence['data'].items() if k!='offers'}}})
