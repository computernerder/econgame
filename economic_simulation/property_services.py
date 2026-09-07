"""Property care consumes real worker capacity, supplies and prepaid commitments."""
from datetime import date,timedelta
from .campaign import Campaign,integer
from .domain import RuleError
from .simulation_support import stable_roll

SERVICES={
    'cleaning':dict(role='cleaner',skill='service',minutes=120,rate=120,supply=12,interval=7),
    'landscaping':dict(role='gardener',skill='maintenance',minutes=180,rate=150,supply=25,interval=14),
    'security':dict(role='security_guard',skill='service',minutes=120,rate=160,supply=8,interval=2)}


def care(world,p):
    return world.systems.get('property_care',{}).get(p.id,dict(cleanliness=70,grounds=70,patrols=[],last_day=''))


def presentation(world,p):
    facts=care(world,p)
    return 90+(facts['cleanliness']+facts['grounds'])//14


def protection(world,p):
    cutoff=(date.fromisoformat(world.date)-timedelta(days=7)).isoformat()
    region=next(r for r in world.systems['regions'] if r['id']==p.region)
    return min(max(0,region['crime']//4-1),6,2*len({d for d in care(world,p)['patrols'] if cutoff<=d<=world.date}))


class PropertyServices(Campaign):
    def initialize(self):
        for p in self.w.properties:
            if p.owner:self.s.setdefault('property_care',{}).setdefault(p.id,care(self.w,p))

    def quote(self,p,kind,visits,provider='outside'):
        spec=SERVICES[kind]
        from .real_estate import area
        effort=spec['minutes']*max(1,min(6,(area(p)+599)//600))
        rate=spec['rate'] if provider=='outside' else spec['rate']*80//100
        return dict(effort=effort,rate=rate,total=effort*visits*rate)

    def action(self,action,args,source):
        if action=='cancel_property_service':
            job=next((j for j in self.s.get('property_service_jobs',[]) if j['id']==args.get('job_id') and j['status']=='working'),None)
            if not job:raise RuleError('Choose unfinished property service work.')
            self.require(job['owner']);return self.cancel(job,source,'Cancelled by the owner.')
        p=self.e.get_property(args.get('property_id',''));self.require(p.owner)
        if p.status in ('sold','expired'):raise RuleError('Choose a current owned property.')
        kind=args.get('kind','cleaning')
        if kind not in SERVICES:raise RuleError('Choose cleaning, landscaping or security.')
        provider=args.get('provider','outside')
        if provider!='outside':
            from .business_rules import BusinessRules
            b=BusinessRules(self.e).company(provider)
            office_care=b.industry=='office' and kind in ('cleaning','landscaping')
            if (b.industry!=kind and not office_care) or b.status!='operating':raise RuleError('Choose an operating service provider or a home office for basic cleaning and grounds care.')
        if any(j['property_id']==p.id and j['kind']==kind and j['status']=='working' for j in self.s.get('property_service_jobs',[])):
            raise RuleError('This property already has unfinished work for this service. Cancel it before replacing the plan.')
        visits=integer(args.get('visits',4),1,20);interval=integer(args.get('interval',SERVICES[kind]['interval']),1,30)
        quote=self.quote(p,kind,visits,provider)
        self.e.post(p.owner,source,'Reserve complete property service plan',{'asset:cash':-quote['total'],'asset:prepaid_property_services':quote['total']})
        job=dict(id=self.uid('property-service'),property_id=p.id,owner=p.owner,provider=provider,kind=kind,
            visits=visits,completed_visits=0,effort=quote['effort'],remaining=quote['effort'],rate=quote['rate'],
            prepaid=quote['total'],paid=quote['total'],expense=0,refunded=0,worked=0,travel=0,supplies=0,
            interval=interval,next_visit=self.w.date,created=self.w.date,
            due=(date.fromisoformat(self.w.date)+timedelta(days=(visits-1)*interval+14)).isoformat(),
            priority=integer(args.get('priority',2),1,5),status='working',outcome='Awaiting scheduled capacity.',last_day='')
        self.s.setdefault('property_service_jobs',[]).append(job)
        return f'{visits} '+('visit' if visits==1 else 'visits')+f' reserved for ${quote["total"]/100:,.2f}; {quote["effort"]/60:g} qualified hours per visit. First visit can start on the next staffed weekday. The business manager can renew under the routine-care policy; personal-property plans remain manual.'

    def cancel(self,job,source,reason):
        refund=job['prepaid']
        if refund:self.e.post(job['owner'],source,'Undelivered property services refunded',{'asset:prepaid_property_services':-refund,'asset:cash':refund})
        job.update(prepaid=0,refunded=job['refunded']+refund,status='cancelled',outcome=reason+f' ${refund/100:,.2f} unused reserve returned; delivered work remains an expense.')
        return job['outcome']

    def valid(self,job):
        p=self.e.get_property(job['property_id'])
        b=next((b for b in self.w.businesses if b.id==job['provider']),None)
        if p.owner!=job['owner'] or p.status in ('sold','expired') or (job['provider']!='outside' and (not b or not self.controlled(b.id) or b.status!='operating')):
            self.cancel(job,job['id']+':ended','Ownership or provider availability changed.');return False
        return True

    def ready(self,job):
        return job['status']=='working' and job['next_visit']<=self.w.date and job['last_day']!=self.w.date and self.valid(job)

    def weather(self,region):
        return stable_roll(self.w,'grounds-weather:'+region+':'+self.w.date)<20

    def progress(self,job,minutes,quality):
        cost=minutes*job['rate'];job['prepaid']-=cost;job['expense']+=cost;job['worked']+=minutes;job['remaining']-=minutes;job['last_day']=self.w.date
        provider=job['provider'];key='expense:outside_property_services' if provider=='outside' else 'expense:internal_property_services:'+provider
        self.e.post(job['owner'],job['id']+':'+self.w.date,'Property service delivered',{'asset:prepaid_property_services':-cost,key:cost})
        if provider!='outside':
            self.e.post(provider,job['id']+':'+self.w.date,'Internal property service payment released',{'asset:cash':cost,'income:internal_property_services:'+job['owner']:-cost})
        self.s.setdefault('property_service_costs',{})[job['property_id']]=self.s.get('property_service_costs',{}).get(job['property_id'],0)+cost
        totals=self.s.setdefault('property_cost_totals',{}).setdefault(job['property_id'],dict(holding=0,interest=0,repairs=0))
        totals['services']=totals.get('services',0)+cost
        job['outcome']=f'{job["worked"]/60:g} qualified hours delivered; {job["completed_visits"]}/{job["visits"]} visits completed.'
        if job['remaining']:return
        p=self.e.get_property(job['property_id']);facts=self.s.setdefault('property_care',{}).setdefault(p.id,care(self.w,p))
        if job['kind']=='security':facts['patrols'].append(self.w.date)
        else:
            key='cleanliness' if job['kind']=='cleaning' else 'grounds'
            facts[key]=min(100,facts[key]+max(5,quality//3))
        job['completed_visits']+=1
        job['outcome']=f'{job["kind"].title()} visit completed at {quality}/100 workmanship. {job["completed_visits"]}/{job["visits"]} visits delivered; ${job["expense"]/100:,.2f} actual service expense.'
        if job['completed_visits']==job['visits']:
            job.update(status='complete',completed=self.w.date)
            self.e.event('Property service plan completed',p.name+': '+job['outcome'])
        else:
            job['remaining']=job['effort'];job['next_visit']=(date.fromisoformat(self.w.date)+timedelta(days=job['interval'])).isoformat()

    def operate(self,rules,b,buckets,management,open_day):
        from .industry_operations import IndustryOperations
        from .economy import Economy
        from .distress import Distress
        spec=SERVICES[b.industry];role=spec['role'];values=buckets[role]
        state=IndustryOperations(self.e).state(b)
        capacity=min(sum(values),b.equipment*b.capacity_percent//200000)*management*state['equipment_condition']*Distress(self.e).capacity(b)//1000000 if open_day else 0
        if b.industry=='landscaping' and self.weather(b.region):capacity=0
        remaining=capacity;internal=travel=supplies=0
        staff=[emp for emp in rules.staff(b.id) if rules.position(emp.position_id).role==role]
        quality=sum(rules.person(emp.person_id).skills.get(spec['skill'],30) for emp in staff)//max(1,len(staff))
        for job in sorted(self.s.get('property_service_jobs',[]),key=lambda j:(j['priority'],j['due'],j['id'])):
            if job['provider']!=b.id or not self.ready(job):continue
            p=self.e.get_property(job['property_id'])
            if b.industry=='landscaping' and self.weather(p.region):continue
            journey=30 if p.region==b.region else 90
            used=min(max(0,remaining-journey),job['remaining'],self.w.cash(b.id)//spec['supply'])
            if not used:continue
            cost=used*spec['supply']
            self.e.post(b.id,job['id']+':supplies:'+self.w.date,'Property service supplies consumed',{'asset:cash':-cost,'expense:property_service_supplies':cost})
            job['supplies']+=cost;job['travel']+=journey
            self.progress(job,used,quality);remaining-=used+journey;internal+=used;travel+=journey;supplies+=cost
        # Outside customers receive only the remaining equipment and staffed time.
        demand=b.daily_demand*Economy(self.e).demand_factor(b)*IndustryOperations(self.e).demand_factor(b)//10000
        demand=demand*max(25,200-b.price_percent)//100 if open_day else 0
        if b.industry=='landscaping' and date.fromisoformat(self.w.date).month in (12,1,2):demand//=2
        external=min(remaining,demand,self.w.cash(b.id)//spec['supply']);cost=external*spec['supply']
        if external:
            self.e.post(b.id,'care-supplies:'+b.id+':'+self.w.date,'Outside customer supplies consumed',{'asset:cash':-cost,'expense:property_service_supplies':cost})
            rules.invoice(b,external*spec['rate']*b.price_percent//100,'property_services','care-invoice:'+b.id+':'+self.w.date,14)
        used=internal+external+travel
        for hour in range(24):take=min(used,values[hour]);values[hour]-=take;used-=take
        result=dict(output=internal+external,unit='qualified service minutes',demand=demand,capacity=capacity,
            internal_minutes=internal,external_minutes=external,travel_minutes=travel,supplies=cost+supplies,
            unused_capacity=max(0,remaining-external),bottleneck='Staff, equipment condition, travel and supply cash; outside invoices collect after 14 days.' if capacity else 'No capacity today: check schedules, licenses, equipment, distress or landscaping weather.')
        IndustryOperations(self.e).customer_feedback(b,dict(demand=demand,output=external))
        return result

    def deliver_home_office(self,rules,b,buckets):
        if b.industry!='office' or b.status!='operating' or b.equipment<=0:return
        from .qualified_capacity import eligible,capacities,consume
        department=self.s.get('departments',{}).get(b.id+':maintenance')
        staff=[emp for emp in rules.staff(b.id) if rules.position(emp.position_id).role=='maintenance'
               and eligible(rules,emp) and rules.person(emp.person_id).skills.get('maintenance',0)>=40
               and (not department or not department['staff'] or emp.id in department['staff'])]
        for job in sorted(self.s.get('property_service_jobs',[]),key=lambda j:(j['priority'],j['due'],j['id'])):
            if job['provider']!=b.id or job['kind'] not in ('cleaning','landscaping') or not self.ready(job):continue
            p=self.e.get_property(job['property_id'])
            if department and p.region not in department['regions']:continue
            if job['kind']=='landscaping' and self.weather(p.region):continue
            journey=30 if p.region==b.region else 90;spec=SERVICES[job['kind']]
            capacity=sum(capacities(rules,b,buckets,staff).values())
            effort=min(job['remaining'],max(0,capacity-journey),self.w.cash(b.id)//spec['supply'])
            if not effort:continue
            used,labor,names,quality=consume(rules,b,buckets,staff,effort+journey)
            if used<=journey:continue
            effort=used-journey;supplies=effort*spec['supply']
            self.e.post(b.id,job['id']+':supplies:'+self.w.date,'Home-office property care supplies',{'asset:cash':-supplies,'expense:property_service_supplies':supplies})
            job['supplies']+=supplies;job['travel']+=journey
            job['labor_cost']=job.get('labor_cost',0)+labor
            job['staff']=sorted(set(job.get('staff',[]))|set(names))
            self.progress(job,effort,quality)

    def tick(self):
        self.initialize();today=date.fromisoformat(self.w.date)
        for job in self.s.get('property_service_jobs',[]):
            if job['status']!='working' or not self.valid(job):continue
            if job['provider']=='outside' and today.weekday()<5 and self.ready(job):
                p=self.e.get_property(job['property_id'])
                if job['kind']!='landscaping' or not self.weather(p.region):self.progress(job,min(240,job['remaining']),75)
            if job['status']=='working' and job['due']<self.w.date and not job.get('warned'):
                job['warned']=True
                self.e.event('Property service deadline missed',job['id']+': '+str(job['visits']-job['completed_visits'])+' visits remain. Add capacity or cancel undelivered work.',True)
        for p in self.w.properties:
            if not p.owner or p.status in ('sold','expired'):continue
            facts=self.s['property_care'][p.id]
            if facts['last_day']==self.w.date:continue
            facts['last_day']=self.w.date
            facts['cleanliness']=max(0,facts['cleanliness']-(1 if p.status in ('occupied','rented','managed') else int(today.day%3==0)))
            facts['grounds']=max(0,facts['grounds']-int(today.day%3==0))
            cutoff=(today-timedelta(days=30)).isoformat();facts['patrols']=[d for d in facts['patrols'] if d>=cutoff]
            if today.day==1:
                from .economy import Economy
                risk=max(1,Economy(self.e).region(p.region)['crime']//4-protection(self.w,p))
                if stable_roll(self.w,'property-incident:'+p.id+':'+self.w.date)<risk:
                    charge=10000+stable_roll(self.w,p.id+':damage:'+self.w.date,20001)
                    self.e.post(p.owner,'property-incident:'+p.id+':'+self.w.date,'Recorded property vandalism cleanup',{'expense:property_incident':charge,'liability:payable':-charge})
                    totals=self.s.setdefault('property_cost_totals',{}).setdefault(p.id,dict(holding=0,interest=0,repairs=0))
                    totals['incidents']=totals.get('incidents',0)+charge
                    facts['grounds']=max(0,facts['grounds']-15)
                    self.e.event('Property vandalism recorded',p.name+f': ${charge/100:,.2f} cleanup payable. Patrol coverage reduces risk but cannot prevent every incident.',self.controlled(p.owner),financial_amount=charge)
