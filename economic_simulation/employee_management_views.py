"""Employee management read models; rendering never changes balances or policies."""
from datetime import date,timedelta
from .domain import Engine, GAME_RULES
from .business_rules import BusinessRules
from .workforce import Workforce
from .campaign import Campaign
from .employee_reporting import supervisor, options
from .time_off import KINDS, balances, requests, coverage, absent, active_request, policy, review_status


def view(world,business_id='',employment_id=''):
    rules=BusinessRules(Engine(world));wf=Workforce(rules.e);controlled=Campaign(rules.e).controlled
    staff=[e for e in world.employments if controlled(e.employer) and (e.status in ('active','joining') or e.id==employment_id)]
    if business_id:staff=[e for e in staff if e.employer==business_id]
    companies={b.id:b.name for b in world.businesses if controlled(b.id)}
    employee=next((e for e in staff if e.id==employment_id),None)
    selected=[employee] if employee else staff
    today=date.fromisoformat(world.date);end=(today+timedelta(days=13)).isoformat()
    rows=[];scheduled_hours=lost_hours=0
    for emp in selected:
        for i in range(1,15):
            day=today+timedelta(days=i)
            if day.weekday() not in emp.days or emp.start_date>day.isoformat():continue
            scheduled_hours+=emp.weekly_hours/len(emp.days)
            values=wf.effective(emp.employer,emp,on=day.isoformat())[0]
            holiday=values['paid_holidays'] and (day.month,day.day) in ((1,1),(7,4),(12,25))
            if absent(world,emp,day.isoformat()) or holiday:lost_hours+=emp.weekly_hours/len(emp.days)
        for request in requests(world,emp):
            rows.append(dict(request,name=rules.person(emp.person_id).name,company=companies[emp.employer],
                label=KINDS[request['kind']],impact=coverage(world,emp,request),
                review=review_status(world,request) if request['status']=='pending' and emp.status=='active' else None,
                url=f'/?page=employee&employment_id={emp.id}&scope={emp.employer}#employee-time-off'))
    data=dict(requests=sorted(rows,key=lambda r:(r['status']!='pending',r['start'],r['id']),reverse=False),
        pending=sum(r['status']=='pending' for r in rows),away=sum(absent(world,e) for e in selected),
        available_hours=round(scheduled_hours-lost_hours,1),lost_hours=round(lost_hours,1),through=end,
        companies=companies,business_id=business_id,employee=None,kinds=KINDS)
    if employee:
        emp=employee;person=rules.person(emp.person_id);values,sources,locked=wf.effective(emp.employer,emp)
        parent=supervisor(world,emp)
        leave=active_request(world,emp)
        data['employee']=dict(id=emp.id,status=emp.status,name=person.name,employer=emp.employer,company=companies[emp.employer],
            banks=balances(world,emp),benefits=values,locked=locked,policy_sources=sources,benefit_cost=wf.benefit_cost(emp,values),
            supervisors=options(world,emp),supervisor_id=parent.id if parent else '',
            supervisor_label=(rules.person(parent.person_id).name+' · '+companies.get(parent.employer,parent.employer)) if parent else 'Owner / company leadership',
            policy=policy(world,emp.employer),start=(today+timedelta(days=1)).isoformat(),end=(today+timedelta(days=7)).isoformat(),
            status_label=KINDS[leave['kind']]+' until '+leave['end'] if leave else 'On leave' if absent(world,emp) else emp.status.title(),
            medical=list(GAME_RULES['medical']),dental=list(GAME_RULES['dental']))
    return data


def benefit_action(engine,args):
    from .campaign import integer,flag
    from .domain import RuleError
    rules=BusinessRules(engine);emp=rules.contract(args.get('employment_id',''));rules.company(emp.employer)
    wf=Workforce(engine);_,_,locked=wf.effective(emp.employer,emp)
    allowed={'medical','dental','employer_share','retirement_percent','vacation_days','sick_days','floating_holidays','paid_holidays'}
    from .workforce import LIMITS
    if flag(args.get('inherit')):
        for key in allowed:emp.policy_overrides.pop(key,None)
        return 'Individual benefit overrides removed. Employer and parent policies apply prospectively.'
    updates={}
    for key in allowed:
        if key not in args:continue
        if key in locked:raise RuleError('The parent policy locks '+key.replace('_',' ')+'. Edit that policy instead.')
        value=args[key]
        if key in ('medical','dental'):
            if value not in GAME_RULES[key]:raise RuleError('Choose an available '+key+' plan.')
        elif key=='paid_holidays':value=flag(value)
        else:value=integer(value,*LIMITS[key])
        updates[key]=value
    emp.policy_overrides.update(updates)
    rules.record(emp.person_id,'Individual benefits updated prospectively. Existing leave reservations and earned payroll retained.')
    return 'Benefits updated. Costs apply to future payroll. Vacation accrues monthly; sick and floating entitlements reset each January. Existing banks are not immediately refilled.'
