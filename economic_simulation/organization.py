"""Read-only ownership and position trees, using saved relationships."""
from urllib.parse import urlencode

from .positions import open_positions
from .business_views import entity_names
from .business_models import INDUSTRY_NAMES


def link(page, **args):
    return '/?' + urlencode(dict(page=page, **args))


def node(identity, kind, title, subtitle, url='', **extra):
    return dict(id=identity, kind=kind, title=title, subtitle=subtitle, url=url,
                children=[], meta=[], links=[], **extra)


def attach(nodes, parents, root):
    """Break invalid/cyclic links at leadership rather than hiding positions."""
    warnings=[]
    for identity, item in nodes.items():
        if identity == root['id']:
            continue
        parent=parents.get(identity, root['id'])
        seen={identity}; cursor=parent
        while cursor != root['id'] and cursor in nodes and cursor not in seen:
            seen.add(cursor); cursor=parents.get(cursor, root['id'])
        if parent not in nodes or cursor in seen:
            warnings.append(item['title'] + ': unavailable or circular parent; shown under leadership.')
            parent=root['id']
        nodes[parent]['children'].append(item)
    for item in nodes.values():
        item['children'].sort(key=lambda n:(n['kind']=='property', n['title'].casefold(), n['id']))
    return warnings


def ownership_tree(world, focus='personal'):
    names=entity_names(world)
    if focus not in names:
        focus='personal'
    root=node('personal','owner',world.owner_name,'Personal owner',link('owner',scope='personal'))
    nodes={'personal':root}
    parents={}
    if 'company' in names:
        nodes['company']=node('company','company',names['company'],'Holding company',link('finance',scope='company'))
        parents['company']='personal'
    businesses={b.id:b for b in world.businesses if b.id in names}
    for bid,b in businesses.items():
        item=node(bid,'company',b.name,INDUSTRY_NAMES[b.industry],link('business',business_id=bid,scope=bid))
        item['meta']=[b.status.replace('_',' ').title(), 'Owned by '+names.get(b.owner,'Unknown owner')]
        if bid in world.systems.get('operating_locations',{}):
            item['subtitle']='Operating location · '+INDUSTRY_NAMES[b.industry]
            item['meta'].append('Shared legal obligations with '+names.get(b.owner,b.owner))
        item['links']=[dict(label='Employee hierarchy',url=link('organization',chart='employees',business_id=bid,scope=bid))]
        nodes[bid]=item;parents[bid]=b.owner
    properties=[p for p in world.properties if p.owner in names and p.status not in ('sold','expired')]
    for p in properties:
        identity='property:'+p.id
        item=node(identity,'property',p.name,p.category.title()+' · '+p.kind,link('property',property_id=p.id,scope=p.owner),value=p.value)
        item['meta']=[p.status.replace('_',' ').title(), 'Owned by '+names[p.owner]]
        occupant=names.get(p.occupant) or next((b.name for b in world.businesses if b.id==p.occupant),None)
        tenants=[names.get(lease['tenant'],lease['tenant']) for lease in world.systems.get('leases',[]) if lease['property_id']==p.id and lease['status']=='active' and lease['end_date']>world.date]
        if occupant:
            item['meta'].append('Used by '+occupant)
        elif tenants:
            item['meta'].append('Leased to '+', '.join(sorted(set(tenants))))
        elif p.status=='rented':
            item['meta'].append('Rental tenant: '+(p.tenant or 'Occupied'))
        nodes[identity]=item;parents[identity]=p.owner
    warnings=attach(nodes,parents,root)
    selected=nodes[focus]
    flattened=[]; pending=[selected]
    while pending:
        current=pending.pop();flattened.append(current);pending.extend(current['children'])
    return dict(root=selected,focus=focus,options=[dict(id=k,name=v) for k,v in names.items()],
                companies=sum(n['kind']=='company' for n in flattened),properties=sum(n['kind']=='property' for n in flattened),
                warnings=warnings,count=len(flattened))


def employee_tree(world, business_id=''):
    names=entity_names(world)
    companies=sorted((b for b in world.businesses if b.id in names),key=lambda b:b.name.casefold())
    selected=next((b for b in companies if b.id==business_id),companies[0] if companies else None)
    options=[dict(id=b.id,name=b.name) for b in companies]
    if not selected:
        return dict(root=None,business_id='',options=options,count=0,active=0,joining=0,vacancies=0,warnings=[])
    bid=selected.id
    root=node(bid,'company',selected.name,'Company leadership',link('business',business_id=bid,scope=bid))
    root['meta']=['Owned by '+names.get(selected.owner,'Unknown owner')]
    from .domain import Engine
    from .leadership import Leadership
    director,leader=Leadership(Engine(world)).director(bid,False)
    if leader:
        person=next(p for p in world.people if p.id==leader.person_id)
        root['meta'].append('Director: '+person.name+' · payroll: '+names[leader.employer])
        from .director_scope import coverage
        source=coverage(world)[bid][1]
        if source!=bid:root['meta'].append('Director inherited from '+names[source])
        root['meta'].append('Authority $'+format(director['limit']/100,',.2f')+' per decision and total per day')
        root['links'].append(dict(label='Director employee record',url=link('employee',employment_id=leader.id,scope=leader.employer)))
    nodes={bid:root};parents={};people={p.id:p for p in world.people}
    staff={e.position_id:e for e in world.employments if e.employer==bid and e.status in ('active','joining')}
    counts=dict(active=0,joining=0,vacancies=0)
    for pos in open_positions(world,bid):
        emp=staff.get(pos.id);role=pos.role.replace('_',' ').title()
        if emp:
            person=people[emp.person_id]
            item=node(pos.id,'employee',person.name,role,link('employee',employment_id=emp.id,scope=bid),status=emp.status)
            assignments=[d for d in world.systems.get('directors',[]) if d['active'] and d['employment_id']==emp.id and d['business_ids']]
            if assignments:
                from .leadership_history import LABELS
                designation=LABELS[assignments[0].get('role','director')]
                item['subtitle']=designation if assignments[0].get('role')==pos.role else designation+' · '+role
                for assignment in assignments:
                    from .director_scope import assigned
                    for target in assigned(world,assignment):
                        if target in names:item['links'].append(dict(label='Oversees '+names[target],url=link('business',business_id=target,scope=target)))
            executive=world.systems.get('executives',{}).get(emp.id)
            if executive and executive['active']:
                item['subtitle']=executive['role'].replace('_',' ').title()+' · '+role
                item['links'] += [dict(label='Executive scope: '+names.get(target,target),url=link('business',business_id=target,scope=target)) for target in executive['business_ids']]
            item['meta']=[f'{emp.weekly_hours} h/week', 'Starts '+emp.start_date if emp.status=='joining' else 'Active employee']
            item['links']+=[dict(label='Change reporting line',url=link('workforce',employment_id=emp.id,scope=bid))]
            counts[emp.status]+=1
        else:
            item=node(pos.id,'vacancy','Vacant position',role,link('hiring',business_id=bid,role=pos.role,position_id=pos.id,scope=bid),status='vacant')
            item['meta']=['Reports remain attached to this position']
            counts['vacancies']+=1
        if pos.required_license:
            item['meta'].append('License: '+pos.required_license.replace('_',' '))
        from .employee_reporting import parent_position
        nodes[pos.id]=item;parents[pos.id]=parent_position(world,pos) or bid
    # Context cards show cross-company supervision while keeping employer counts local.
    from .employee_reporting import supervisor, parent_position
    all_staff={e.position_id:e for e in world.employments if e.status=='active' and e.employer in names}
    def context_card(emp):
        person=people[emp.person_id];pos=next(p for p in world.positions if p.id==emp.position_id)
        item=node(pos.id,'employee',person.name,pos.role.replace('_',' ').title(),link('employee',employment_id=emp.id,scope=emp.employer),status=emp.status)
        item['meta']=['Employed and paid by '+names[emp.employer],'Cross-company reporting']
        nodes[pos.id]=item;parents[pos.id]=parent_position(world,pos) or bid
    for emp in all_staff.values():
        parent=supervisor(world,emp)
        if emp.employer!=bid and parent and parent.employer==bid:context_card(emp)
    for _ in range(len(world.positions)):
        missing=[p for p in parents.values() if p not in nodes and p in all_staff]
        if not missing:break
        for pid in missing:context_card(all_staff[pid])
    warnings=attach(nodes,parents,root)
    return dict(root=root,business_id=bid,options=options,count=len(nodes),warnings=warnings,**counts)


def organization_view(world,chart,business_id,focus):
    chart='employees' if chart=='employees' else 'ownership'
    tree=employee_tree(world,business_id) if chart=='employees' else ownership_tree(world,focus)
    return dict(chart=chart,tree=tree)
