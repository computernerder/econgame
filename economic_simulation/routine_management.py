"""Manager-led care and collections using existing employees and authority."""
from datetime import date, timedelta
from .campaign import Campaign, flag, integer
from .domain import RuleError
from .manager_defaults import limits as manager_limits,collection_limit,action_limit


def policy(world,b):
    old=world.systems.get('operating_automation',{}).get(b.id,{})
    return {**dict(collections=True,agency=True,legal_collections=True,write_off=True,
                   write_off_limit=min(100000,manager_limits(b)['purchasing_limit']),
                   collection_limit=collection_limit(b),property_care=old.get('property_operations',True),
                   renew_services=True,prefer_owned=True,care_threshold=60,visits=4,
                   period_limit=max(manager_limits(b)['purchasing_limit'],collection_limit(b))*4),
            **b.authority.get('routine_management',{})}


class RoutineManagement(Campaign):
    def action(self,args):
        from .business_rules import BusinessRules
        b=BusinessRules(self.e).company(args.get('business_id',''))
        p=policy(self.w,b)
        for key in ('collections','agency','legal_collections','write_off','property_care','renew_services','prefer_owned'):
            if key in args:p[key]=flag(args[key])
        for key,low,high in [('care_threshold',20,85),('visits',1,20),('period_limit',0,1000000000),('collection_limit',0,1000000000),('write_off_limit',0,1000000000)]:
            if key in args:p[key]=integer(args[key],low,high)
        b.authority['routine_management']={**b.authority.get('routine_management',{}),**{key:p[key] for key in args if key in p}}
        return 'Routine management policy saved. The available local manager acts first; a director covers missing managers. Default coverage includes company-owned properties in other counties. Explicit county restrictions, purchase limits, monthly commitments and cash reserves still apply.'

    def capacity(self,employee,record):
        if not employee:return 0
        # Routine follow-up has a finite daily administrative allowance, shared
        # across every business an acting director covers.
        limit=min(60 if record else 120,employee.weekly_hours*60//max(1,len(employee.days)))
        used=sum(20 if r['action']=='property_service' else 10 for r in self.s.get('authority_audit',[])
                 if r.get('actor')==employee.id and r['date']==self.w.date and r['action'] in ('property_service','recover_invoice','service_request','write_off_invoice'))
        return max(0,limit-used)

    def perform(self,leader,b,key,action,args,cost,detail,minutes):
        record,employee=leader.actor(b,action,args)
        if self.capacity(employee,record)<minutes:return False
        # Retry only the generated property-care questions selected for a fresh
        # policy review. Other exceptions and player deferrals stay untouched.
        if (b.id,key) not in getattr(self,'rechecking',set()) and any(r['business_id']==b.id and r['key']==key and r['status']=='open' for r in self.s.get('management_requests',[])):return False
        monthly=sum(r['commitment'] for r in self.s.get('authority_audit',[])
                    if r['business_id']==b.id and r['date'][:7]==self.w.date[:7] and r['action'] in ('property_service','recover_invoice','service_request','write_off_invoice'))
        if cost and monthly+cost>policy(self.w,b)['period_limit']:
            leader.request(b,key,action,args,cost,detail+' The full commitment exceeds the routine monthly budget.');return False
        return leader.perform(b,key,action,args,cost,cost<=action_limit(b,action,args),detail)

    def collection_proposal(self,b,invoice,settings):
        attempts=invoice.get('recovery_attempts',[])
        method=next((m for m in ('reminder','plan','agency') if m not in attempts and (m!='agency' or settings['agency'])),None)
        if method:
            return ('recover_invoice',dict(entity=b.id,invoice_id=invoice['id'],method=method),
                    invoice['amount']//4 if method=='agency' else 0,
                    {'reminder':'Send a free reminder','plan':'Request three installments','agency':'Use a contingency agency; its fee comes only from recovered cash'}[method])
        completed=any(t['recipient']==b.id and t['target_id']==invoice['id'] and t['department']=='legal'
                      and t['matter'] in ('collection','dispute') and t['status']=='complete' for t in self.s.get('service_tasks',[]))
        # Paid legal work must have a plausible recovery greater than its cost.
        from .service_office import DEPARTMENTS
        cost=DEPARTMENTS['legal'][1]*150
        if settings['legal_collections'] and not completed and invoice['amount']>cost*2:
            provider='outside'
            if settings['prefer_owned']:
                from .business_rules import BusinessRules
                from .qualified_capacity import eligible
                from .leadership import Leadership
                rules=BusinessRules(self.e)
                for dept in sorted(self.s.get('departments',{}).values(),key=lambda d:d['provider']):
                    if dept['role']!='legal' or b.region not in dept['regions'] or not self.controlled(dept['provider']):continue
                    company=rules.company(dept['provider'])
                    if company.status!='operating':continue
                    staff=[emp for emp in rules.staff(company.id) if rules.position(emp.position_id).role=='legal' and
                           (not dept['staff'] or emp.id in dept['staff']) and Leadership(self.e).available(emp) and eligible(rules,emp)]
                    capacity=sum(emp.weekly_hours*60//max(1,len(emp.days)) for emp in staff)
                    backlog=sum(t['remaining'] for t in self.s.get('service_tasks',[]) if t['provider']==company.id and t['department']=='legal' and t['status'] in ('queued','working'))
                    if capacity and backlog<capacity*5:provider=company.id;break
            return ('service_request',dict(recipient=b.id,department='legal',matter='collection',target_id=invoice['id'],provider=provider,mode='outside' if provider=='outside' else 'internal'),cost,
                    'Request qualified legal collection after ordinary attempts; recovery is uncertain and delivery consumes real staff time and expenses')
        if settings['write_off']:
            return ('write_off_invoice',dict(entity=b.id,invoice_id=invoice['id']),invoice['amount'],
                    'Resolve exhausted customer recovery; further paid collection is uneconomic or has already been attempted. Write off the remaining balance as bad-debt expense, with no cash received')
        return None

    def provider(self,p,kind,prefer_owned):
        if not prefer_owned:return 'outside'
        from .manager_defaults import automation
        owner=next((b for b in self.w.businesses if b.id==p.owner),None)
        if owner and not automation(self.w,owner)['prefer_internal_property']:return 'outside'
        from .internal_property_services import InternalPropertyServices
        office=InternalPropertyServices(self.e).care_provider(p,kind)
        if office:return office
        from .property_services import SERVICES,PropertyServices
        from .business_rules import BusinessRules
        from .specialists import LICENSES
        from .leadership import Leadership
        rules=BusinessRules(self.e);spec=SERVICES[kind]
        for b in sorted(self.w.businesses,key=lambda b:(b.region!=p.region,b.id)):
            if b.industry!=kind or b.status!='operating' or not self.controlled(b.id) or b.equipment<=0:continue
            # Do not queue work behind an overloaded crew simply because it is owned.
            if any(j['provider']==b.id and j['status']=='working' for j in self.s.get('property_service_jobs',[])):continue
            licensed=LICENSES.get(spec['role'])
            staff=[e for e in rules.staff(b.id) if rules.position(e.position_id).role==spec['role']
                   and Leadership(self.e).available(e)
                   and all(not key or rules.person(e.person_id).licenses.get(key,'')>=self.w.date for key in (licensed,rules.position(e.position_id).required_license))]
            needed=PropertyServices(self.e).quote(p,kind,1,b.id)['effort']
            if sum(e.weekly_hours*60//max(1,len(e.days)) for e in staff)<needed+(30 if b.region==p.region else 90):continue
            if self.w.cash(b.id)<needed*spec['supply']:continue
            return b.id
        return 'outside'

    def care(self,leader,b,settings,only_keys=None):
        from .property_services import PropertyServices,care,SERVICES
        for p in self.w.properties:
            if p.owner!=b.id or p.status in ('sold','expired') or p.category=='land':continue
            facts=care(self.w,p)
            for kind,spec in SERVICES.items():
                key='property-care:'+p.id+':'+kind
                if only_keys is not None and key not in only_keys:continue
                jobs=[j for j in self.s.get('property_service_jobs',[]) if j['property_id']==p.id and j['kind']==kind]
                if any(j['status']=='working' for j in jobs):continue
                last=jobs[-1] if jobs else None
                # Cancelling a plan is an intentional stop. A later manually
                # booked plan can restart that service's renewal cycle.
                if last and last['status']=='cancelled':continue
                renew=last and last['status']=='complete' and settings['renew_services']
                interval=last['interval'] if renew else spec['interval']
                if renew and (date.fromisoformat(last['completed'])+timedelta(days=interval)).isoformat()>self.w.date:continue
                need=kind!='security' and facts['cleanliness' if kind=='cleaning' else 'grounds']<settings['care_threshold']
                if not renew and not need:continue
                provider=self.provider(p,kind,settings['prefer_owned'])
                visits=last['visits'] if renew else settings['visits']
                quote=PropertyServices(self.e).quote(p,kind,visits,provider)
                self.perform(leader,b,key,'property_service',
                    dict(property_id=p.id,kind=kind,visits=visits,interval=interval,provider=provider),quote['total'],
                    ('Renew ' if renew else 'Book ')+kind+' at '+p.name+'; '+str(visits)+' funded visits using '+
                    ('outside specialists' if provider=='outside' else leader.rules.company(provider).name)+'.',20)

    def recheck_property_care(self):
        """Retry saved routine proposals using current need, prices and authority."""
        from .leadership import Leadership
        pending=pending_property_care(self.w)
        self.rechecking={(r['business_id'],r['key']) for r in pending}
        leader=Leadership(self.e)
        try:
            for b in self.w.businesses:
                keys={key for bid,key in self.rechecking if bid==b.id}
                if not keys or b.status!='operating' or not self.controlled(b.id) or not leader.actor(b)[1]:continue
                settings=policy(self.w,b)
                if settings['property_care']:self.care(leader,b,settings,only_keys=keys)
        finally:self.rechecking=set()

    def collections(self,leader,b,settings):
        from .customer_collections import overdue,busy
        for invoice in list(b.receivables):
            if not overdue(self.w,invoice) or busy(self.w,b.id,invoice):continue
            proposal=self.collection_proposal(b,invoice,settings)
            if not proposal:continue
            action,args,cost,detail=proposal;detail+=' · '+invoice['id']+'.'
            if action=='write_off_invoice' and cost>settings['write_off_limit']:
                leader.request(b,'collect:'+invoice['id'],action,args,cost,detail+' This exceeds the permitted write-off amount.');continue
            done=self.perform(leader,b,'collect:'+invoice['id'],action,args,cost,detail,10)
            if done:
                # A handled payment exception is a digest item, not a reason to
                # interrupt a skip; unrelated failures still stop it.
                for event in self.e.events:
                    if event['title'] in ('Customer default','Customer collection delayed','Customer recovery needs review') and event.get('invoice_id')==invoice['id']:
                        event['pause_suppressed']=True
                        event['handled_by']=leader.rules.person(leader.actor(b)[1].person_id).name
                        reason=event['title']
                        # Pause reasons carry invoice IDs on new payment events.
                        self.e.pause_reasons[:]=[r for r in self.e.pause_reasons if not (r.get('invoice_id')==invoice['id'] and r['title']==reason)]

    def tick(self):
        from .leadership import Leadership
        leader=Leadership(self.e)
        for b in self.w.businesses:
            if b.status!='operating' or not self.controlled(b.id) or not leader.actor(b)[1]:continue
            settings=policy(self.w,b)
            if settings['collections']:self.collections(leader,b,settings)
            if settings['property_care']:self.care(leader,b,settings)


def assigned_collection(world,b,invoice):
    """Pending routine work belongs to the manager queue, not the player inbox."""
    settings=policy(world,b)
    if not settings['collections']:return False
    from .domain import Engine
    from .leadership import Leadership
    from .manager_defaults import staffed
    leadership=Leadership(Engine(world))
    if staffed(world,b):
        if not manager_limits(b)['enabled']:return False
    elif not leadership.director(b.id,False)[1]:return False
    return bool(RoutineManagement(leadership.e).collection_proposal(b,invoice,settings))


def pending_property_care(world):
    from .property_services import SERVICES
    return [r for r in world.systems.get('management_requests',[])
            if r['status']=='open' and r['action']=='property_service'
            and r['args'].get('kind') in SERVICES
            and r['key']=='property-care:'+r['args'].get('property_id','')+':'+r['args']['kind']]


def ready_property_care(world):
    """Preview the complete queue once, including cumulative costs and workload.

    Reading a screen never books work. Only requests that can actually execute
    under today's policy move out of the player approval count. A daily step
    repeats these checks before advancing the date and committing real work.
    """
    pending=pending_property_care(world)
    if not pending or world.systems.get('campaign_outcome',{}).get('status')=='insolvent':return set()
    import copy
    from .domain import Engine
    engine=Engine(copy.deepcopy(world));engine.simulating=True
    RoutineManagement(engine).recheck_property_care()
    ids={r['id'] for r in pending}
    return {r['id'] for r in engine.world.systems.get('management_requests',[]) if r['id'] in ids and r['status']=='resolved'}
