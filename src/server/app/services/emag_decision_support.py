"""Bounded observed offer blockers and missing evidence, without root-cause claims."""
from app.services import emag_commerce as commerce, emag_operations as operations, store_artifacts as artifacts


def view(store_id):
    with artifacts.snapshot_guard():
        snapshot=commerce.source(store_id)
        offers=snapshot['data']['offers']
        issues=operations._issues(snapshot)
        issues.sort(key=lambda i:(0 if type(i.get('general_stock')) is int and i['general_stock']>0 else 1 if i.get('general_stock') is None else 2,str(i['id']),i['reason']))
        cards=[]
        for issue in issues[:100]:
            offer=next(o for o in offers if o['id']==issue['id'])
            field='offer_validation_status' if issue['reason']=='invalid_price' else 'validation_status'
            stock=offer.get('general_stock')
            if type(stock) is not int or stock<0:stock=None
            cards.append({'id':issue['issue_id'],'product_id':str(offer['id']),'title_key':'insights.blocker.'+issue['reason'],
                'reason':issue['reason'],'priority':'high' if stock and stock>0 else 'review','stock':stock,
                'evidence':[{'field':field,'value':offer.get(field)},{'field':'general_stock','value':stock}],
                'checks':[{'key':'platform_status_details','status':'missing'},{'key':'product_data_and_category_requirements','status':'requires_review'},{'key':'confirmed_root_cause','status':'unknown'}],
                'knowledge_query':'价格' if issue['reason']=='invalid_price' else '商品'})
        return {'store_id':store_id,'snapshot_id':snapshot['snapshot_id'],'captured_at':snapshot['captured_at'],
                'products':[{'id':str(o['id']),'name':o.get('name') or str(o['id'])} for o in offers],
                'cards':cards,'marketplace_writes':False}
