"""Explicit, source-bound promotion assumptions; never platform eligibility."""
from decimal import Decimal, localcontext
from app.services import emag_commerce as commerce, store_artifacts as artifacts

NUMBERS = ('discount_pct','voucher_pct','commission_reduction_pct','support_ex_vat_ron','extra_cost_ron')


def check(store_id, snapshot_id, product_id, payload):
    if not isinstance(payload,dict) or set(payload)-set(NUMBERS+('stacking',)):
        raise ValueError('Unknown promotion input')
    if payload.get('stacking','unknown') not in ('unknown','sequential'):
        raise ValueError('Unknown stacking assumption')
    values={}
    for key in NUMBERS:
        value=payload.get(key,None if key in ('support_ex_vat_ron','extra_cost_ron') else '0')
        if value is not None:
            if not isinstance(value,str):raise ValueError('Numeric inputs must be strings')
            value=commerce.number(value)
            if key.endswith('_pct') and value>100:raise ValueError('Percentage must be at most 100')
        values[key]=value
    with artifacts.snapshot_guard():
        view=commerce.view(store_id)
        if view['snapshot_id']!=snapshot_id:raise ValueError('Evidence is stale; reload first')
        product=next((p for p in view['products'] if str(p['offer']['id'])==product_id),None)
        if product is None:raise FileNotFoundError('Product absent from current snapshot')
        record=product['record']
        missing=[]
        if not record:missing.append('cost_record')
        elif record['stale']:missing.append('current_cost_record')
        inputs=dict(record['inputs']) if record and not record['stale'] else {}
        if values['extra_cost_ron'] is None:missing.append('extra_cost_ron')
        missing.extend(product['economics']['missing'] if record and not record['stale'] else commerce.COSTS)
        missing=list(dict.fromkeys(missing))
        result={'store_id':store_id,'snapshot_id':snapshot_id,'product_id':product_id,
                'status':'incomplete' if missing else 'review_required','price_basis':'exclusive_vat','currency':'RON',
                'cost_revision':record['revision'] if record else None,'missing':missing,
                'warnings':[{'code':'assumptions_require_verification','details':'Confirm entered fees, tax basis, campaign terms and support independently; estimates are not actual profit or eligibility approval.'}],
                'scenarios':[],'knowledge_query':'优惠券','marketplace_writes':False}
        if missing:return result
        with localcontext() as ctx:
            ctx.prec=80
            inputs['other_ron']=str(commerce.number(inputs['other_ron'])+values['extra_cost_ron'])
            inputs['commission_pct']=str(commerce.number(inputs['commission_pct'])*(1-values['commission_reduction_pct']/100))
            sale=commerce.number(product['offer']['sale_price'])
            factors=[('baseline',Decimal(1)),('discount',1-values['discount_pct']/100),('voucher',1-values['voucher_pct']/100)]
            if payload.get('stacking')=='sequential':factors.append(('sequential',(1-values['discount_pct']/100)*(1-values['voucher_pct']/100)))
            elif values['discount_pct'] and values['voucher_pct']:result['warnings'].append({'code':'stacking_unknown','details':'Discount and voucher are separate assumptions; combined eligibility is unknown.'})
            for kind,factor in factors:
                price=sale*factor
                economics=commerce.calculate(inputs,{**product['offer'],'sale_price':str(price)})['economics']
                support=values['support_ex_vat_ron']
                result['scenarios'].append({'kind':kind,'sale_price_ex_vat_ron':f'{price:.2f}','economics':economics,
                    'support_ex_vat_ron':None if support is None else str(support),
                    'contribution_with_assumed_support_ron':None if support is None else f"{Decimal(economics['contribution_ron'])+support:.2f}"})
        return result
