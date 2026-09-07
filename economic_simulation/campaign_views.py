"""Progressively disclosed campaign screens. All values come from saved state."""
from datetime import date,timedelta
from .positions import open_positions
from .domain import GAME_RULES,Engine
from .campaign import Campaign
from .workforce import Workforce,BOOL_FIELDS,LIMITS
from .business_rules import BusinessRules
from .business_models import ROLE_SKILLS,INDUSTRY_ROLES

PAGES={'policies','workforce','services','expansion','regions','financing','inbox','scorecard','franchises','spaces','settings','forecast'}
PAGES.update({'operations_center','home_office','property_workbench','commercial_contracts','property_services','developer'})


from .money_display import money

def field(name,label,value='',kind='text',options=None,minimum=None,maximum=None):
    monetary={'salary_limit','training_budget','purchasing_limit','hourly_rate','shift_premium','bonus','health_account','education','transport','childcare','meals'}
    if kind=='number' and name in monetary:
        name+='_dollars';value=value/100;minimum=minimum/100 if minimum is not None else None;maximum=maximum/100 if maximum is not None else None
        label=label.replace('(cents per employee/month)','($ per employee/month)').replace('(cents)','($)')
    return dict(name=name,label=label,value=value,kind=kind,options=options or [],minimum=minimum,maximum=maximum)

def choices(mapping):return [dict(value=k,label=v) for k,v in mapping.items()]

def hidden(name,value):return field(name,'',value,'hidden')

def form(action,title,description,fields,button='Review decision →'):
    return dict(action=action,title=title,description=description,fields=fields,button=button)

def table(title,headers,rows,description=''):
    return dict(title=title,headers=headers,rows=rows,description=description)

def campaign_view(world,page,scope,employment_id='',offset=0):
    if page=='inbox':
        from .decision_inbox import inbox_view
        return inbox_view(world)
    if page=='developer':
        from .developer_views import developer_view
        return developer_view(world,scope)
    if page=='property_services':
        from .property_service_views import property_service_view
        return property_service_view(world,scope)
    if page=='commercial_contracts':
        from .commercial_views import commercial_view
        return commercial_view(world,scope)
    if page in ('operations_center','home_office','property_workbench'):
        from .extension_views import extension_view
        return extension_view(world,page,scope)
    e=Engine(world);c=Campaign(e);wf=Workforce(e);r=BusinessRules(e)
    owned=[b for b in world.businesses if c.controlled(b.id)]
    from .business_views import entity_names
    names=entity_names(world)
    account_options=choices(names);business_options=choices({b.id:b.name for b in owned})
    employees=[emp for emp in world.employments if c.controlled(emp.employer) and emp.status in ('active','joining')]
    people_options=choices({emp.id:r.person(emp.person_id).name+' · '+names[emp.employer] for emp in employees})
    view=dict(title=page.replace('_',' ').title(),intro='',forms=[],tables=[],metrics=[],notes=[],links=[],page=page)
    if page=='policies':
        view.update(title='Policies and benefits',intro='Resolve each field through owner, company and individual agreements. Changes begin on their scheduled date; zero is a real choice.')
        values,sources,locked=wf.effective(scope)
        view['tables'].append(table('Effective policy',['Field','Value','Source','Lock'],[(k.replace('_',' ').title(),money(v) if k in ('health_account','education','transport','childcare','meals') else str(v),names.get(sources[k],sources[k]),'Parent locked' if k in locked else 'Overridable') for k,v in values.items()]))
        fields=[hidden('entity',scope),field('effective','Effective date',(date.fromisoformat(world.date)+timedelta(days=7)).isoformat(),'date')]
        for k,v in values.items():
            if k in locked:continue
            if k in ('medical','dental'):fields.append(field(k,k.title(),v,'select',choices({x:x.replace('_',' ').title() for x in GAME_RULES[k]})))
            elif k in BOOL_FIELDS:fields.append(field(k,k.replace('_',' ').title(),v,'checkbox'))
            else:
                lo,hi=LIMITS.get(k,(0,200000));label=k.replace('_',' ').title()+(' (cents per employee/month)' if k not in LIMITS else '')
                fields.append(field(k,label,v,'number',minimum=lo,maximum=hi))
        fields.append(field('locked','Lock these fields for child companies (comma-separated names)'))
        view['forms'].append(form('policy_set','Schedule a policy rollout','Only changed future obligations are applied. Expand this editor to choose a detailed compensation and benefit package.',fields))
        view['forms'].append(form('policy_reset','Restore inheritance','Clear this account’s local overrides from the selected date. The parent’s future changes will flow through.',[hidden('entity',scope),field('effective','Effective date',world.date,'date')]))
        view['tables'].append(table('Medical plan comparison',['Plan','Monthly premium','Deductible','Out-of-pocket limit','Network breadth'],[(k.replace('_',' ').title(),money(p['premium']),money(p['deductible']),money(p['limit']),str(p['network'])+'/100') for k,p in GAME_RULES['medical'].items()]))
        view['tables'].append(table('Rollout history',['Scope','Version','Effective','Change'],[(names.get(p['scope'],p['scope']),p['version'],p['effective'],'Restore inheritance' if p.get('reset') else ', '.join(p['values'])) for p in reversed(world.systems['policies'])][-50:]))
    elif page=='workforce':
        view.update(title='Career and employee development',intro='Promote, review and develop people. Skills, relationships, ambition, trust and workload influence outcomes separately.')
        emp=next((x for x in employees if x.id==employment_id),employees[0] if employees else None)
        if not emp:view['notes'].append('Acquire or open a business to begin developing its employees.');return view
        p=r.person(emp.person_id);b=r.company(emp.employer)
        view['title']=p.name+' · development'
        view['metrics']=[('Morale',p.morale),('Loyalty',p.loyalty),('Trust',p.trust),('Culture',b.culture)]
        view['links']=[dict(label='Basic pay, schedule and leave',url=f'/?page=employee&employment_id={emp.id}&scope={b.id}'),dict(label='All employees',url='/?page=people&scope='+scope)]
        view['notes']=[f'Career preference: {p.ambition}. Home region: {p.home_region}. Employment state: {p.labor_state}.',f'Notice date: {p.notice_on or "None"}. Education completion: {p.education.get("due","Not enrolled")}.']
        base=[hidden('employment_id',emp.id)]
        vacant=[pos for pos in open_positions(world,b.id) if not any(x.position_id==pos.id and x.status in ('active','joining') for x in employees)]
        if vacant:view['forms'].append(form('promote','Offer a promotion','The old position becomes vacant. Technical performance does not prove leadership; the new role begins a 30-day onboarding period.',base+[field('position_id','Vacant role',vacant[0].id,'select',choices({pos.id:pos.role.title() for pos in vacant})),field('amount_dollars','New monthly salary ($)',emp.salary/100,'number',minimum=100)]))
        from .employee_reporting import options as reporting_options, supervisor
        current=supervisor(world,emp)
        view['forms'].append(form('reporting','Change reporting line','Choose an employee in any owned business, including the home office. Payroll stays with the employer; this does not grant spending authority. Cycles and self-reporting are rejected.',base+[field('reports_to','Primary supervisor',current.id if current else '','select',choices({'':'Owner / company leadership',**reporting_options(world,emp)}))]))
        view['forms'].append(form('compensation','Compensation and incentives','Hourly pay uses contracted hours. Shift premiums are monthly cents; bonuses pay once. Commission and profit sharing depend on actual monthly results.',base+[field('pay_basis','Pay basis',emp.compensation.get('pay_basis','salary'),'select',choices({'salary':'Monthly salary','hourly':'Hourly contract'})),field('hourly_rate','Hourly rate (cents)',emp.compensation.get('hourly_rate',2000),'number',minimum=0),field('shift_premium','Monthly shift premium (cents)',emp.compensation.get('shift_premium',0),'number',minimum=0),field('commission_percent','Commission (%)',emp.compensation.get('commission_percent',0),'number',minimum=0,maximum=20),field('profit_share_percent','Profit share (%)',emp.compensation.get('profit_share_percent',0),'number',minimum=0,maximum=20),field('bonus','One-time bonus (cents)',0,'number',minimum=0)]))
        view['forms'].append(form('education','Sponsor education','Paid study takes two scheduled hours each working day. Qualifications become visible at completion; relevant work still demonstrates specific ability.',base+[field('course','Course','certificate','select',choices({'certificate':'Certification · 90 days · $1,200','trade':'Trade qualification · 1 year · $4,000','associate':'Associate · 2 years · $8,000','bachelor':'Bachelor · 4 years · $18,000','master':'Master · 2 years · $12,000','doctorate':'Doctorate · 3 years · $16,000'})),field('skill','Discipline','engineering','select',choices({k:k.title() for k in p.skills}))]))
        view['forms'].append(form('review_employee','Development review','Costs $100 and provides a dated, bounded estimate of current-role ability and workplace concerns.',base))
        view['links'].insert(0,dict(label='Benefits, time-off requests and coverage',url=f'/?page=employee&employment_id={emp.id}&scope={b.id}#employee-time-off'))
        view['tables'].append(table('Known observations',['Date','Source','Confidence','Evidence'],[(o['date'],o['source'],o['confidence'],o['detail']) for o in reversed(p.observations)]))
        view['tables'].append(table('Professional relationships',['Person','Recorded relationship'],[(r.person(pid).name,value) for pid,value in p.relationships.items()]))
    elif page=='services':
        view.update(title='Shared services and headquarters',intro='Reserve existing employee time for linked operations. Source payroll is charged once; internal reimbursements are eliminated from group results.')
        for b in owned:
            premises=[p for p in world.properties if p.owner==b.id and p.status in ('vacant','occupied') and not any(o['property_id']==p.id and o['active'] for o in world.systems['offices'])]
            if premises:
                view['forms'].append(form('headquarters','Fit out headquarters · '+b.name,'Costs $800 per desk. Hire specialists and assign their time to provide shared services.',[hidden('business_id',b.id),field('property_id','Company-owned premises',premises[0].id,'select',choices({p.id:p.name for p in premises})),field('desks','Desks',20,'number',minimum=1,maximum=200)]))
        view['tables'].append(table('Headquarters',['Company','Property','Desks','Status'],[(names.get(o['business_id'],o['business_id']),o['property_id'],o['desks'],'Active' if o['active'] else 'Not acquired') for o in world.systems['offices'] if c.controlled(o['business_id'])]))
        view['forms'].append(form('service_agreement','Create a service agreement','Both businesses retain independent finances. Markup changes their individual margins but not group profit.',[field('source','Employing business','','select',business_options),field('target','Receiving business','','select',business_options),field('markup','Cost markup (%)',0,'number',minimum=0,maximum=25),field('staff_access','Permit shared staff',True,'checkbox')]))
        view['forms'].append(form('assign_staff','Assign contracted time','Intervals must fit inside the employee’s existing shift. Travel consumes 30 minutes when counties differ; leave and study reduce delivery.',[field('employment_id','Employee','','select',people_options),field('target','Receiving business','','select',business_options),field('role','Service role','maintenance','select',choices({k:k.replace('_',' ').title() for k in ROLE_SKILLS})),field('start_minute','Start minute after midnight (08:00 = 480)',480,'number',minimum=0,maximum=1439),field('minutes','Minutes reserved per working day',120,'number',minimum=1,maximum=720)]))
        active=[a for a in world.systems['assignments'] if a['active']]
        if active:view['forms'].append(form('end_assignment','End an assignment','Returns the reserved time to the employer and retains its history.',[field('assignment_id','Assignment',active[0]['id'],'select',choices({a['id']:a['id']+' → '+names.get(a['target'],a['target']) for a in active}))]))
        view['tables'].append(table('Assignments',['Employee','Employer','Recipient','Role','Reserved minutes','Travel','Last charge'],[(r.person(r.contract(a['employment_id']).person_id).name,names.get(a['source'],a['source']),names.get(a['target'],a['target']),a['role'],a['minutes'],a['travel'],money(a['last_cost'])) for a in active]))
        properties=[p for p in world.properties if p.owner in names and p.owner not in ('personal','company') and p.status in ('vacant','occupied')]
        view['forms'].append(form('headquarters','Fit out a headquarters','Requires a company-owned vacant building. Each desk costs $800. Specialists and agreements provide the actual service capacity.',[field('business_id','Company','','select',business_options),field('property_id','Owned building','','select',choices({p.id:p.name for p in properties})),field('desks','Desks',20,'number',minimum=1,maximum=200)]))
        for b in owned:
            view['links'].append(dict(label='Leadership and authority · '+b.name,url='/?page=business&business_id='+b.id+'&scope='+b.id+'#leadership'))
            view['forms'].append(form('recruit','Recruitment campaign · '+b.name,'Applicants arrive in 3–7 days. A campaign does not promise a hire or reveal private skill values.',[hidden('business_id',b.id),field('role','Role',INDUSTRY_ROLES[b.industry][0],'select',choices({k:k.title() for k in INDUSTRY_ROLES[b.industry]})),field('channel','Channel','local','select',choices({'local':'Local advertising · $200 · 7 days','specialist':'Specialist recruiter · $650 · 7 days','referral':'Referral campaign · $350 · 3 days'}))]))
    else:
        from .campaign_screens import populate
        populate(view, world, page, scope, c, owned, names)
    return view
