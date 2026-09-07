"""Effective director oversight follows owned businesses, without copied jobs."""


def coverage(world,overrides=None):
    from .campaign import Campaign
    from .domain import Engine
    owned=Campaign(Engine(world)).controlled
    businesses={b.id:b for b in world.businesses if owned(b.id) and b.status!='closed'}
    employees={e.id:e for e in world.employments if e.status=='active' and e.employer in businesses}
    direct={bid:r for r in world.systems.get('directors',[]) if r['active'] and r['employment_id'] in employees
            for bid in r['business_ids'] if bid in businesses}
    direct.update(overrides or {})
    result={}
    for bid in businesses:
        current=bid;seen=set()
        while current in businesses and current not in seen:
            seen.add(current)
            if current in direct:
                result[bid]=(direct[current],current);break
            b=businesses[current]
            if not b.authority.get('inherit_director',True):break
            current=b.owner
    return result


def assigned(world,record,overrides=None):
    return sorted(bid for bid,(r,_) in coverage(world,overrides).items() if r is record)


def prospective(world,employee,business):
    record=next((r for r in world.systems.get('directors',[]) if r['active'] and r['employment_id']==employee.id),None)
    record=record if record is not None else dict(employment_id=employee.id,active=True,business_ids=[])
    return assigned(world,record,{business.id:record})


def workload(world,employee):
    from .workforce import Workforce
    from .domain import Engine
    bids=sorted({bid for bid,(r,_) in coverage(world).items() if r['employment_id']==employee.id})
    employer=next(b for b in world.businesses if b.id==employee.employer)
    p=Workforce(Engine(world)).effective(employee.employer,employee)[0]
    hours=min(employee.weekly_hours,p.get('overtime_limit',60),employer.authority.get('overtime_cap',60) if employer.authority.get('enabled') else 60)
    available=max(0,hours*60//max(1,len(employee.days))-180)
    executive=any(r['employment_id']==employee.id and r['active'] and r.get('role') in ('home_office_director','division_vp','corporate_services_vp') for r in world.systems.get('directors',[]))
    minutes=30 if executive else 60;maximum=8 if executive else 5
    return dict(businesses=bids,count=len(bids),minutes=len(bids)*minutes,available=available,maximum=maximum,
        overloaded=len(bids)>maximum or len(bids)*minutes>available)


def overloaded(world):
    records={r['employment_id'] for r in world.systems.get('directors',[]) if r['active']}
    loads=[(e,workload(world,e)) for e in world.employments if e.id in records and e.status=='active']
    return [(e,load) for e,load in loads if load['overloaded']]


def reconcile(engine):
    """Log scope changes from acquisitions/closures and initialize old saves on a day step."""
    from .leadership_history import duties,record_change
    from .business_rules import BusinessRules
    rules=BusinessRules(engine);world=engine.world
    cached=world.systems.get('director_scope_history',{})
    active={r['employment_id'] for r in world.systems.get('directors',[]) if r['active']}
    for emp in world.employments:
        if emp.id not in active:continue
        now=duties(world,emp)
        before=cached.get(emp.id)
        if before is None:
            # Existing direct appointments already have their own historical entry.
            roots={bid for r in world.systems.get('directors',[]) if r['active'] and r['employment_id']==emp.id for bid in r['business_ids']}
            before=[dict(row,businesses=[b for b in row['businesses'] if b['id'] in roots]) if row['role']=='director' else row for row in now]
        record_change(rules,emp,before,'Default subsidiary oversight follows the current ownership hierarchy.')
