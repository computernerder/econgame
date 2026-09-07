"""Explain staffing requirements and guide hiring without changing the live world."""
import copy
import math
from datetime import date,timedelta
from urllib.parse import urlencode

from .positions import open_positions
from .industries import SALES, PROJECTS, sales_capacity, project_capacity
from .business_models import OPENING_ROLES,INDUSTRY_ROLES,ROLE_PAY,ROLE_SKILLS,Employment
from .business_rules import BusinessRules
from .domain import Engine,RuleError

PURPOSES={
    'cleaner':'Delivers cleaning plans and outside jobs from one time budget; allow travel and cash for supplies.',
    'gardener':'Maintains grounds; equipment, weather, travel and supplies constrain daily work.',
    'security_guard':'Provides property patrols and outside security services. A current security-guard credential is required.',
    'driver':'Drives one delivery per 30 qualified minutes, within fleet limits and overlapping dispatch coverage.',
    'dispatcher':'Coordinates one delivery per 10 qualified minutes, overlapping driver shifts.',
    'machine_operator':'Runs manufacturing equipment and leads production on customer orders.',
    'production_worker':'Supports manufacturing at 50% of qualified time, limited by machine-operator hours.',
    'tradesperson':'Delivers plumbing and electrical jobs and supervises apprentices.',
    'apprentice':'Contributes 50% of qualified hours, limited by tradesperson supervision.',
    'builder':'Delivers construction projects and supervises laborers.',
    'laborer':'Contributes 50% of qualified hours, limited by builder supervision.',
    'teller':'Serves 12 outside customers per qualified hour; handles deposits and fee income.',
    'loan_officer':'Reviews a loan in two qualified hours. Cash reserves constrain lending.',
    'manager':'Provides management coverage. Without leadership, productive capacity falls; plan one manager per eight other staff.',
    'cashier':'Checkout capacity: 10 sales per qualified work hour. Must overlap with stockers.',
    'stocker':'Stock handling: 18 sales per qualified work hour. Must overlap with cashiers.',
    'chef':'Kitchen capacity: 13 meals per qualified work hour. Must overlap with servers.',
    'server':'Service capacity: 15 meals per qualified work hour. Must overlap with chefs.',
    'engineer':'Delivers support, consulting and fixed-fee work from one shared time budget. Requires an engineering qualification.',
    'technician':'Adds engineering capacity at 70% of qualified technician time. Can complement engineering staff.',
    'property_manager':'Services one external unit per 15 qualified minutes each working day and provides management coverage.',
    'maintenance':'Performs maintenance work. Rental portfolios need 15 qualified minutes per owned rental property per weekday; uncovered work is outsourced.',
}


from .specialists import PURPOSES as SPECIALIST_PURPOSES
PURPOSES.update(SPECIALIST_PURPOSES)

def vacancies(world,bid,role):
    filled={e.position_id for e in world.employments if e.status in ('active','joining','seller')}
    return [p for p in open_positions(world,bid) if p.role==role and p.id not in filled]


def staffing_plan(world,bid):
    from .ui_workflows import role_label
    rules=BusinessRules(Engine(world));b=rules.company(bid)
    from .restaurant import active
    if active(world,b):
        from .restaurant_staffing import staffing_plan as dining_plan
        return dining_plan(world,b)
    staff=[e for e in world.employments if e.employer==bid and e.status in ('active','joining')]
    positions={p.id:p for p in world.positions}
    core=(["manager",PROJECTS[b.industry][0],PROJECTS[b.industry][1]] if b.industry in PROJECTS else
          ["manager",SALES[b.industry][0],SALES[b.industry][2]] if b.industry in SALES else
          {'cleaning':['manager','cleaner'],'landscaping':['manager','gardener'],'security':['manager','security_guard'],'logistics':['manager','driver','dispatcher'],'self_storage':['property_manager','maintenance'],'bank':['manager','teller','loan_officer'],'property_management':['property_manager','maintenance'],'rental':['property_manager','maintenance'],'office':['manager']}[b.industry])
    by_role={role:[e for e in staff if positions[e.position_id].role==role] for role in INDUSTRY_ROLES[b.industry]}
    shared={role:0.0 for role in INDUSTRY_ROLES[b.industry]}
    contracts={e.id:e for e in world.employments}
    for assignment in world.systems.get('assignments',[]):
        emp=contracts.get(assignment['employment_id'])
        if not assignment['active'] or not emp or emp.status not in ('active','joining'):continue
        weekdays=sum(day<5 for day in emp.days)
        if assignment['source']==bid:
            shared[positions[emp.position_id].role]-=assignment['minutes']*weekdays/60
        if assignment['target']==bid:
            shared[assignment['role']]+=(assignment['minutes']-assignment['travel'])*weekdays/60
    targets={role:0 for role in core}
    targets['manager']=40*max(1,math.ceil(sum(e.weekly_hours for e in staff if positions[e.position_id].role not in ('manager','property_manager'))/320)) if 'manager' in core else 0
    assumptions='Planning hours assume standard productivity, a five-day trading week and overlapping shifts. Actual skill, leave, holidays and shared assignments affect coverage.'
    if b.industry in SALES:
        from .economy import Economy
        demand=math.ceil(b.daily_demand*max(25,200-b.price_percent)/100*Economy(Engine(world)).demand_factor(b)/100)
        factor=max(0.7,b.capacity_percent/100) if b.status=='developing' else max(0.01,b.capacity_percent/100)
        a,am,z,zm,_,unit=SALES[b.industry]
        rates={a:60/am,z:60/zm}
        targets.update({role:math.ceil(demand*5/rate/factor) for role,rate in rates.items()})
        workload=f'Plan for about {demand} '+SALES[b.industry][5]+' per working day at current prices and regional demand, before daily variation.'
    elif b.industry in PROJECTS:
        lead,support,percent=PROJECTS[b.industry]
        technical=max(0,sum(e.weekly_hours for e in by_role[support])+shared[support])*percent/100
        from .project_portfolio import jobs,remaining
        active=jobs(b);planned=remaining(b) if active else (b.contract_base_minutes or b.contract_minutes)
        base=planned/60/b.project_planning_days+(5 if b.industry=='engineering' else 0)
        targets[lead]=max(4,math.ceil(max(base*5-technical,base*2.5 if b.industry!='engineering' else 0)))
        workload=f'Planning goal: {len(active)} active projects with {planned/60:g} qualified hours remaining over {b.project_planning_days} working days. Concurrent limit: {b.concurrent_project_limit}. {support.replace("_"," ").title()} time contributes at {percent}%.'
        if b.industry=='engineering':workload+=' Allow up to 1 support hour and 4 consulting hours per day.'
        else:workload+=' Assistants need lead workers; their contribution cannot exceed lead-worker hours.'
        assumptions+=' This is a throughput goal, not an opening requirement; fewer workers can complete work more slowly.'
    elif b.industry in ('cleaning','landscaping','security'):
        from .property_services import SERVICES
        role=SERVICES[b.industry]['role']
        jobs=[j for j in world.systems.get('property_service_jobs',[]) if j['provider']==bid and j['status']=='working']
        internal=sum((j['effort']+90)*7/max(1,j['interval']) for j in jobs)
        targets[role]=math.ceil((b.daily_demand*5+internal)/60)
        workload=f'Outside demand starts near {b.daily_demand/60:g} qualified hours per weekday; {len(jobs)} active property plans add about {internal/60:.1f} weekly hours including travel. Supplies are paid before 14-day collections. Equipment, qualifications and weather can reduce delivery.'
    elif b.industry=='logistics':
        targets['driver']=math.ceil(b.daily_demand*0.5*5)
        targets['dispatcher']=math.ceil(b.daily_demand/6*5)
        workload=f'Outside demand is about {b.daily_demand} deliveries/day, plus group needs. Each delivery takes 30 qualified driver minutes and 10 overlapping dispatcher minutes. Fleet ceiling: {b.fleet_vehicles*8} daily delivery slots. Cross-region group deliveries use two slots. Add hours for your group workload.'
    elif b.industry=='self_storage':
        targets['property_manager']=max(4,math.ceil(min(3,b.storage_units-b.storage_occupied)*0.5*5))
        targets['maintenance']=math.ceil(b.storage_units*2*5/60)
        workload=f'{b.storage_occupied}/{b.storage_units} units occupied. Allow 30 qualified minutes per new tenant (up to three/day) and two maintenance minutes per unit each weekday. Existing tenants pay on weekends; uncovered maintenance is outsourced.'
    elif b.industry=='bank':
        targets['teller']=math.ceil(b.daily_demand*5/12)
        targets['loan_officer']=20
        workload=f'{b.daily_demand} branch customers/day at 12 visits per qualified teller hour; allow two credit-review hours per loan, up to two new loans/day. Lending also needs cash above the deposit and payroll reserve.'
    elif b.industry=='property_management':
        targets['property_manager']=max(4,math.ceil(b.external_units*0.25*5))
        targets['maintenance']=20
        workload=f'{b.external_units} external client units need 15 qualified minutes each per working day. The optional maintenance target supports up to four billable hours per day.'
    elif b.industry=='rental':
        count=sum(p.owner==bid and p.occupancy_use!='operating' and p.status!='sold' for p in world.properties)
        targets['maintenance']=math.ceil(count*0.25*5)
        workload=f'{count} rental properties. Leases earn rent without mandatory employees; uncovered maintenance is purchased from contractors. Property managers are optional leadership.'
    else:
        workload='Headquarters has no automatic sales. Hire specialists for the services and hours you actually assign to other companies.'
    from .revenue_kits import state as kit_state,settings as kit_settings,CATALOG as KIT_CATALOG
    if kit_state(world,b):
        configured=kit_settings(world,b)
        if b.industry=='gas_station':
            base_demand=demand if configured['fuel']['enabled'] else 0
            cashier_minutes=base_demand*0.75;attendant_minutes=base_demand*0.6
            for key,row in configured.items():
                q=KIT_CATALOG[b.industry][key]
                if q['kind']=='sales' and row['enabled']:
                    sales=q['demand']*max(15,200-row['price_percent'])/100
                    cashier_minutes+=sales*3;attendant_minutes+=sales*2
            targets['cashier']=math.ceil(cashier_minutes*5/60/factor)
            targets['attendant']=math.ceil(attendant_minutes*5/60/factor)
            workload='Planning goal covers fuel and enabled convenience streams together. Checkout and preparation time compete across offerings; adjust work shares to match demand.'
        elif b.industry=='engineering':
            service_hours=(1 if configured['support']['enabled'] else 0)+(4 if configured['consulting']['enabled'] else 0)
            targets['engineer']=max(4,math.ceil(max(0,(planned/60/b.project_planning_days+service_hours)*5-technical)))
            workload=f'Planning goal: {len(active)} active projects, {planned/60:g} work hours remaining over {b.project_planning_days} working days, plus up to {service_hours} support/consulting hours per day.'
            if configured.get('drawing_review',{}).get('enabled'):
                workload+=' Drawing review and stamping require a currently licensed professional engineer; technician hours cannot replace that licensed work.'
        elif b.industry=='factory':
            products_per_day=planned/60/b.project_planning_days
            factor=max(0.01,b.capacity_percent/100)
            targets['machine_operator']=max(1,math.ceil(products_per_day*0.5*5/factor))
            targets['production_worker']=max(1,math.ceil(products_per_day*0.25*5/factor))
            workload=f'Planning goal: {planned/60:g} products across accepted manufacturing orders over {b.project_planning_days} working days. At standard equipment capacity, each product needs 30 machine-operator minutes and 15 production-worker minutes; order progress records 60 minutes per product.'
        workload+=' Revenue-kit work shares determine which stream receives those hours. Setup, material cash and equipment condition can further limit output.'
    projections=[];totals={role:0 for role in core}
    for offset in range(1,8):
        day=date.fromisoformat(world.date)+timedelta(days=offset)
        if day.weekday()>=5:continue
        clone=copy.deepcopy(world);clone.date=day.isoformat()
        for emp in clone.employments:
            if emp.status=='joining' and emp.start_date<=clone.date:emp.status='active'
        engine=Engine(clone);r=BusinessRules(engine);projected=r.company(bid)
        buckets,management=r.work(projected,day)
        for role in core:totals[role]+=sum(buckets.get(role,[]))/60
        if b.industry in SALES:
            output=sales_capacity(b.industry,buckets)*management*max(70 if b.status=='developing' else 0,b.capacity_percent)//10000
            projections.append(dict(date=day.isoformat(),capacity=output,target=demand,unit=SALES[b.industry][5]+'/day'))
        elif b.industry in PROJECTS:
            output=project_capacity(b.industry,{r:sum(v) for r,v in buckets.items()})*management*min(120,max(70 if b.status=='developing' else 0,b.capacity_percent))//10000
            projections.append(dict(date=day.isoformat(),capacity=round(output/60,1),target=round(base,1),unit='qualified hours/day'))
        elif b.industry=='logistics':
            from .logistics import freight_capacity
            projections.append(dict(date=day.isoformat(),capacity=freight_capacity(b,buckets,management),target=b.daily_demand,unit='deliveries/day'))
        elif b.industry=='self_storage':
            projections.append(dict(date=day.isoformat(),capacity=min(3,sum(buckets['property_manager'])//30),target=min(3,b.storage_units-b.storage_occupied),unit='new tenants/day'))
        elif b.industry=='bank':
            factor=management*max(70 if b.status=='developing' else 0,b.capacity_percent)//100
            projections.append(dict(date=day.isoformat(),capacity=sum(buckets['teller'])*12*factor//6000,target=b.daily_demand,unit='customers/day'))
        elif b.industry=='property_management':
            projections.append(dict(date=day.isoformat(),capacity=sum(buckets['property_manager'])//15,target=b.external_units,unit='client units/day'))
    purposes=dict(PURPOSES)
    if b.industry=='self_storage':
        purposes['property_manager']='Admits a new storage tenant per 30 qualified minutes, up to three per working day. Existing tenants do not need daily admissions work.'
        purposes['maintenance']='Provides two maintenance minutes per unit per weekday; uncovered work costs $36 per hour.'
    if b.industry in SALES:
        a,am,z,zm,_,unit=SALES[b.industry]
        purposes[a]=f'Provides sales capacity at {60/am:g} {unit} per qualified hour; must overlap with {z.replace("_"," ")}. '
        purposes[z]=f'Provides stock or preparation capacity at {60/zm:g} {unit} per qualified hour; must overlap with {a.replace("_"," ")}. '
    rows=[];priorities=[]
    for role in core:
        members=by_role[role];active=[e for e in members if e.status=='active'];joining=[e for e in members if e.status=='joining']
        committed=sum(e.weekly_hours for e in members);target=targets.get(role,0)
        missing=max(0,math.ceil(target-max(0,committed+shared[role])));needed=role in OPENING_ROLES[b.industry]
        absent_required=needed and not members
        if absent_required:missing=max(4,missing)
        status='Required role missing' if absent_required else 'More hours suggested' if missing else 'Incoming hire planned' if joining else 'Optional' if target==0 and not needed else 'Planned hours covered'
        row=dict(role=role,label=role_label(role),purpose=purposes.get(role,'Shared service specialist.'),required=needed,target_hours=target,target_people=math.ceil(target/40),active=len(active),joining=len(joining),hours=committed,coverage=round(totals.get(role,0),1),missing=missing,status=status,vacancies=len(vacancies(world,bid,role)),market_pay=ROLE_PAY[role],url='/?'+urlencode(dict(page='hiring',business_id=bid,scope=bid,role=role)))
        row['shared_hours']=round(shared[role],1)
        rows.append(row)
        if missing:priorities.append(row)
    priority=sorted(priorities,key=lambda r:(r['status']!='Required role missing',-r['missing']))
    if priority:
        first=priority[0];summary=f"Start with {first['label']}: {first['missing']} more contracted hours/week suggested. Part-time hires can fill smaller gaps."
    elif projections and any(p['capacity']<p['target'] for p in projections):
        summary='Planned hours are covered, but effective coverage is below the goal on some days. Check overlapping shifts, leave, training and shared assignments before adding headcount.'
    else:summary='No immediate core staffing gap is indicated. Hire for growth, resilience or a specific shared service rather than filling every possible role.'
    return dict(rows=rows,summary=summary,workload=workload,assumptions=assumptions,projections=projections,minimum=', '.join(sorted(r.replace('_',' ').title() for r in OPENING_ROLES[b.industry])) or 'No mandatory employees',optional=[dict(role=role,purpose=PURPOSES.get(role,'Shared service specialist.'),label=role_label(role),url='/?'+urlencode(dict(page='hiring',business_id=bid,scope=bid,role=role))) for role in INDUSTRY_ROLES[b.industry] if role not in core])


def hiring_view(world,bid,role,position_id=""):
    from .ui_workflows import role_label
    rules=BusinessRules(Engine(world));b=rules.company(bid)
    if role not in INDUSTRY_ROLES[b.industry]:raise RuleError('Choose a role used by this business.')
    plan=staffing_plan(world,bid)
    row=next((r for r in plan['rows'] if r['role']==role),None)
    hours=min(40,max(4,row['missing'] if row and row['missing'] else 40))
    salary=ROLE_PAY[role]*hours//40
    vacant=vacancies(world,bid,role);position=vacant[0] if vacant else None
    if position_id:
        position=next((p for p in vacant if p.id==position_id),None)
        if position is None:raise RuleError("This position is no longer vacant. Reopen the employee hierarchy and select an available vacancy.")
    from .specialists import LICENSES, recruitment_quote
    recruitment=recruitment_quote(world,bid)
    license_name=(position.required_license if position else None) or LICENSES.get(role)
    eligible=[];excluded=[]
    for person in world.people:
        if not person.candidate:continue
        reason=None
        if role=='engineer' and not any('Engineering' in q for q in person.qualifications):reason='Engineering qualification required'
        elif license_name and person.licenses.get(license_name,'')<world.date:reason='Required license missing or expired'
        if not reason:
            try:rules.check_schedule(Employment('offer-preview',person.id,position.id if position else 'new-position',bid,salary,hours,(date.fromisoformat(world.date)+timedelta(days=3)).isoformat(),status='joining'))
            except RuleError as error:reason=str(error)
        skill=ROLE_SKILLS[role]
        item=dict(id=person.id,name=person.name,qualifications=person.qualifications,skill=person.skills.get(skill,30) if skill in person.demonstrated else None,reason=reason)
        (excluded if reason else eligible).append(item)
    eligible.sort(key=lambda p:(p['skill'] is None,-(p['skill'] or 0),p['name']))
    return dict(business_id=bid,business_name=b.name,role=role,label=role_label(role),purpose=row['purpose'] if row else PURPOSES.get(role,'Optional specialist: hire for an identified service need.'),requirements='Engineering qualification required.' if role=='engineer' else 'No mandatory degree for this role in the current game rules.',license=license_name,hours=hours,salary=salary,market_pay=ROLE_PAY[role],cash=world.cash(bid),upfront=salary+recruitment['fee'],recruitment=recruitment,eligible=eligible,excluded=excluded,position_id=position.id if position else '',starts=(date.fromisoformat(world.date)+timedelta(days=3)).isoformat(),row=row)
