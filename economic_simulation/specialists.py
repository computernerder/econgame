"""Specialist work has finite, dated service capacity and visible operating benefits."""
from datetime import date,timedelta
from .campaign import Campaign
from .domain import RuleError
from .business_models import SUPPORT_ROLES

PURPOSES={
 'hr':'HR covers 15 qualified minutes per employee/day: up to +2 morale and +1 loyalty/day. Each hire uses 60 banked HR minutes instead of paying $300 for outside hiring support. HR payroll and separately ordered recruiting campaigns still cost money.',
 'it':'IT covers 15 qualified minutes per employee/day (minimum one hour): up to 10% more productive capacity from the same staffed hours.',
 'accounting':'Bank 120 qualified minutes to prepare a dated management report: 30-day revenue, margin, expenses, working capital and cash runway. Basic account balances remain available.',
 'legal':'Bank 20 qualified hours to negotiate one existing acquisition offer. Seller willingness and legal skill determine acceptance; a concession is not current cash. Requires a valid legal-practice license.',
 'logistics':'Two qualified coordinator hours/day reduce outside freight quotes and a carrier’s fuel costs by up to 20%. Fleet capacity is still finite.',
 'purchasing':'Two qualified hours/day reduce supplier/admin overhead by up to 20% and earn up to 5% supplier rebates on goods sold or project materials consumed. Most useful in high-volume operations.',
 'marketing':'Four qualified hours/day generate up to 15% extra customer demand in sales businesses and freight companies. Staff and inventory must still fulfill demand.'}
LICENSES={'legal':'legal_practice','accounting':'accounting','security_guard':'security_guard','real_estate_agent':'real_estate','electrician':'electrical','plumber':'plumbing','hvac_technician':'hvac'}


def pool(world,bid):
    cutoff=(date.fromisoformat(world.date)-timedelta(days=29)).isoformat()
    return [r for r in world.systems.get('specialist_work',{}).get(bid,[]) if cutoff<=r['date']<=world.date]


def available(world,bid,role):return sum(r['remaining'].get(role,0) for r in pool(world,bid))


def consume(world,bid,role,minutes):
    if available(world,bid,role)<minutes:raise RuleError(f'Needs {minutes/60:g} qualified {role} work hours banked within the last 30 days. Hire or assign a specialist and advance working days.')
    for row in pool(world,bid):
        used=min(minutes,row['remaining'].get(role,0));row['remaining'][role]=row['remaining'].get(role,0)-used;minutes-=used
        if not minutes:break


def recruitment_quote(world,bid):
    """Quote hiring administration using work already delivered to this business.

    Local and assigned HR contribute to the same finite, dated pool. Merely
    employing HR elsewhere in the group does not create free service capacity.
    """
    minutes=available(world,bid,'hr')
    internal=minutes>=60
    explanation=(
        'Internal HR handles this hire using 60 minutes of completed HR work. '
        'No outside recruitment fee; HR payroll remains an operating cost.'
        if internal else
        f'Outside hiring support costs $300: this business has {minutes:g} of the 60 HR minutes needed. '
        'Assign HR time to this business and advance working days to build capacity.'
    )
    return dict(fee=0 if internal else 30000,hr_minutes=60 if internal else 0,
                available_minutes=minutes,explanation=explanation)


def recruitment_fee(world,bid):return recruitment_quote(world,bid)['fee']


def apply(rules,b,buckets):
    w=rules.w
    minutes={role:sum(buckets.get(role,[])) for role in SUPPORT_ROLES}
    staff=rules.staff(b.id);need=max(60,len(staff)*15)
    result=dict(minutes=minutes,hr_percent=min(100,minutes['hr']*100//need),it_percent=min(10,minutes['it']*10//need),purchasing_percent=min(20,minutes['purchasing']*20//120),logistics_percent=min(20,minutes['logistics']*20//120),marketing_percent=min(15,minutes['marketing']*15//240))
    for role,effect in w.systems.get('service_effects',{}).get(b.id,{}).items():
        if effect['expires']<w.date:continue
        key={'hr':'hr_percent','it':'it_percent','purchasing':'purchasing_percent','logistics':'logistics_percent','marketing':'marketing_percent'}.get(role)
        if key:
            cap={'hr':100,'it':10,'purchasing':20,'logistics':20,'marketing':15}[role]
            result[key]=min(cap,max(result[key],effect['quality']*cap//100))
    records=w.systems.setdefault('specialist_work',{});records[b.id]=pool(w,b.id)
    if not any(r['date']==w.date for r in records[b.id]):
        remaining={role:min(minutes[role],max(0,4800-available(w,b.id,role))) for role in ('hr','legal','accounting')}
        records[b.id].append(dict(date=w.date,remaining=remaining,worked=minutes))
        for emp in staff:
            if b.payroll_overdue:continue
            person=rules.person(emp.person_id)
            person.morale=min(100,person.morale+result['hr_percent']*2//100)
            person.loyalty=min(100,person.loyalty+result['hr_percent']//100)
    for role,values in buckets.items():
        if role not in SUPPORT_ROLES:
            buckets[role]=[v*(100+result['it_percent'])//100 for v in values]
    return result


def view(world,b):
    last=b.last_day.get('specialists',{})
    positions={p.id:p for p in world.positions}
    payroll=sum(e.salary for e in world.employments if e.employer==b.id and e.status in ('active','joining') and positions[e.position_id].role in SUPPORT_ROLES)
    shared=sum(a.get('last_cost',0) for a in world.systems['assignments'] if a['active'] and a['target']==b.id and a['role'] in SUPPORT_ROLES)
    return dict(base_payroll=payroll,shared_cost=shared,date=b.last_day.get('date'),roles=[dict(role=role,label=role.upper() if role in ('hr','it') else role.title(),purpose=purpose,minutes=last.get('minutes',{}).get(role,0),banked=available(world,b.id,role)) for role,purpose in PURPOSES.items()],effects=last,reports=[r for r in world.systems.get('management_reports',[]) if r['business_id']==b.id][-3:])


class Specialists(Campaign):
    def action(self,action,args):
        from .business_rules import BusinessRules
        rules=BusinessRules(self.e);business=rules.company(args.get('business_id',''))
        if action=='specialist_report':
            consume(self.w,business.id,'accounting',120)
            cutoff=(date.fromisoformat(self.w.date)-timedelta(days=29)).isoformat()
            values={}
            for day,accounts in business.financial_days.items():
                if cutoff<=day<=self.w.date:
                    for key,value in accounts.items():values[key]=values.get(key,0)+value
            revenue=-sum(v for k,v in values.items() if k.startswith('income:'))
            expenses=sum(v for k,v in values.items() if k.startswith('expense:'))
            accounts=self.w.accounts[business.id]
            report=dict(id=self.uid('management-report'),business_id=business.id,name=business.name,date=self.w.date,from_date=cutoff,revenue=revenue,expenses=expenses,profit=revenue-expenses,margin=round((revenue-expenses)*100/revenue,1) if revenue else None,cash=self.w.cash(business.id),receivables=accounts.get('asset:receivable',0)+accounts.get('asset:unbilled',0),payroll=-accounts.get('liability:payroll',0),inventory=accounts.get('asset:inventory',0),runway=round(self.w.cash(business.id)*30/expenses,1) if expenses>0 else None)
            records=self.s.setdefault('management_reports',[]);records.append(report)
            same=[r for r in records if r['business_id']==business.id]
            for old in same[:-12]:records.remove(old)
            self.e.event('Accounting report prepared',business.name+' has a new 30-day management report in Shared services. Two qualified accounting hours were used.')
            return 'Management report prepared. View the dated report in Shared services; account balances and prior reports are unchanged.'
        if action=='negotiate_acquisition':
            target=rules.company(args.get('target_id',''),owned=False)
            if target.owner or target.status!='market' or target.market_parent:raise RuleError('Choose an available standalone business or whole group listing.')
            if target.id in self.s.get('negotiated_acquisitions',{}):raise RuleError('This listing has already been negotiated.')
            quote=rules.quote(target.id);discount=min(target.asking*5//100,2500000,max(0,quote['goodwill']))
            if not discount:raise RuleError('This listing has no negotiable goodwill above its included net assets.')
            consume(self.w,business.id,'legal',1200)
            from .service_office import ServiceOffice
            staff=[e for e in rules.staff(business.id) if rules.position(e.position_id).role=='legal']
            quality=sum(rules.person(e.person_id).skills.get('legal',30) for e in staff)//len(staff) if staff else 60
            task=dict(id=self.uid('legal-work'),provider=business.id,recipient=business.id,department='legal',mode='internal',priority=2,effort=1200,remaining=0,due=self.w.date,created=self.w.date,completed=self.w.date,status='complete',outcome='',target_id=target.id,matter='negotiation',original_offer=target.asking,staff=[e.id for e in staff],worked=1200,internal_cost=0,outside_cost=0,recovered=0,improvement=0)
            ServiceOffice(self.e).legal_result(task,quality)
            self.s.setdefault('service_tasks',[]).append(task)
            self.s.setdefault('negotiated_acquisitions',{})[target.id]=dict(adviser=business.id,date=self.w.date,discount=task['improvement'])
            self.e.event('Acquisition negotiation completed',task['outcome'])
            return task['outcome']
        raise RuleError('Choose an available specialist service.')
