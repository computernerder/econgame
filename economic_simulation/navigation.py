"""One management context for related screens, with explicit purchase accounts."""
from urllib.parse import urlencode

from .business_views import entity_names

PAGE_LABELS={'overview':'Home','businesses':'Businesses','business':'Business','people':'Employees','employee':'Employee',
    'hiring':'Hiring','workforce':'Employee terms','portfolio':'Properties','property':'Property','market':'Buy property',
    'business_market':'Buy a business','finance':'Finances','financing':'Loans & taxes','home_office':'Home office',
    'services':'Service benefits & reports','property_workbench':'Property repairs & projects','property_services':'Property services',
    'spaces':'Spaces & leases','commercial_contracts':'Contracts & purchasing','operations_center':'Operations & recovery',
    'management':'Management overview','inbox':'Decision inbox','activity':'Activity','organization':'Organization',
    'policies':'Policies & benefits','regions':'Counties & community','expansion':'Start or expand a business',
    'settings':'Campaign settings','games':'My games','owner':'Personal finances','forecast':'Forecast','scorecard':'Scorecard',
    'franchises':'Brands & franchises','developer':'Developer tools'}
PROPERTY_PAGES={'portfolio','property','market','spaces','property_workbench','property_services'}
TEAM_PAGES={'people','employee','workforce','hiring'}
SERVICE_PAGES={'home_office','services'}


def url(page,scope='personal',**args):
    return '/?' + urlencode(dict(page=page,scope=scope,**args))


def resolve_context(world,page,scope,business_id='',employment_id='',property_id='',chart='ownership',org_root='',all_properties=False):
    names=entity_names(world)
    owned={b.id:b for b in world.businesses if b.id in names}
    scope=scope if scope in names else 'personal'
    notice=''
    if page=='business' and not business_id and scope in owned:business_id=scope
    if page=='business' and not any(b.id==business_id for b in world.businesses):
        page='businesses';business_id='';notice='That business is unavailable. Choose a business below.'
    if page=='employee':
        emp=next((e for e in world.employments if e.id==employment_id and e.employer in owned),None)
        if not emp or emp.status not in ('active','joining'):
            page='people';business_id=emp.employer if emp else scope if scope in owned else ''
            notice='That employee is no longer available in the active team. Choose an employee below.'
    if page=='property' and not any(p.id==property_id and (p.status=='market' or p.owner in names and p.status not in ('sold','expired')) for p in world.properties):
        page='portfolio';notice='That property is no longer available here. Your current properties are shown below.'
    if page in ('owner','businesses','management'):
        scope='personal'
    elif page in ('business','hiring') and business_id in owned:
        scope=business_id
    elif page in ('employee','workforce'):
        emp=next((e for e in world.employments if e.id==employment_id and e.employer in owned and e.status in ('active','joining')),None)
        if emp:
            scope=business_id=emp.employer
    elif page in ('property','property_workbench'):
        prop=next((p for p in world.properties if p.id==property_id),None)
        # Unowned market listings retain the explicitly selected buyer.
        if prop and prop.owner in names and prop.status not in ('sold','expired'):
            scope=prop.owner
    elif page=='people':
        if business_id in owned:
            scope=business_id
        elif scope in owned:
            business_id=scope
        else:
            business_id='';scope='personal'
    elif page=='organization':
        if chart=='employees':
            if business_id in owned:
                scope=business_id
            elif scope in owned:
                business_id=scope
            elif owned:
                scope=business_id=min(owned.values(),key=lambda b:b.name.casefold()).id
        else:
            org_root=org_root if org_root in names else scope
            scope=org_root
    if page=='portfolio' and all_properties:
        scope='personal'
    if page=='overview' and scope in owned:
        page='business';business_id=scope
    return dict(page=page,scope=scope,business_id=business_id,org_root=org_root,notice=notice)


def navigation_view(world,page,scope,business_id='',chart='ownership',all_properties=False):
    names=entity_names(world)
    owned={b.id:b for b in world.businesses if b.id in names}
    current=owned.get(scope)
    def destination(target):
        from .campaign_views import PAGES
        if page=='management':return url('management','personal')+('#policy-'+target if target in owned else '')
        if page in ('portfolio','property'):
            return url('portfolio',target)
        if page in TEAM_PAGES:
            if target=='company':return url('overview',target)
            return url('people',target,business_id=target if target in owned else '')
        if page=='organization':
            target_chart=chart if target in owned else 'ownership'
            return url('organization',target,chart=target_chart,business_id=target if target in owned and target_chart=='employees' else '',org_root=target)
        if page in PAGES or page in ('market','business_market','finance','activity','games'):
            return url(page,target)
        return url('business',target,business_id=target) if target in owned else url('overview',target)
    choices=[]
    for identity,name in names.items():
        if identity=='personal':
            category='Personal';description='Personal portfolio'
        elif identity=='company':
            category='Holding company';description=name+' · Holding company'
        else:
            category='Businesses';description=name
            owner=owned[identity].owner
            if owner not in ('personal',None):description+=' · owned by '+names.get(owner,'another company')
        choices.append(dict(id=identity,label=description,category=category,url=destination(identity)))
    section=('team' if page in TEAM_PAGES or page=='organization' and chart=='employees' else
             'properties' if page in PROPERTY_PAGES else 'services' if page in SERVICE_PAGES else
             'finance' if page in ('finance','financing') else 'ownership' if page=='organization' else 'business')
    tabs=[]
    if current or scope=='company':
        tabs=[dict(key='business',label='Operations' if current else 'Overview',url=url('business',scope,business_id=scope) if current else url('overview',scope)),
              dict(key='properties',label='Properties',url=url('portfolio',scope)),
              dict(key='finance',label='Finances',url=url('finance',scope))]
        if current:
            tabs.insert(1,dict(key='team',label='Team',url=url('people',scope,business_id=scope)))

    shared_page=page in ('organization','home_office')
    shared=[]
    if current or scope=='company':
        shared=[dict(label='Organization · ownership chart',url=url('organization',scope,chart='ownership',org_root=scope))]
        if current:shared.append(dict(label='Home Office · shared services',url=url('home_office',scope)))
    if shared_page:tabs=[]
    # Fleet-wide directories explicitly leave a company; company tabs keep it.
    global_page=page in ('businesses','management') or page=='portfolio' and all_properties
    if global_page:tabs=[]
    trail=[];cursor=current.owner if current else 'personal' if scope=='company' else None
    while cursor and cursor in names and cursor not in [x['id'] for x in trail]:
        trail.insert(0,dict(id=cursor,name=names[cursor],url=url('business',cursor,business_id=cursor) if cursor in owned else url('overview',cursor)))
        cursor=owned[cursor].owner if cursor in owned else 'personal' if cursor=='company' else None
    primary=('portfolio' if page in PROPERTY_PAGES-{'market','spaces'} else 'people' if page in TEAM_PAGES else
             'businesses' if page=='business' else page)
    if current and tabs and not global_page and page in ('business','people','employee','hiring','workforce','portfolio','property','finance'):primary='businesses'
    related=[dict(page=p,label=PAGE_LABELS[p],url=url(p,scope),active=p==page) for p in
        ('operations_center','home_office','property_workbench','commercial_contracts','property_services')]
    return dict(shared=shared,shared_page=shared_page,primary=primary,page_label=PAGE_LABELS.get(page,page.replace('_',' ').title()),related=related,
                choices=choices,current=current.name if current else names[scope],tabs=tabs,section=section,trail=trail,
                context='All businesses' if page=='businesses' else 'All properties' if all_properties else 'Managing business' if current else 'Holding company' if scope=='company' else 'Personal portfolio',
                buyer=page in ('market','business_market') or page=='business' and business_id not in owned,global_page=global_page)
