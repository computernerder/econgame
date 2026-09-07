"""Read-only routes from blocked actions to existing decisions and controls."""
from .business_views import entity_names
from .navigation import url


def delegation_link(world, request_id):
    names=entity_names(world)
    request=next((r for r in world.systems.get('management_requests',[]) if r['id']==request_id and r['business_id'] in names and r['status'] in ('open','deferred')),None)
    if not request:return None
    bid=request['business_id']
    if request['action'] in ('recover_invoice','write_off_invoice') or (request['action']=='service_request' and request['args'].get('matter')=='collection'):
        return dict(label='Change collection limits · '+names[bid],url=url('management')+'#routine-policy-'+bid)
    return dict(label='Change delegated limits · '+names[bid],url=url('management',authority_business=bid)+'#authority-limits-'+bid)


def approval_links(world):
    from .decision_inbox import items
    rows=[r for r in items(world) if r['kind']=='management' and r['status']=='open']
    links=[dict(label='Review approval · '+r['entity_name'],url=url('inbox')+'#'+r['id']) for r in rows[:3]]
    if len(rows)>3:links.append(dict(label=f'View all {len(rows)} approvals in inbox',url=url('inbox')))
    return links


def recovery_links(world, message, args=None):
    """Suggestions never execute a command or imply that funding is available.

    Error text selects a destination category; record identifiers are accepted
    only from the current controlled world, never interpolated from the text.
    Unrecognized errors retain an inbox/activity fallback.
    """
    args=args or {};names=entity_names(world);text=message.casefold()
    scope=next((args[k] for k in ('business_id','entity','recipient','scope') if isinstance(args.get(k),str) and args[k] in names),'personal')
    request=next((r for r in world.systems.get('management_requests',[]) if r['id']==args.get('request_id') and r['business_id'] in names),None)
    if request:scope=request['business_id']
    emp=next((e for e in world.employments if e.id==args.get('employment_id') and e.employer in names),None)
    if emp:scope=emp.employer
    position=next((p for p in world.positions if p.id==args.get('position_id') and p.business_id in names),None)
    if position:scope=position.business_id
    links=[]
    if args.get('department_id') in world.systems.get('departments',{}):
        department=world.systems['departments'][args['department_id']]
        if department['provider'] in names:
            links.append(dict(label='Review this shared team and assignments',url=url('home_office',department['provider'])+'#internal-departments'))
            links.append(dict(label='Change this department’s coverage and staff',url=url('home_office',department['provider'],action_focus='department_configure',department_id=department['id'])+'#task-focus'))
    office=next((b for b in world.businesses if b.id==args.get('office_id') and b.id in names and b.industry=='office'),None)
    if office:
        links.append(dict(label='Review '+office.name+' funding',url=url('business',office.id,business_id=office.id)+'#business-capital'))
    def add(label,page,**params):links.append(dict(label=label,url=url(page,scope,**params)))
    if any(t in text for t in ('invoice','customer recovery','customer collection')):
        links.append(dict(label='Review customer collections',url=url('operations_center',scope)+'#customer-collections'))
    if any(t in text for t in ('revenue','stream','kit','specialty','equipment setup')) and scope not in ('personal','company'):
        links.append(dict(label='Manage revenue streams and equipment kits',url=url('business',scope,business_id=scope)+'#revenue-kits'))
    if 'refresh' in text or 'out of date' in text:
        return [dict(label='Refresh this screen',url='',behavior='refresh')]
    if 'pause time' in text:
        return [dict(label='Show pause control',url='',behavior='time')]
    if any(t in text for t in ('approval','authority','delegat','director','manager','limit','reserve')):
        links.extend(approval_links(world))
        links.append(dict(label='Review management policies',url=url('management')+('#policy-'+scope if scope not in ('personal','company') else '')))
    if any(t in text for t in ('cash','fund','afford','payroll','arrears','overdue','unpaid','loan','debt','tax','insolven')):
        if scope not in ('personal','company'):
            links.append(dict(label='Review business funding',url=url('business',scope,business_id=scope)+'#business-capital'))
        else:add('Review capital and personal funds','owner')
        add('Review unpaid obligations','operations_center')
        add('Loans and taxes','financing')
    if any(t in text for t in ('employee','staff','qualification','qualified','credential','license','scheduled','hours','vacan')):
        if emp:add('Review employee and schedule','employee',employment_id=emp.id)
        from .business_models import INDUSTRY_ROLES
        from .positions import position_open
        business=next((b for b in world.businesses if b.id==scope),None)
        role=position.role if position else args.get('role')
        if business and role in INDUSTRY_ROLES[business.industry]:
            add('Review role requirements and candidates','hiring',business_id=scope,role=role,
                position_id=position.id if position and position_open(world,position) else '')
        add('Review staffing','people',business_id=scope if scope not in ('personal','company') else '')
    if any(t in text for t in ('repair','condition','roof','renovat','maintenance','tenant','lease','deposit','closing','lot','construction','building design')):
        add('Review property work and leases','property_workbench')
    if any(t in text for t in ('consent','legal','restriction','contract','supplier')):
        add('Review contracts and legal work','commercial_contracts')
    if any(t in text for t in ('service','capacity','department','queue')):
        add('Review service capacity','home_office')
    # Keep a direct owned property link when the rejected command identifies it.
    prop=next((p for p in world.properties if p.id==args.get('property_id') and p.owner in names and p.status not in ('sold','expired')),None)
    if prop:
        links.insert(0,dict(label='Open '+prop.name,url=url('property',prop.owner,property_id=prop.id)))
        if any(t in text for t in ('repair','condition','roof','renovat','maintenance','qualified','license','material')):
            links.insert(0,dict(label='Review work for '+prop.name,url=url('property_workbench',prop.owner,property_id=prop.id,
                action_focus='develop_property' if prop.category=='land' else 'property_work',work_system=args.get('system',''))+'#task-focus'))
    if not links:links=[dict(label='Review decision inbox',url=url('inbox')),dict(label='Review recent activity',url=url('activity'))]
    return list({link['url']:link for link in links}.values())[:5]


def progress_links(world, progress):
    if progress.get('running') or not progress.get('blocked'):return []
    if progress.get('blocker')=='approval':
        from .time_off import blockers
        if blockers(world):return [dict(label='Review time-off requests in decision inbox',url=url('inbox'))]+approval_links(world)
        return approval_links(world) or [dict(label='Review decision inbox',url=url('inbox'))]
    links=recovery_links(world,progress.get('reason',''))
    inbox=dict(label='Review decision inbox',url=url('inbox'))
    if not any(link['url']==inbox['url'] for link in links):links.insert(0,inbox)
    return links
