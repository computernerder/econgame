"""Concurrent contracts share one finite pool of qualified work or shipments."""
import copy
from datetime import date, timedelta
from .domain import Engine, RuleError


def jobs(b):
    primary = [dict(number=b.project_number, fee=b.contract_fee, minutes=b.contract_minutes,
                    progress=b.project_progress, earned=b.project_earned)] if b.project_active else []
    return primary + [dict(j) for j in b.parallel_projects]


def remaining(b):
    return sum(j['minutes']-j['progress'] for j in jobs(b))


def project_minutes(b, qualified):
    available = max(0, qualified - (min(60, qualified) if b.retainer else 0))
    return available - (min(240, available//3) if b.hourly_rate else 0)


def planning_capacity(world, b, kit_key=None):
    """Five upcoming weekdays; absences, qualifications and shared staff apply."""
    from .business_rules import BusinessRules
    from .industry_operations import IndustryOperations
    from .industries import project_capacity
    from .distress import Distress
    total = 0
    for offset in range(1, 8):
        day = date.fromisoformat(world.date) + timedelta(days=offset)
        if day.weekday() >= 5:continue
        clone = copy.deepcopy(world);clone.date = day.isoformat()
        for emp in clone.employments:
            if emp.status == 'joining' and emp.start_date <= clone.date:emp.status = 'active'
        e = Engine(clone);rules = BusinessRules(e);company = rules.company(b.id)
        buckets, management = rules.work(company, day)
        operations = IndustryOperations(e);operations.before(company, buckets)
        minutes = {role:sum(values) for role,values in buckets.items()}
        distress = Distress(e).capacity(company)
        from .revenue_kits import state,capacity as kit_capacity,CATALOG
        if state(world,b):
            budgets=kit_capacity(rules,company,buckets,management)
            total+=budgets.get(kit_key,0) if kit_key else sum(v for key,v in budgets.items() if CATALOG[b.industry][key]['kind']=='project')
        elif b.industry == 'factory':
            qualified = min(minutes.get('machine_operator',0), minutes.get('production_worker',0)*2)
            units = qualified*b.capacity_percent*distress//300000
            demand = max(1,b.daily_demand or 10)*operations.demand_factor(company)//100
            total += min(units,demand)*60
        else:
            qualified = project_capacity(b.industry,minutes)*management*min(120,b.capacity_percent)//10000
            total += project_minutes(b, qualified*distress//100)
    return total//5


def acceptance_reason(world,b,offer,capacity=None):
    if offer.get('blocked'):return offer['blocked']
    from .revenue_kits import state,tag
    if state(world,b):
        per_stream=planning_capacity(world,b,offer['kit'])
        pending=sum(j['minutes']-j['progress'] for j in jobs(b) if tag(world,b,j['number'])['kit']==offer['kit'])
        if pending+offer['minutes']>per_stream*b.project_planning_days:
            return 'This stream needs more qualified hours, a larger work share or a longer planning window before accepting another contract.'
        from .authority import cash_forecast
        material_commitment=(offer['minutes']*offer.get('materials',0)+59)//60
        if cash_forecast(world,b.id,30)['available']<material_commitment:
            return 'Known obligations and this contract require more material and operating cash. Fund the business before accepting.'
    if len(jobs(b)) >= b.concurrent_project_limit:
        return 'The concurrent project limit is reached. Finish work or increase the limit.'
    if jobs(b):
        capacity = planning_capacity(world,b) if capacity is None else capacity
        needed = remaining(b)+offer['minutes']
        if needed > capacity*b.project_planning_days:
            return f'Insufficient qualified capacity for another job: {needed/60:.1f} hours of combined work versus {capacity*b.project_planning_days/60:.1f} hours over {b.project_planning_days} working days. Add qualified staff, adjust schedules or complete more work.'
    return ''


def autofill(rules,b,capacity):
    from .engineering import next_offer
    from .leadership import Leadership
    if not b.auto_projects or capacity <= 0:return
    # Recheck actual daily capacity after every addition. Required approvals stay
    # in the inbox and stop this loop before any unauthorized contract is taken.
    while len(jobs(b)) < b.concurrent_project_limit:
        from .revenue_kits import state,project_choices
        if state(rules.w,b):
            # An unavailable specialty (for example an expired stamping license)
            # must not stop a different, staffed line of work. Authority refusals
            # still stop acceptance; do not shop around an approval requirement.
            keys=project_choices(rules.w,b)
            first=next_offer(rules.w,b).get('kit')
            if first in keys:keys=[first]+[key for key in keys if key!=first]
            eligible=next((key for key in keys if not acceptance_reason(rules.w,b,next_offer(rules.w,b,key),capacity)),None)
            if not eligible or not Leadership(rules.e).accept_project(b,eligible):break
        else:
            if acceptance_reason(rules.w,b,next_offer(rules.w,b),capacity):break
            if jobs(b) and acceptance_reason(rules.w,b,next_offer(rules.w,b)):break
            if not Leadership(rules.e).accept_project(b):break


def deliver(rules,b,budget,income='project_work',days=14,selected_numbers=None):
    active = jobs(b)
    selected=lambda j:selected_numbers is None or j['number'] in selected_numbers
    total = sum(j['minutes']-j['progress'] for j in active if selected(j))
    budget = min(max(0,budget),total)
    if not budget:return 0,0,[]
    # Proportional allocation, with stable integer rounding; no minute is reused.
    allocations = [budget*(j['minutes']-j['progress'])//total if selected(j) else 0 for j in active]
    spare = budget-sum(allocations)
    for i,j in enumerate(active):
        if spare and selected(j) and allocations[i]<j['minutes']-j['progress']:
            allocations[i]+=1;spare-=1
    earned_total=0;survivors=[];work=[]
    for j,minutes in zip(active,allocations):
        j['progress']+=minutes
        earned=j['fee']*j['progress']//j['minutes']-j['earned'];j['earned']+=earned
        earned_total+=earned
        if earned:
            rules.e.post(b.id,f'project_earned:{b.id}:{j["number"]}:{rules.w.date}',
                'Fixed-fee project work earned' if income=='project_work' else 'Manufactured order earned through shipment',
                {'asset:unbilled':earned,'income:'+income:-earned})
        work.append(dict(number=j['number'],minutes=minutes,earned=earned))
        if j['progress']==j['minutes']:
            source=f'project_invoice:{b.id}:{j["number"]}'
            due=(date.fromisoformat(rules.w.date)+timedelta(days=days)).isoformat()
            rules.e.post(b.id,source,'Completed project invoiced' if days==14 else 'Completed manufacturing order invoiced',
                {'asset:unbilled':-j['fee'],'asset:receivable':j['fee']})
            b.receivables.append(dict(id=source,amount=j['fee'],due=due))
            b.project_history.append(dict(number=j['number'],fee=j['fee'],minutes=j['minutes'],completed=rules.w.date,due=due,invoice_id=source,stream=income))
            b.project_history=b.project_history[-30:]
            rules.e.event(b.industry.title()+' project completed',f'{b.name}: job {j["number"]} invoiced for ${j["fee"]/100:,.2f}. Collection in {days} days.',not b.auto_projects,financial_amount=j['fee'])
        else:survivors.append(j)
    if survivors:
        first=survivors.pop(0)
    else:first=active[-1]
    b.project_number=first['number'];b.contract_fee=first['fee'];b.contract_minutes=first['minutes']
    b.project_progress=first['progress'];b.project_earned=first['earned']
    b.project_active=first['progress']<first['minutes'];b.parallel_projects=survivors
    return budget,earned_total,work


def validate(b,accounts):
    active=jobs(b)
    if not 5<=b.project_planning_days<=120:raise RuleError('Project planning window must be 5–120 working days.')
    if not 1<=b.concurrent_project_limit<=10:raise RuleError('Concurrent project limit must be 1–10.')
    if b.parallel_projects and not b.project_active:raise RuleError('Active project queue has no lead contract.')
    if len({j['number'] for j in active})!=len(active):raise RuleError('Duplicate active project number.')
    for j in active:
        if not 0<=j['progress']<j['minutes'] or j['fee']<=0 or not 0<=j['earned']<=j['fee']:
            raise RuleError('Invalid active project work or fee.')
    if accounts.get('asset:unbilled',0)!=sum(j['earned'] for j in active):raise RuleError('Active project earnings do not reconcile.')
