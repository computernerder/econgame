"""Reconcile queued obligations and escrow to the same persisted ledger."""
from .domain import RuleError


def validate_extensions(world):
    for records,owner,key in [('developments','owner','asset:development_reserve'),('property_service_jobs','owner','asset:prepaid_property_services'),('service_tasks','recipient','asset:prepaid_services'),('property_work','owner','asset:prepaid_works'),('flip_progress','entity','asset:flip_reserve')]:
        values=world.systems.get(records,[] if records!='flip_progress' else {})
        rows=list(values.values()) if isinstance(values,dict) else values
        expected={}
        for row in rows:
            value=row.get('reserve',0) if records=='flip_progress' else row.get('prepaid',0)
            if value<0 or row.get('remaining',0)<0:raise RuleError('Work or project reserves cannot be negative.')
            expected[row[owner]]=expected.get(row[owner],0)+value
        for entity,accounts in world.accounts.items():
            if accounts.get(key,0)!=expected.get(entity,0):raise RuleError('Work and project cash reserves do not reconcile.')
    for bid,state in world.systems.get('industry_state',{}).items():
        if bid in world.accounts and state.get('finished_cost',0)!=world.accounts[bid].get('asset:finished_goods',0):
            raise RuleError('Finished manufacturing inventory does not reconcile.')
    for uid,record in world.systems.get('operating_locations',{}).items():
        unit=next((b for b in world.businesses if b.id==uid),None)
        if not unit or record['company']==uid or unit.owner!=record['company']:
            raise RuleError('A location must remain within its legal company.')
    for task in world.systems.get('service_tasks',[]):
        if task.get('product')=='onboarding' and not 0<=task['participant_done']<=task['participant_required']:
            raise RuleError('Paid onboarding participation exceeds its reserved requirement.')
    for systems in world.systems.get('deployed_systems',{}).values():
        for system in systems.values():
            if not 0<=system['condition']<=100:raise RuleError('Deployed system condition is outside its supported range.')
    for job in world.systems.get('property_service_jobs',[]):
        if job['paid']!=job['prepaid']+job['expense']+job['refunded'] or not 0<=job['completed_visits']<=job['visits']:
            raise RuleError('Property service reserves do not reconcile to delivery and refunds.')
    for facts in world.systems.get('property_care',{}).values():
        if not all(0<=facts[k]<=100 for k in ('cleanliness','grounds')):raise RuleError('Property care condition is outside its range.')
    credits={}
    for contract in world.systems.get('supplier_contracts',[]):
        if contract['available']<0 or contract['credit']!=contract['available']*contract['rate']:
            raise RuleError('Supplier credit minutes do not reconcile to their prepaid value.')
        credits[contract['buyer']]=credits.get(contract['buyer'],0)+contract['credit']
        reserved=sum(t.get('prepaid',0) for t in world.systems.get('service_tasks',[]) if t.get('supplier_contract')==contract['id'])
        if contract['paid']!=contract['credit']+reserved+contract['expense']+contract['expired_cost']:
            raise RuleError('Supplier payment does not reconcile to credit, projects and actual expenses.')
        if not 0<=contract['used_today']<=contract['daily_capacity']:raise RuleError('Supplier daily delivery exceeds reserved capacity.')
    for entity,accounts in world.accounts.items():
        if accounts.get('asset:service_credit',0)!=credits.get(entity,0):raise RuleError('Supplier credits do not reconcile to the ledger.')
