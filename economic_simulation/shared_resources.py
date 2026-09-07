"""Read-only team discovery and eligibility for ongoing shared support."""
from .business_views import entity_names
from .business_models import INDUSTRY_ROLES
from .specialists import LICENSES, PURPOSES


def departments(world):
    names=entity_names(world)
    result={key:d for key,d in world.systems.get('departments',{}).items() if d['provider'] in names}
    from .internal_property_services import agent_department
    for b in world.businesses:
        if b.id in names:
            department=agent_department(world,b)
            if department:result.setdefault(department['id'],department)
    return result


def members(world,department):
    positions={p.id:p for p in world.positions}
    return [e for e in world.employments if e.employer==department['provider']
            and e.status in ('active','joining') and positions[e.position_id].role==department['role']
            and (not department['staff'] or e.id in department['staff'])]


def credential_gap(world,emp):
    position=next(p for p in world.positions if p.id==emp.position_id)
    person=next(p for p in world.people if p.id==emp.person_id)
    for credential in (position.required_license,LICENSES.get(position.role)):
        if credential and person.licenses.get(credential,'')<world.date:
            return 'Current '+credential.replace('_',' ')+' license needed'
    return ''


def support_problem(world,department,emp,target):
    if department['role'] not in PURPOSES:return 'This team delivers specific jobs. Request a project instead.'
    if not emp or emp not in members(world,department) or emp.status!='active':return 'Choose an active employee assigned to this department.'
    gap=credential_gap(world,emp)
    if gap:return gap+'.'
    source=next((b for b in world.businesses if b.id==department['provider']),None)
    if not source or source.status!='operating':return 'The employing company must be operating.'
    if not target or target.id not in entity_names(world) or target.status!='operating':return 'Choose an operating business you own.'
    if target.id==source.id:return 'Staff already support their own employer. Choose another business.'
    if department['role'] not in INDUSTRY_ROLES[target.industry]:return 'The receiving business does not use this support role.'
    if target.region not in department['regions']:return 'Add the receiving county to this department’s coverage first.'
    return ''
