"""High-level property care, scale choices and HR work visibility."""
from .domain import Engine, RuleError
from .campaign import Campaign
from .campaign_views import field, hidden, choices, form, table, money
from .property_development import BLUEPRINTS, LEVELS, Development, owner_busy
from .property_operations import systems_for
from .qualified_capacity import TRADE_LICENSES

def detail(world,pid):
    p=next(p for p in world.properties if p.id==pid)
    facts=systems_for(world,p)
    designs=[]
    if p.category=='land':
        for design in BLUEPRINTS:
            for level in LEVELS:
                try:designs.append(Development(Engine(world)).quote(p,design,level))
                except RuleError:continue
    from .business_models import INDUSTRY_NAMES
    development=next((j for j in reversed(world.systems.get('developments',[])) if j['property_id']==pid),None)
    building=bool(development and development['status']=='building')
    description=(development['label']+' under construction. The budget is funded; lease or occupy after completion.' if building else p.description)
    if building:designs=[]
    if p.category!='land' and description=='Vacant serviced land. Fund a suitable building before occupation or rent.':
        description=p.kind+'. '+('Ready to lease or occupy with a compatible business.' if p.status=='vacant' else 'Use and occupancy follow the property status and current agreements.')
    return dict(description=description,building=building,acquisition_basis=p.basis-(development['spent'] if development else 0),committed_basis=p.basis+(development['prepaid'] if development else 0),land=p.category=='land',designs=designs,specialization=', '.join(INDUSTRY_NAMES.get(k,k.replace('_',' ').title()) for k in p.specialization),
        systems=[] if p.category=='land' else [dict(key=k,name='Heating / cooling' if k=='heating_cooling' else k.replace('_',' ').title(),condition=v['condition'],age=v['age'],
            license=TRADE_LICENSES.get(k,'General qualified work'),priority='Urgent' if v['condition']<25 else 'Repair due' if v['condition']<40 else 'Monitor' if v['condition']<65 else 'Serviceable') for k,v in facts.items()],
        work=[j for j in world.systems.get('property_work',[]) if j['property_id']==pid and j['status']=='working'],
        development=development)

def extend(view,world,names,businesses,scope):
    page=view['page'];e=Engine(world);c=Campaign(e)
    props=[p for p in world.properties if p.owner and c.controlled(p.owner)]
    if page not in ('property_workbench','home_office'):return
    if page=='property_workbench':
        lots=[p for p in props if p.category=='land' and p.status=='vacant']
        buildings=[p for p in props if p.category!='land']
        urgent=sum(v['condition']<40 for p in buildings for v in systems_for(world,p).values())
        view['metrics']=[('Owned buildings',str(len(buildings))),('Empty lots',str(len(lots))),('Systems needing repair',str(urgent)),('Owner time','2 decisions/day while repairing' if owner_busy(world) else 'Available')]
        view['links'].insert(0,dict(label='Buy an empty lot',url='/?page=market&category=land&scope='+scope))
        view['notes'].insert(0,'Start with outside contractors or basic owner repairs. Add licensed trades and an in-house agent when recurring work supports their payroll. Property equipment is separate from business production equipment.')
        view['tables'].insert(0,table('Property systems needing attention',['Property','System','Condition','Required credential','Next step'],
            [(p.name,k.replace('_',' ').title(),str(v['condition'])+'/100',TRADE_LICENSES.get(k,'General qualified work'),'Repair below 40; inspect or maintain otherwise') for p in buildings for k,v in systems_for(world,p).items() if v['condition']<65]))
        view['tables'].insert(1,table('Construction projects',['Property','Design / size','Status','Schedule','Cost installed','Reserved / refundable'],
            [(next(p.name for p in world.properties if p.id==j['property_id']),j['label']+' / '+str(j['area'])+' m²',j['status'],str(j['elapsed'])+' / '+str(j['days'])+' days',money(j['spent']),money(j['prepaid'])+' / '+money(j.get('refunded',0))) for j in world.systems.get('developments',[])]))
        rows=[]
        for p in lots:
            for design in BLUEPRINTS:
                for level in LEVELS:
                    try:q=Development(e).quote(p,design,level)
                    except RuleError:continue
                    rows.append((p.name,q['label'],str(q['area'])+' m²',money(q['total']),str(q['days'])+' days',money(q['rent']),money(q['estimated_value'])))
        view['tables'].append(table('Building options for owned lots',['Lot','Design','Floor area','Cash reserved','Duration','Potential rent / month','Estimated completed value'],rows,
            'Construction includes approvals, installed building systems and 10% contingency. Reserve is fully funded before work. Values depend on local demand and workmanship; businesses, stock and production equipment are purchased separately.'))
        view['forms'].insert(0,form('develop_property','Build on an empty lot','Review the matching building option below. Starter, established and large premises have different area, cost and schedule. All capital is reserved now; unused contingency returns on completion.',[
            field('property_id','Owned empty lot','','select',choices({p.id:p.name for p in lots})),field('blueprint','Building design','homes','select',choices({k:v[0] for k,v in BLUEPRINTS.items()})),field('level','Scale',1,'select',choices({str(k):v[0] for k,v in LEVELS.items()}))]))
        for f in view['forms']:
            if f['action']=='property_work':
                f['description']+=' Electrical, HVAC and plumbing require valid licenses. Owner work supports basic interior/exterior work only, uses four hours per simulated day, and leaves two discretionary decisions per day. Required approvals and recovery remain available.'
                for x in f['fields']:
                    if x['name']=='provider':x['options'].insert(1,dict(value='owner',label='Owner — materials only; spend decision time'))
    # A property-specific work product, delivered using the existing finite office queue.
    from .internal_property_services import agent_department
    providers={b.id:b.name for b in businesses if b.status=='operating' and agent_department(world,b)}
    targets={p.id:p.name for p in world.properties if p.status=='market' or p in props}
    view['forms'].append(form('service_request','Use an in-house real estate agent','Managers and directors prefer a staffed home office by default for planned flips and marketed company property. A licensed home-office agent can use basic office tools without separate department setup; configuring a department adds tools and explicit coverage. Sixteen qualified hours prepare one closing, valid 90 days. Completed work reduces brokerage by 70%; payroll and other closing expenses remain.',[
        hidden('department','real_estate_agent'),hidden('product','property_representation'),hidden('mode','internal'),field('recipient','Buyer or seller account',scope,'select',choices(names)),field('provider','Staffed agent department','','select',choices(providers)),field('target_id','Property','','select',choices(targets)),hidden('days',30)]))
    view['tables'].append(table('Agent closing work',['Property','Client','Status','Expires','Actual fee reduction','Work product'],[(targets.get(t['target_id'],t['target_id']),names.get(t['recipient'],t['recipient']),t['status'],t.get('expires','Pending'),money(t.get('fee_avoided',0)),t['outcome']) for t in world.systems.get('service_tasks',[]) if t.get('product')=='property_representation']))
    trade_staff=[emp for emp in world.employments if emp.status=='active' and c.controlled(emp.employer)]
    view['forms'].append(form('renew_license','Train or renew property credentials','Trade licenses require prior trade qualifications. The $250 fictional credential course takes 30 days. Hire an already licensed specialist when immediate coverage is needed.',[
        field('employment_id','Employee','','select',choices({emp.id:next(p.name for p in world.people if p.id==emp.person_id)+' / '+names[emp.employer] for emp in trade_staff})),field('license','Credential','real_estate','select',choices({k:k.title() for k in ('real_estate','electrical','plumbing','hvac')}))]))
    if page=='property_workbench':
        for action,label in [('develop_property','Build on a lot'),('property_work','Book repairs'),('outsource_property_work','Outsource work'),('service_request','Agent closing help')]:
            target=next((f for f in view['forms'] if f['action']==action and (action!='service_request' or f['title']=='Use an in-house real estate agent')),None)
            if target:
                target['anchor']='property-action-'+action
                view['links'].append(dict(label=label,url='#'+target['anchor']))

def hr_view(world):
    tasks=[t for t in world.systems.get('service_tasks',[]) if t.get('product') in ('role_search','assessment','onboarding','succession')]
    sourced={pid for t in tasks for pid in t.get('applicants',[])}
    return dict(sourced=len(sourced),hired=sum(any(emp.person_id==pid and emp.status in ('active','joining') for emp in world.employments) for pid in sourced),
        assessed=sum(t['status']=='complete' and t.get('product')=='assessment' for t in tasks),pending=sum(t['status'] in ('queued','working') for t in tasks),
        cost=sum(t['internal_cost']+t['outside_cost'] for t in tasks),minutes=sum(t['worked'] for t in tasks))
