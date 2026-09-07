"""Prefer real, available internal property specialists for delegated work."""
import copy
from datetime import date
from .campaign import Campaign
from .domain import Engine

REPAIR_ROLES=('maintenance','tradesperson','builder','engineer','electrician','plumber','hvac_technician')


def agent_department(world,b):
    saved=world.systems.get('departments',{}).get(b.id+':real_estate_agent')
    if saved is not None:return saved
    roles={p.id:p.role for p in world.positions}
    if b.industry!='office' or not any(e.employer==b.id and e.status=='active' and roles.get(e.position_id)=='real_estate_agent' for e in world.employments):return None
    # Existing office equipment supports basic work. Paid department tools and
    # explicitly configured coverage remain separate upgrades and restrictions.
    return dict(id=b.id+':real_estate_agent',provider=b.id,role='real_estate_agent',staff=[],tools=0,
                regions=[r['id'] for r in world.systems.get('regions',[])],industries=[b.industry],
                last_capacity=0,last_used=0,last_cost=0,leader='',automatic=True)


def agent_work_minutes(world,provider,recipient,p):
    department=agent_department(world,provider)
    roles={pos.id:pos.role for pos in world.positions};people={person.id:person for person in world.people}
    staff=[emp for emp in world.employments if emp.employer==provider.id and emp.status=='active'
           and roles.get(emp.position_id)=='real_estate_agent' and people[emp.person_id].licenses.get('real_estate','')>=world.date
           and (not department['staff'] or emp.id in department['staff'])]
    quality=sum(people[emp.person_id].skills.get('service',30) for emp in staff)//len(staff) if staff else 30
    expertise=100 if not recipient or recipient.industry in department['industries'] else 65
    speed=max(30,quality)*expertise*(80+department['tools']*20)//10000
    return (960*100+max(1,speed)-1)//max(1,speed)+(300 if provider.region!=p.region else 0)


class InternalPropertyServices(Campaign):
    def providers(self,owner,region):
        return sorted((b for b in self.w.businesses if b.status=='operating' and self.controlled(b.id)
                       and b.equipment>0 and not b.payroll_overdue),
                      key=lambda b:(b.industry!='office',b.id!=owner,b.region!=region,b.id))

    def staff_capacity(self,b,p,roles,license_name=None,qualification=0,department=None):
        from .business_rules import BusinessRules
        from .leadership import Leadership
        from .qualified_capacity import eligible
        if department and p.region not in department['regions']:return [],0
        # Work projections must not accrue payroll, alter morale or enroll staff
        # in the live world. Delivery later consumes the existing named pool.
        trial=Engine(copy.deepcopy(self.w));trial.simulating=True
        rules=BusinessRules(trial);company=rules.company(b.id)
        employees=[emp for emp in rules.staff(b.id) if rules.position(emp.position_id).role in roles
                   and (not department or not department['staff'] or emp.id in department['staff'])
                   and Leadership(trial).available(emp) and eligible(rules,emp,license_name)
                   and rules.person(emp.person_id).skills.get('maintenance',0)>=qualification]
        if not employees:return [],0
        rules.work(company,date.fromisoformat(trial.world.date))
        pool=(self.e.named_capacity[b.id] if getattr(self.e,'named_capacity_dates',{}).get(b.id)==self.w.date else trial.named_capacity[b.id])
        return employees,sum(pool.get(emp.id,0) for emp in employees)

    def repair(self,b,p,system,kind):
        from .property_operations import PropertyOperations
        from .manager_defaults import automation
        from .qualified_capacity import TRADE_LICENSES
        from .authority import labor_allowance,cash_forecast
        quote=PropertyOperations(self.e).quote(p,system,kind)
        fallback=dict(provider='outside',cost=quote['total'],reason='Use an outside contractor; internal preference is disabled.')
        if not automation(self.w,b)['prefer_internal_property']:return fallback
        fallback['reason']='Use an outside contractor; no qualified internal crew can meet the work window with its current workload.'
        for provider in self.providers(b.id,p.region):
            department=self.s.get('departments',{}).get(provider.id+':maintenance')
            # A configured maintenance team limits that team's assignments.
            roles=('maintenance',) if department else REPAIR_ROLES
            employees,capacity=self.staff_capacity(provider,p,roles,TRADE_LICENSES.get(system),quote['qualification'],department)
            travel=30 if provider.region!=p.region else 0
            capacity=max(0,capacity-travel)
            backlog=sum(j['remaining']+travel for j in self.s.get('property_work',[]) if j['provider']==provider.id and j['status']=='working')
            backlog+=sum(t['remaining'] for t in self.s.get('service_tasks',[]) if t['provider']==provider.id
                         and t['department'] in roles and t['status'] in ('queued','working'))
            days=1 if kind=='emergency' else quote['downtime']
            if not employees or backlog+quote['effort']>capacity*days:continue
            if cash_forecast(self.w,provider.id,7)['available']<0:continue
            labor=labor_allowance(self.w,provider.id,roles,quote['effort'])
            return dict(provider=provider.id,cost=quote['materials']+labor,assigned_staff=','.join(emp.id for emp in employees),
                        reason='Use '+provider.name+' internal staff; qualifications, current coverage and queued work fit the repair window. Materials are paid now and actual labor is allocated as delivered.')
        return fallback

    def care_provider(self,p,kind):
        from .property_services import PropertyServices,SERVICES
        if kind not in ('cleaning','landscaping'):return None
        for b in self.providers(p.owner,p.region):
            if b.industry!='office':continue
            department=self.s.get('departments',{}).get(b.id+':maintenance')
            employees,capacity=self.staff_capacity(b,p,('maintenance',),qualification=40,department=department)
            needed=PropertyServices(self.e).quote(p,kind,1,b.id)['effort']
            journey=30 if b.region==p.region else 90
            backlog=sum(j['remaining']+journey for j in self.s.get('property_work',[]) if j['provider']==b.id and j['status']=='working')
            backlog+=sum(j['remaining']+journey for j in self.s.get('property_service_jobs',[]) if j['provider']==b.id and j['status']=='working')
            backlog+=sum(t['remaining'] for t in self.s.get('service_tasks',[]) if t['provider']==b.id and t['department']=='maintenance' and t['status'] in ('queued','working'))
            if employees and backlog+needed+journey<=capacity*2 and self.w.cash(b.id)>=needed*SERVICES[kind]['supply']:
                return b.id
        return None

    def agent(self,b,p):
        from .authority import cash_forecast,labor_allowance
        for provider in self.providers(b.id,p.region):
            department=agent_department(self.w,provider)
            if not department:continue
            employees,capacity=self.staff_capacity(provider,p,('real_estate_agent',),'real_estate',department=department)
            travel=30 if provider.region!=p.region else 0
            if not employees or capacity<=travel:continue
            people={person.id:person for person in self.w.people}
            quality=sum(people[emp.person_id].skills.get('service',30) for emp in employees)//len(employees)
            expertise=100 if b.industry in department['industries'] else 65
            speed=max(30,quality)*expertise*(80+department['tools']*20)//10000
            daily=(capacity-travel)*speed//100
            backlog=sum(t['remaining'] for t in self.s.get('service_tasks',[]) if t['provider']==provider.id
                        and t['department']=='real_estate_agent' and t['status'] in ('queued','working'))
            if daily<=0 or backlog+960>daily*10:continue
            if cash_forecast(self.w,provider.id,14)['available']<0:continue
            minutes=agent_work_minutes(self.w,provider,b,p)
            # Fully burdened rates include a cushion; this is a commitment, not
            # a made-up cash charge. Office payroll still accrues only once.
            return dict(provider=provider.id,cost=labor_allowance(self.w,provider.id,('real_estate_agent',),minutes,1),
                        calendar_days=((backlog+960+daily-1)//daily+1)*7//5+2)
        return None

    def prepare_closing(self,b,p,leader,limit):
        from .manager_defaults import automation
        from .property_development import representation
        if not automation(self.w,b)['prefer_internal_property'] or representation(self.w,p,b.id):return True
        tasks=[t for t in self.s.get('service_tasks',[]) if t.get('product')=='property_representation'
               and t['recipient']==b.id and t['target_id']==p.id]
        if any(t['status'] in ('queued','working') for t in tasks):return False
        # Cancelling explicitly chooses the ordinary outside closing route.
        if tasks and tasks[-1]['status']=='cancelled':return True
        proposal=self.agent(b,p)
        if not proposal:return True
        listing=self.s.get('property_listings',{}).get(p.id,{})
        if listing.get('status')=='closing' and (date.fromisoformat(listing['due'])-date.fromisoformat(self.w.date)).days<proposal['calendar_days']:
            return True # Do not buy preparation that cannot precede an agreed closing.
        provider=next(x for x in self.w.businesses if x.id==proposal['provider'])
        leader.perform(b,'agent:'+p.id,'service_request',dict(recipient=b.id,provider=provider.id,
            department='real_estate_agent',product='property_representation',mode='internal',target_id=p.id,days=30),
            proposal['cost'],proposal['cost']<=limit,
            'Assign '+provider.name+' to prepare closing for '+p.name+'. The transaction waits for completed licensed work; brokerage falls only when that work is used at closing.')
        return False
