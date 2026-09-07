"""Read current leadership duties and record actual career changes."""
from .money_display import money

LABELS={'director':'Director','home_office_director':'Home Office Director',
        'division_vp':'Division VP','corporate_services_vp':'VP of Corporate Services'}


def duties(world,emp):
    if emp.status!='active':return []
    from .director_scope import assigned
    records=[dict(r,role=r.get('role','director'),business_ids=assigned(world,r)) for r in world.systems.get('directors',[])
             if r['employment_id']==emp.id and r['active'] and r['business_ids']]
    executive=world.systems.get('executives',{}).get(emp.id)
    if executive and executive['active'] and executive['business_ids']:records.append(executive)
    names={b.id:b.name for b in world.businesses}
    return [dict(role=r['role'],label=LABELS[r['role']],limit=r['limit'],
                 businesses=[dict(id=bid,name=names.get(bid,bid)) for bid in sorted(r['business_ids'])]) for r in records if r['business_ids']]


def describe(rows):
    return '; '.join(row['label']+' for '+', '.join(b['name'] for b in row['businesses'])+
                    ' (delegated limit '+money(row['limit'])+')' for row in rows)


def record_change(rules,emp,before,reason=''):
    after=duties(rules.w,emp)
    if any(r['employment_id']==emp.id for r in rules.w.systems.get('directors',[])):
        rules.w.systems.setdefault('director_scope_history',{})[emp.id]=after
    if before==after:return
    if not before:detail='Appointed '+describe(after)+'.'
    elif not after:detail='Leadership duties ended: '+describe(before)+'.'
    else:detail='Leadership duties changed: '+describe(before)+' → '+describe(after)+'.'
    if reason:detail+=' '+reason
    employer=rules.company(emp.employer,owned=False)
    detail+=' Employer: '+employer.name+'. Monthly base pay: '+money(emp.salary)+'.'
    rules.record(emp.person_id,detail)
