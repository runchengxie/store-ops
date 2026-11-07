"""eMAG RO interpretation behind the common operations port."""
from app.platforms.contracts import AdapterDescriptor,Capability
from app.services import emag_operations,emag_workspace,emag_jobs,store_artifacts


class EmagAdapter:
    descriptor=AdapterDescriptor('emag','eMAG','1',('RO',),(
        Capability('overview','supported','read'),
        Capability('evidence_read','supported','read'),
        Capability('local_drafts','supported','local'),
        Capability('price_update','supported','write'),
        Capability('market_sales','unverified','read'),
    ))

    def stores(self):
        return [{**s,'platform':'emag','platform_label':'eMAG','marketplace':'RO','currency':'RON','timezone':'Europe/Bucharest'} for s in emag_operations.stores()]

    def overview(self,store_id):
        with store_artifacts.snapshot_guard():
            data=emag_workspace.view(store_id)
            try:
                receipt=emag_jobs.latest(store_id)
            except FileNotFoundError:
                receipt=None
            if receipt is not None and receipt.get('store_id')!=store_id:
                raise ValueError('Collection receipt belongs to another store')
            collection={k:receipt[k] for k in ('store_id','status','stage','started_at','updated_at','finished_at','snapshot_id','error_type') if k in receipt} if receipt else None
            stock=(data.get('commercial_summary') or {}).get('inventory',{}).get('general_stock_total')
            if type(stock) is not int or stock<0:
                stock=None
            return {'store_id':store_id,'platform':'emag','platform_label':'eMAG','marketplace':'RO','currency':'RON','timezone':'Europe/Bucharest',
                    'adapter_version':self.descriptor.version,'schema_version':1,
                    'snapshot_id':data['snapshot_id'],'captured_at':data['captured_at'],'source':data['source'],
                    'coverage':data['coverage'],'limitations':data['limitations'],
                    'metrics':{'products':len(data['offers']),'issues':len(data['issues']),'stock':stock},
                    'collection':collection,'marketplace_writes':False,
                    'readiness':{'overview':'available','price_update':'separate_opt_in_workflow'}}
