"""Recovery safeguards use existing exposure and recorded costs, never invented savings."""
from .domain import RuleError
from .money_display import money


def claim_summary(world, claim):
    tasks=[t for t in world.systems.get('service_tasks',[]) if t.get('department')=='legal' and t.get('target_id')==claim['id'] and t['recipient']==claim['owner']]
    return dict(spent=sum(t.get('outside_cost',0)+t.get('internal_cost',0) for t in tasks),
                recovered=sum(t.get('recovered',0) for t in tasks),
                attempts=sum(t['status']=='complete' for t in tasks),
                active=[t for t in tasks if t['status'] in ('queued','working')])


def check_recovery(world, task, outside_cost=0, new=False):
    if task['department']!='legal' or task['matter'] not in ('collection','dispute'):return
    claim=next((c for c in world.systems.get('legal_claims',[]) if c['id']==task['target_id'] and c['owner']==task['recipient']),None)
    lease=next((l for l in world.systems.get('leases',[]) if l['id']==task['target_id'] and l['owner']==task['recipient']),None)
    if not claim and not lease:return  # Customer invoices have their own staged recovery rules.
    others=[t for t in world.systems.get('service_tasks',[]) if t['id']!=task['id'] and t['recipient']==task['recipient'] and t.get('target_id')==task['target_id'] and t['department']=='legal' and t['matter'] in ('collection','dispute')]
    if claim and claim['status']!='open':raise RuleError('This warranty claim is already closed. No further legal spending is available.')
    if new and any(t['status'] in ('queued','working') for t in others):raise RuleError('Recovery is already queued for this claim or rent balance. Review that work instead of paying twice.')
    if not new:
        active=[t for t in world.systems.get('service_tasks',[]) if t in others or t['id']==task['id']]
        first=next((t for t in active if t['status'] in ('queued','working')),None)
        if first and first['id']!=task['id']:raise RuleError('An earlier recovery request already covers this claim or rent balance. Duplicate unfinished work was stopped.')
    if claim and any(t['status']=='complete' and not (t.get('requires_outside') and task['mode']=='outside') for t in others):raise RuleError('Legal already attempted this warranty claim. Review its documented outcome or close the claim in the decision inbox; repeating the same negotiation cannot improve the result.')
    exposure=claim['amount'] if claim else lease['arrears']
    spent=sum(t.get('internal_cost',0)+t.get('outside_cost',0) for t in others)+task.get('internal_cost',0)+task.get('outside_cost',0)
    if spent+outside_cost>=exposure:
        raise RuleError(f'Recovery would cost {money(spent+outside_cost)} including prior work against at most {money(exposure)} owed. Use qualified internal legal staff if worthwhile, or close the claim in the decision inbox. Recovery is uncertain.')


def close_claim(engine,args):
    from .campaign import Campaign
    claim=next((c for c in engine.world.systems.get('legal_claims',[]) if c['id']==args.get('claim_id') and c['status']=='open'),None)
    if not claim:raise RuleError('Choose an open warranty claim.')
    Campaign(engine).require(claim['owner'])
    if claim_summary(engine.world,claim)['active']:raise RuleError('Cancel unfinished recovery work before closing this claim; unused outside capacity can be refunded.')
    claim.update(status='closed',resolved=engine.world.date,resolution='Owner chose to stop pursuing this claim.')
    engine.event('Warranty claim closed',claim['fact']+' No cash recovered; actual legal expenses remain recorded.')
    return 'Claim closed. No cash recovered or new expense booked; prior legal costs remain in the accounts.'
