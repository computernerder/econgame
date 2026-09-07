"""Focused restaurant controls. Forecasts are supplied by the staffing guide."""
from .restaurant import settings,active,SCALES,DAY_NAMES,targets,expected
from .business_rules import BusinessRules
from .domain import Engine
from .campaign_views import field,hidden,form,choices
from .management import policy,HIRING
from .positions import open_positions
from .workforce import Workforce


def view(world,b):
    rules=BusinessRules(Engine(world));p=settings(world,b);enabled=active(world,b)
    workforce=Workforce(Engine(world));staff=[];cost=0
    for e in world.employments:
        if e.employer!=b.id or e.status not in ('active','joining'):continue
        employee_cost=e.salary+e.salary*max(0,e.weekly_hours-40)//max(1,e.weekly_hours*2)+e.compensation.get('shift_premium',0)
        from .domain import GAME_RULES
        employee_cost+=employee_cost*GAME_RULES['tax']['payroll_percent']//100+workforce.benefit_cost(e,workforce.effective(b.id,e)[0])
        cost+=employee_cost
        length=e.weekly_hours*60//len(e.days);end=e.shift_start*60+length
        from .time_off import absent
        staff.append(dict(id=e.id,name=rules.person(e.person_id).name,role=rules.position(e.position_id).role.replace('_',' ').title(),
            status=e.status,hours=e.weekly_hours,days=e.days,start=e.shift_start,end=f'{end//60:02}:{end%60:02}',cost=employee_cost,
            pinned=e.id in p['manual_staff'],away=absent(world,e,world.date),salary=e.salary))
    controls=[form('restaurant_plan','Opening hours, demand and staffing plan',
        'Save to use meal-time operations at this location. Plan a volume for staffing, or use 0 to follow forecast demand. Opening longer does not create customers. Advertising is paid daily when cash is available. Managers schedule when their scheduling policy allows it.',[
            hidden('business_id',b.id),field('days','Open days',[str(d) for d in p['days']],'multiselect',choices(dict((str(i),n) for i,n in enumerate(DAY_NAMES)))),
            field('opens','Opens at (24-hour clock)',p['opens'],'number',minimum=5,maximum=16),field('closes','Closes at (24-hour clock)',p['closes'],'number',minimum=12,maximum=24),
            field('takeaway','Takeaway share (%)',p['takeaway'],'number',minimum=0,maximum=80),field('stock_days','Ingredient stock target (days)',p['stock_days'],'number',minimum=1,maximum=5),
            field('marketing_monthly_dollars','Monthly advertising budget ($)',p['marketing_monthly']/100,'number',minimum=0,maximum=50000),
            field('planning_covers','Staffing goal: meals per open day (0 = forecast)',p['planning_covers'],'number',minimum=0,maximum=2000),
            field('auto_schedule','Manager may stagger unpinned shifts',p['auto_schedule'],'checkbox')],button='Review restaurant plan →')]
    controls[0].update(anchor='restaurant-plan',expanded=not enabled)
    operating=policy(b,world)
    controls.append(form('management_policy','Restaurant hiring and cash policy',
        'Grow toward workload hires the role with the largest weekly hours gap, up to your headcount limit. Managers make one hiring attempt each Monday. Joining employees count toward the limit. Cash, pay bands and delegated annual commitments still apply; exceptions go to the decision inbox.',[
            hidden('target',b.id),field('hiring','Hiring approach',operating['hiring'],'select',choices(dict(HIRING, grow='Grow toward restaurant workload'))),
            field('staffing_target','Maximum active and joining employees',b.authority.get('staffing_target',len(open_positions(world,b.id))),'number',minimum=0,maximum=100),
            field('cash_reserve_dollars','Minimum cash reserve ($)',operating['cash_reserve']/100,'number',minimum=0,maximum=10000000),
            field('stock','Manager replenishes ingredients',operating['stock'],'checkbox')],button='Review hiring policy →'))
    return dict(active=enabled,plan=p,scale=SCALES[p['level']],next=SCALES.get(p['level']+1),forms=controls,staff=staff,
        roles=sorted({e['role'] for e in staff}),days=DAY_NAMES,cost=cost,hours=sum(e['hours'] for e in staff),fte=round(sum(targets(world,b).values())/40,1),expected=expected(world,b))
