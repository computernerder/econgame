"""Task-first shared teams, using saved queues and validated form presets."""
from datetime import date
from .business_views import entity_names
from .campaign_views import field,hidden,choices,form
from .navigation import url
from .shared_resources import departments,members,credential_gap,support_problem
from .specialists import PURPOSES,available
from .service_office import DEPARTMENTS
from .service_products import PRODUCTS
from .time_off import absent


def task_url(department,action='service_request',product='',page='home_office'):
    return url(page,department['provider'],action_focus=action,shared_team=department['id'],service_product=product)+'#task-focus'


def describe(world,department):
    from .ui_workflows import role_label
    names=entity_names(world);role=department['role'];provider=department['provider']
    people={p.id:p for p in world.people};staff=members(world,department)
    roster=[]
    for emp in staff:
        status=credential_gap(world,emp)
        if not status:
            status=('Joining' if emp.status=='joining' else 'On leave' if absent(world,emp)
                    else 'Not scheduled today' if date.fromisoformat(world.date).weekday() not in emp.days else 'Scheduled today')
        roster.append(dict(name=people[emp.person_id].name,status=status,url=url('employee',provider,employment_id=emp.id)))
    businesses=[b for b in world.businesses if b.id in names and b.status=='operating']
    coverage=[dict(name=b.name,county=b.region,covered=b.region in department['regions'],
                   expertise=b.industry in department['industries']) for b in businesses]
    covered_properties=[p for p in world.properties if p.owner in names and p.region in department['regions']]
    tasks=[t for t in world.systems.get('service_tasks',[]) if t['provider']==provider and t['department']==role
           and t['status'] in ('queued','working') and t['mode']!='outside']
    queue=[dict(label=PRODUCTS[t['product']][1] if t.get('product') in PRODUCTS else DEPARTMENTS[role][0],
                recipient=names.get(t['recipient'],t['recipient']),remaining=t['remaining'],status=t['status'],due=t['due']) for t in tasks]
    repairs=[j for j in world.systems.get('property_work',[]) if role=='maintenance' and j['provider']==provider and j['status']=='working']
    for job in repairs:
        prop=next(p for p in world.properties if p.id==job['property_id'])
        queue.append(dict(label=job['system'].replace('_',' ').title()+' '+job['kind'],recipient=prop.name,
                          remaining=job['remaining'],status='working',due=''))
    for job in world.systems.get('property_service_jobs',[]):
        if role!='maintenance' or job['provider']!=provider or job['status']!='working':continue
        prop=next(p for p in world.properties if p.id==job['property_id'])
        queue.append(dict(label=job['kind'].title()+' visits',recipient=prop.name,
            remaining=job['remaining']+max(0,job['visits']-job['completed_visits']-1)*job['effort'],status='scheduled',due=job['due']))
    ids={e.id for e in staff}
    assignments=[]
    for a in world.systems.get('assignments',[]):
        if not a['active'] or a['employment_id'] not in ids:continue
        emp=next(e for e in staff if e.id==a['employment_id'])
        assignments.append(dict(employee=people[emp.person_id].name,target=names.get(a['target'],a['target']),
            minutes=a['minutes'],travel=a['travel'],start=f"{a['start_minute']//60:02}:{a['start_minute']%60:02}",cost=a['last_cost'],
            stop=form('end_assignment','End support · '+people[emp.person_id].name+' → '+names.get(a['target'],a['target']),
                      'Return this reserved time to the employer. Employment and past charges remain.',[hidden('assignment_id',a['id'])],button='Review ending support →')))
    actions=[]
    if role in PURPOSES:
        actions.append(dict(label='Schedule regular support',url=task_url(department,'share_department_staff')))
    if role=='maintenance':actions.append(dict(label='Book a property repair',url=task_url(department,'property_work',page='property_workbench')))
    for product,(department_role,title,_) in PRODUCTS.items():
        if department_role==role:actions.append(dict(label=title,url=task_url(department,product=product)))
    if role not in ('hr','it','real_estate_agent'):
        actions.append(dict(label=DEPARTMENTS[role][0],url=task_url(department)))
    if role=='hr':
        how='Schedule regular HR support for another business to build its recruiting hours and support employees. Each hire uses 60 banked HR minutes to avoid the outside recruitment fee. Use a recruiting project for a specific vacancy.'
    elif role=='maintenance':
        how='Managers prefer qualified home-office crews for routine property repairs and care. Book a specific repair here; materials, paid labor, licenses and available time still apply.'
    elif role=='real_estate_agent':
        how='Managers and directors prefer available in-house agents for planned flips and marketed company property. Prepare a specific closing here; the fee reduction applies after 16 qualified hours of work.'
    elif role in PURPOSES:how=PURPOSES[role]+' Schedule recurring hours for another business, or request a specific work product.'
    else:how='Request a work product for a receiving business. Completion uses paid, qualified staff time; configuring a department alone provides no benefit.'
    return dict(roster=roster,coverage=coverage,covered_count=sum(c['covered'] for c in coverage),
        property_count=len(covered_properties),queue=queue,assignments=assignments,actions=actions,how=how,
        banked=available(world,provider,role) if role in ('hr','accounting','legal') else 0,
        banked_label='Recruiting hours' if role=='hr' else role_label(role)+' hours',
        empty=('The employing company is not operating yet. Open or recover it before relying on shared delivery.' if not any(b.id==provider for b in businesses)
               else 'No active staff in this team. Hire or assign staff before relying on internal delivery.' if not any(e.status=='active' for e in staff)
               else 'No shared work scheduled. Choose a task below. Staff may still support their own employer.' if not queue and not assignments
               else 'Work shares the existing employee schedules. Leave, travel and other commitments reduce delivery.'),
        queue_url=url('home_office',provider)+'#service-queue',
        repairs_url=url('property_workbench',provider))


def support_form(world,department):
    from .ui_workflows import role_label
    names=entity_names(world);staff=[e for e in members(world,department) if e.status=='active' and not credential_gap(world,e)]
    people={p.id:p.name for p in world.people}
    targets=[b for b in world.businesses if any(not support_problem(world,department,e,b) for e in staff)]
    start=staff[0].shift_start*60 if staff else 480
    assignments=[a for a in world.systems.get('assignments',[]) if a['active']]
    if staff:
        # Start after an existing reservation instead of proposing an overlap.
        for a in sorted((a for a in assignments if a['employment_id']==staff[0].id),key=lambda a:a['start_minute']):
            if max(start,a['start_minute'])<min(start+120,a['start_minute']+a['minutes']):start=a['start_minute']+a['minutes']
    result=form('share_department_staff','Schedule '+role_label(department['role'])+' support · '+names[department['provider']],
        'Reserve part of an employee’s existing shift for another business. We create an at-cost staff agreement if needed; an existing agreement keeps its terms. '
        'The recipient reimburses actual assigned payroll and benefits. Leave reduces delivery; time cannot overlap other assignments. No extra employee or outside service fee.',[
        hidden('department_id',department['id']),field('employment_id','Employee','','select',choices({e.id:people[e.person_id]+f' · shift starts {e.shift_start:02}:00' for e in staff})),
        field('target','Receiving business','','select',choices({b.id:b.name for b in targets})),
        field('start_time','Start time',f'{start//60:02}:{start%60:02}','time'),
        field('minutes','Time per scheduled day',120,'select',choices({60:'1 hour',120:'2 hours',180:'3 hours',240:'4 hours'}))],button='Review shared support →')
    result['field_context']={name:dict(required=True,options=next(f['options'] for f in result['fields'] if f['name']==name),empty=message) for name,message in (
        ('employment_id','This department needs an active employee with current credentials.'),
        ('target','No eligible receiving business in county coverage. Edit coverage, or use this team for its own employer.'))}
    result['context_notes']=[dict(text=PURPOSES[department['role']])]
    for emp in staff:
        end=emp.shift_start*60+emp.weekly_hours*60//max(1,len(emp.days))
        reserved=[f"{a['start_minute']//60:02}:{a['start_minute']%60:02}–{(a['start_minute']+a['minutes'])//60:02}:{(a['start_minute']+a['minutes'])%60:02} for {names.get(a['target'],a['target'])}" for a in assignments if a['employment_id']==emp.id]
        result['context_notes'].append(dict(when={'employment_id':emp.id},text=f"{people[emp.person_id]}: shift {emp.shift_start:02}:00–{end//60:02}:{end%60:02}. "+('Already reserved: '+', '.join(reserved)+'.' if reserved else 'No existing shared time reservations.')))
    from .form_context import initial_state
    initial_state(result)
    return result


def prepare(view,world,team_id,action,product):
    """Keep invalid or stale links from silently selecting a different provider."""
    if not team_id:return True
    department=departments(world).get(team_id)
    if not department or action not in ('service_request','share_department_staff','property_work'):
        view['notes'].insert(0,'That shared team or task is no longer available. Choose a team below; no work has been booked.')
        return False
    role=department['role']
    if action=='share_department_staff':
        if role not in PURPOSES:return False
        view['forms'].insert(0,support_form(world,department))
    candidates=[f for f in view['forms'] if f['action']==action and
                (action!='service_request' or next((x['value'] for x in f['fields'] if x['name']=='product'),'')==product)]
    if product and (product not in PRODUCTS or PRODUCTS[product][0]!=role):candidates=[]
    if action=='property_work' and role!='maintenance':candidates=[]
    if not candidates:
        view['notes'].insert(0,'This work is not available for the selected team. Choose one of its task links below.')
        return False
    selected=candidates[0]
    selected['shared_selected']=True
    selected['shared_provider']=department['provider']
    selected['shared_department']=department
    names=entity_names(world)
    if action!='share_department_staff':
        selected['title']+=' · '+names[department['provider']]
        for f in selected['fields']:
            if f['name']=='department':f.update(kind='hidden',value=role)
            if f['name']=='mode':f.update(kind='hidden',value='internal')
            if f['name']=='provider':f.update(value=department['provider'],options=choices({department['provider']:names[department['provider']]}))
            if f['name']=='recipient' and role!='real_estate_agent':
                business_regions={b.id:b.region for b in world.businesses}
                f['options']=[o for o in f['options'] if o['value'] not in business_regions or business_regions[o['value']] in department['regions']]
                # Prefer a covered receiving business other than the employer.
                f['value']=next((o['value'] for o in f['options'] if o['value'] not in ('personal','company',department['provider'])),department['provider'])
            if f['name']=='property_id':
                allowed={p.id for p in world.properties if p.owner in names and p.region in department['regions'] and p.category!='land'}
                f['options']=[o for o in f['options'] if o['value'] in allowed]
                f['value']=f['options'][0]['value'] if f['options'] else ''
    from .ui_workflows import role_label
    view['shared_context']=dict(name=role_label(role),provider=names[department['provider']],
        back=url('home_office',department['provider'])+'#internal-departments',
        edit=url('home_office',department['provider'],action_focus='department_configure',department_id=team_id)+'#task-focus')
    return True
