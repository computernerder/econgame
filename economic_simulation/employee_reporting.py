"""One primary supervisor per employment; payroll and authority remain separate."""
from .campaign import Campaign
from .domain import RuleError


def supervisor(world, emp):
    staff = {e.id:e for e in world.employments if e.status=='active'}
    if emp.supervisor_id:return staff.get(emp.supervisor_id)
    pos = next(p for p in world.positions if p.id==emp.position_id)
    return next((e for e in staff.values() if e.position_id==pos.reports_to),None)


def parent_position(world, pos):
    emp = next((e for e in world.employments if e.position_id==pos.id and e.status in ('active','joining')),None)
    if emp and emp.supervisor_id:
        parent = next((e for e in world.employments if e.id==emp.supervisor_id and e.status=='active'),None)
        return parent.position_id if parent else None
    return pos.reports_to


def options(world, emp):
    from .business_views import entity_names
    names=entity_names(world);people={p.id:p.name for p in world.people}
    return {e.id:people[e.person_id]+' · '+names[e.employer] for e in world.employments
            if e.status=='active' and e.employer in names and e.person_id!=emp.person_id}


def change(rules, emp, target):
    pos=rules.position(emp.position_id)
    if not target:emp.supervisor_id=None;pos.reports_to=None
    elif target in {e.id for e in rules.w.employments}:
        parent=rules.contract(target)
        if parent.status!='active' or parent.person_id==emp.person_id:raise RuleError('Choose another active employee as supervisor.')
        rules.company(parent.employer)
        emp.supervisor_id=parent.id;pos.reports_to=None
    else:
        # Existing saved forms and commands may identify a position, including a vacancy.
        parent=rules.position(target)
        if parent.business_id!=emp.employer:raise RuleError('Choose the named employee for a cross-company reporting relationship.')
        emp.supervisor_id=None;pos.reports_to=target
    rules.validate()
    rules.record(emp.person_id,'Primary reporting relationship updated. Payroll and delegated authority remain with their existing accounts and policies.')
    return 'Reporting relationship updated. No employee transfer, duplicated salary or spending authority was created.'


def reconcile(engine):
    controlled=Campaign(engine).controlled
    staff={e.id:e for e in engine.world.employments if e.status=='active'}
    for emp in engine.world.employments:
        parent=staff.get(emp.supervisor_id)
        if emp.supervisor_id and (not parent or not controlled(emp.employer) or not controlled(parent.employer)):
            emp.supervisor_id=None
            person=next(p for p in engine.world.people if p.id==emp.person_id)
            person.history.append(dict(date=engine.world.date,event='Primary supervisor is no longer available in the owned group; reporting returned to company leadership.'))
