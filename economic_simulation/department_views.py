"""Visible department management and saved settings, without changing services."""
from .business_views import entity_names
from .navigation import url
from .ui_workflows import role_label


def prepare(view,world,scope,department_id=''):
    names=entity_names(world)
    businesses={b.id:b for b in world.businesses if b.id in names}
    people={p.id:p.name for p in world.people};positions={p.id:p for p in world.positions}
    from .shared_resources import departments as catalog
    from .shared_team_views import describe
    departments=catalog(world)
    rows=[]
    for key,d in departments.items():
        rows.append(dict(id=key,name=role_label(d['role']),provider=names[d['provider']],
            staff=', '.join(people[e.person_id] for e in world.employments if e.id in d['staff']) or 'All qualified role staff',
            counties=', '.join(d['regions']),industries=', '.join(d['industries']),tools=d['tools'],
            capacity=d.get('last_capacity',0),used=d.get('last_used',0),unused=max(0,d.get('last_capacity',0)-d.get('last_used',0)),
            edit=url('home_office',d['provider'],action_focus='department_configure',department_id=key)+'#task-focus',
            hire=url('hiring',d['provider'],business_id=d['provider'],role=d['role']),**describe(world,d)))
    view['department_rows']=sorted(rows,key=lambda r:(r['provider'],r['name']))
    view['department_add_url']=url('home_office',scope,action_focus='department_configure')+'#task-focus'
    form=next(f for f in view['forms'] if f['action']=='department_configure')
    fields={f['name']:f for f in form['fields']}
    valid=not department_id or department_id in departments
    if not valid:view['notes'].insert(0,'That department is no longer available. Choose an existing department below; no settings have been changed.')
    selected=departments.get(department_id)
    if selected:
        fields['provider']['value']=selected['provider'];fields['department']['value']=selected['role']
        for name in ('provider','department'):
            fields[name]['options']=[o for o in fields[name]['options'] if o['value']==fields[name]['value']]
        form['title']='Edit '+role_label(selected['role'])+' · '+names[selected['provider']]
    else:form['title']='Configure an internal department'
    provider=fields['provider']['value'] or next(iter(businesses),'')
    role=fields['department']['value'];fields['provider']['value']=provider
    fields['tools']['minimum']=0 if provider and businesses[provider].industry=='office' and role=='real_estate_agent' else 1
    saved=departments.get(provider+':'+role,{})
    settings=dict(staff=list(saved.get('staff',[])),tools=saved.get('tools',1),
        regions=','.join(saved.get('regions',[businesses[provider].region] if provider else [])),
        industries=','.join(saved.get('industries',[businesses[provider].industry] if provider else [])),leader=saved.get('leader',''))
    for name,value in settings.items():
        if name in fields:fields[name]['value']=value
    form['fields'].append(dict(name='leader',label='',kind='hidden',value=settings['leader'],options=[],minimum=None,maximum=None))
    staff=[dict(value=e.id,label=people[e.person_id]+(' ('+e.status+')' if e.status!='active' else ''),provider=e.employer,role=positions[e.position_id].role,status=e.status)
        for e in world.employments if e.employer in businesses]
    fields['staff']['label']='Assigned employees (leave unselected for all qualified role staff)'
    fields['staff']['options']=[s for s in staff if s['provider']==provider and s['role']==role and (s['status'] in ('active','joining') or s['value'] in settings['staff'])]
    form['description']='Choose the employing company and service department, then assign its staff, tools and coverage. Existing departments load their saved settings. Home-office agents can work with basic office tools at level 0. Added tool levels cost $500 each; unchanged levels have no charge. Qualified staff and queued work are needed to deliver services.'
    form['button']='Review department settings →'
    form['department_context']=dict(departments=departments,staff=staff,
        businesses={key:dict(name=b.name,region=b.region,industry=b.industry) for key,b in businesses.items()})
    form['department_status']=('Editing saved ' if saved else 'New ')+role_label(role)+' department'+(' · '+names[provider] if provider else '')
    form['department_hire']=url('hiring',provider,business_id=provider,role=role) if provider else ''
    view['department_form']=form
    return valid
