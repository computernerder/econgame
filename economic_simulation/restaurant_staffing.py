"""Meal-time workforce planning, shared-time-aware forecasts and staggered rotas."""
import copy
import math
from datetime import date,timedelta
from itertools import combinations
from urllib.parse import urlencode
from .restaurant import ROLES,MINUTES,PURPOSES,DAY_NAMES,settings,targets,expected,hour_demands,capacity
from .business_models import ROLE_PAY,INDUSTRY_ROLES,OPENING_ROLES
from .business_rules import BusinessRules
from .domain import Engine,RuleError


def role_gaps(world,b):
    positions={p.id:p for p in world.positions};goal=targets(world,b)
    for emp in world.employments:
        if emp.employer==b.id and emp.status in ('active','joining'):
            role=positions[emp.position_id].role
            if role in goal:goal[role]-=emp.weekly_hours
    for a in world.systems.get('assignments',[]):
        if not a['active']:continue
        emp=next((e for e in world.employments if e.id==a['employment_id'] and e.status in ('active','joining')),None)
        if not emp:continue
        if a['target']==b.id and a['role'] in goal:goal[a['role']]-=(a['minutes']-a['travel'])*len(emp.days)/60
        if a['source']==b.id and positions[emp.position_id].role in goal:goal[positions[emp.position_id].role]+=a['minutes']*len(emp.days)/60
    return goal


def hiring_role(world,b):
    gaps=role_gaps(world,b)
    return max((role for role in ROLES if gaps[role]>0),key=lambda role:gaps[role],default=None)


def suggestions(world,b):
    """Greedy per-role coverage; retain hours, pay, shared commitments and pinned shifts."""
    rules=BusinessRules(Engine(world));plan=settings(world,b)
    members=[e for e in world.employments if e.employer==b.id and e.status in ('active','joining') and rules.position(e.position_id).role in ROLES]
    locked=set(plan['manual_staff'])
    locked.update(a['employment_id'] for a in world.systems.get('assignments',[]) if a['active'])
    locked.update(r['employment_id'] for r in world.systems.get('directors',[]) if r['active'])
    locked.update(r['employment_id'] for r in world.systems.get('executives',{}).values() if r['active'])
    today=date.fromisoformat(world.date);goal={};coverage={r:[[0.0]*24 for _ in range(7)] for r in ROLES}
    for role in ROLES:
        need=[]
        for weekday in range(7):
            day=today+timedelta(days=(weekday-today.weekday())%7)
            wanted=hour_demands(plan,plan['planning_covers'] or expected(world,b,day)) if weekday in plan['days'] else {}
            need.append([((max(60,n*sum(MINUTES.values())/8) if role=='manager' else n*MINUTES[role])/0.85) if (n:=wanted.get(h,0)) else 0 for h in range(24)])
        goal[role]=need
    def cells(emp,days,start):
        length=emp.weekly_hours*60//len(days)
        for d in days:
            for h in range(start,min(24,math.ceil(start+length/60))):
                yield d,h,min(60,max(0,length-(h-start)*60))
    def add(emp,sign):
        row=coverage[rules.position(emp.position_id).role]
        for d,h,n in cells(emp,emp.days,emp.shift_start):row[d][h]+=n*sign
    assigned={e.id:copy.deepcopy(e) for e in members}
    for emp in assigned.values():add(emp,1)
    # Two stable passes allow early employees to respond to later shift changes.
    for _ in range(2):
        for emp in assigned.values():
            if emp.id in locked:continue
            role=rules.position(emp.position_id).role;add(emp,-1)
            def score(days,start):
                return sum(min(n,max(0,goal[role][d][h]-coverage[role][d][h])) for d,h,n in cells(emp,days,start))
            current=score(emp.days,emp.shift_start);options=[]
            length=emp.weekly_hours*60//len(emp.days)
            for days in combinations(range(7),len(emp.days)):
                for start in range(max(0,plan['opens']-1),min(20,24-math.ceil(length/60))+1):
                    value=score(days,start)
                    if value>current+0.1:options.append((value,days,start))
            for value,days,start in sorted(options,key=lambda row:(-row[0],row[1],row[2])):
                trial=copy.deepcopy(emp);trial.days=list(days);trial.shift_start=start
                try:rules.check_schedule(trial,replacing=emp.id)
                except RuleError:continue
                emp.days=trial.days;emp.shift_start=start;break
            add(emp,1)
    return [dict(employment_id=e.id,days=assigned[e.id].days,shift_start=assigned[e.id].shift_start,manager_schedule=True)
            for e in members if (e.days,e.shift_start)!=(assigned[e.id].days,assigned[e.id].shift_start)]


def auto_schedule(leader,b):
    plan=settings(leader.w,b)
    if not plan['auto_schedule']:return
    for args in suggestions(leader.w,b):
        emp=leader.rules.contract(args['employment_id']);name=leader.rules.person(emp.person_id).name
        detail='Stagger '+name+' for restaurant service: '+', '.join(DAY_NAMES[d] for d in args['days'])+f" from {args['shift_start']:02}:00; weekly hours and pay unchanged."
        leader.perform(b,'restaurant-schedule:'+emp.id,'restaurant_rota',args,0,True,detail)
    leader.s['restaurants'][b.id]['rota_requested']=False


def staffing_plan(world,b):
    from .staffing import vacancies,PURPOSES as ALL_PURPOSES
    from .ui_workflows import role_label
    rules=BusinessRules(Engine(world));plan=settings(world,b);goal=targets(world,b);gaps=role_gaps(world,b)
    staff=[e for e in world.employments if e.employer==b.id and e.status in ('active','joining')]
    totals={r:0 for r in ROLES};projections=[]
    for offset in range(1,8):
        day=date.fromisoformat(world.date)+timedelta(days=offset);clone=copy.deepcopy(world);clone.date=day.isoformat()
        for emp in clone.employments:
            if emp.status=='joining' and emp.start_date<=clone.date:emp.status='active'
        cb=next(x for x in clone.businesses if x.id==b.id);cr=BusinessRules(Engine(clone));buckets,_=cr.work(cb,day)
        # Apply the same equipment and service time consumption on the copy only.
        from .service_office import ServiceOffice
        from .property_operations import PropertyOperations
        from .property_services import PropertyServices
        from .service_products import ServiceProducts
        from .industry_operations import IndustryOperations
        PropertyOperations(cr.e).deliver(cr,cb,buckets);PropertyServices(cr.e).deliver_home_office(cr,cb,buckets)
        ServiceOffice(cr.e).deliver(cr,cb,buckets);ServiceProducts(cr.e).operate(cb,buckets);IndustryOperations(cr.e).before(cb,buckets)
        for role in ROLES:totals[role]+=sum(buckets.get(role,[]))/60
        demand=expected(clone,cb,day);result=capacity(clone,cb,buckets,demand,stock=100000) if demand else dict(output=0,capacity=0,hourly=[])
        projections.append(dict(date=day.isoformat(),day=DAY_NAMES[day.weekday()],capacity=result['output'],target=demand,unit='meals',hourly=result['hourly']))
    rows=[]
    for role in ROLES:
        members=[e for e in staff if rules.position(e.position_id).role==role];hours=sum(e.weekly_hours for e in members)
        missing=max(0,math.ceil(gaps[role]));required=role in OPENING_ROLES['restaurant']
        rows.append(dict(role=role,label=role_label(role),purpose=PURPOSES[role],required=required,target_hours=goal[role],target_people=math.ceil(goal[role]/40),
            active=sum(e.status=='active' for e in members),joining=sum(e.status=='joining' for e in members),hours=hours,coverage=round(totals[role],1),missing=missing,
            status='Required role missing' if required and not members else 'More hours suggested' if missing else 'Planned hours covered',
            vacancies=len(vacancies(world,b.id,role)),market_pay=ROLE_PAY[role],shared_hours=round(goal[role]-gaps[role]-hours,1),
            url='/?'+urlencode(dict(page='hiring',business_id=b.id,scope=b.id,role=role))))
    short=max(rows,key=lambda r:r['missing'])
    summary=(f"{short['label']}: {short['missing']} more hours/week suggested. Review busy-hour coverage before hiring." if short['missing'] else
             'Contracted hours cover the plan. Check overlapping shifts, leave and meal-time coverage below.')
    return dict(restaurant=True,rows=rows,summary=summary,workload=f"Plan for {plan['planning_covers'] or 'forecast'} meals per open day across {len(plan['days'])} days. About {sum(goal.values())/40:.1f} full-time equivalents; part-time teams need more people.",
        assumptions='Each meal uses five chef, two preparation, four service, one-and-a-half dishwashing and three-quarter host minutes. Uncovered support work falls to chefs and servers. Forecast meals assume ingredients are available; actual sales also depend on cash, stock and daily demand.',
        projections=projections,minimum='Manager, Chef, Server',optional=[dict(role=r,label=role_label(r),purpose=ALL_PURPOSES.get(r,'Shared specialist'),url='/?'+urlencode(dict(page='hiring',business_id=b.id,scope=b.id,role=r))) for r in INDUSTRY_ROLES['restaurant'] if r not in ROLES])
