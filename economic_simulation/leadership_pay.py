"""Prospective pay for additional leadership responsibility, paid by one employer."""
from .domain import RuleError
from .money_display import money

BASE={'director':15,'home_office_director':15,'division_vp':25,'corporate_services_vp':25}


def scope(world,emp):
    record=world.systems.get('executives',{}).get(emp.id,{})
    if record.get('active'):return record['role'],record['business_ids']
    from .director_scope import coverage
    businesses=sorted(bid for bid,(r,_) in coverage(world).items() if r['employment_id']==emp.id)
    director=next((r for r in world.systems.get('directors',[]) if r['active'] and r['employment_id']==emp.id),{})
    return director.get('role','director'),businesses


def quote(world,emp,role,businesses):
    count=len(set(businesses))
    points=BASE[role]+5*(count-1) if count else 0
    credited=world.systems.get('leadership_pay',{}).get(emp.id,{}).get('credited_points',0)
    percent=max(0,points-credited)
    proposed=emp.salary+(emp.salary*percent+99)//100
    rate=None
    if percent and emp.compensation.get('pay_basis')=='hourly':
        denominator=emp.weekly_hours*52
        if denominator<=0:raise RuleError('Set scheduled hours before appointing an hourly employee.')
        rate=max(emp.compensation.get('hourly_rate',0),(proposed*12+denominator-1)//denominator)
        proposed=rate*denominator//12
    return dict(current=emp.salary,salary=proposed,increase=proposed-emp.salary,annual=(proposed-emp.salary)*12,
                percent=percent,points=points,credited=credited,hourly_rate=rate,role=role,count=count)


def apply(rules,emp,q):
    if q['salary']>100000000:raise RuleError('This appointment would exceed the maximum monthly base salary. Review compensation first.')
    person=rules.person(emp.person_id);employer=rules.company(emp.employer)
    if q['increase']:
        emp.salary=q['salary']
        if q['hourly_rate'] is not None:emp.compensation['hourly_rate']=q['hourly_rate']
        detail=(f"{person.name}: leadership responsibility raise of {q['percent']}%, "
                f"{money(q['current'])} → {money(q['salary'])}/month; +{money(q['increase'])}/month "
                f"(+{money(q['annual'])}/year base pay), paid by {employer.name}. "
                "Employer payroll taxes and applicable overtime are additional. Future payroll changes; accrued wages and the annual review date are unchanged.")
        rules.record(person.id,detail)
        rules.e.event('Leadership pay increased',detail)
    else:detail=f"No additional raise: this employee has already been compensated for this level of responsibility. {employer.name} continues payroll at {money(emp.salary)}/month."
    world=rules.w
    world.systems.setdefault('leadership_pay',{})[emp.id]=dict(credited_points=max(q['credited'],q['points']),reviewed=world.date,role=q['role'],business_count=q['count'])
    for request in world.systems.get('management_requests',[]):
        if request['key']=='leadership-pay:'+emp.id and request['status'] in ('open','deferred'):
            request.update(status='resolved',resolved=world.date,outcome=detail)
    return detail


def resolve_if_unneeded(world,emp):
    role,businesses=scope(world,emp)
    if emp.status=='active' and businesses and quote(world,emp,role,businesses)['increase']:return
    for request in world.systems.get('management_requests',[]):
        if request['key']=='leadership-pay:'+emp.id and request['status'] in ('open','deferred'):
            request.update(status='resolved',resolved=world.date,outcome='No uncompensated active leadership duties remain.')
