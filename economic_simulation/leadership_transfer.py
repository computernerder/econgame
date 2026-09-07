"""Move an existing employee into home-office leadership without recreating them."""
import copy
from .domain import Engine,RuleError
from .campaign import Campaign
from .business_rules import BusinessRules
from .business_models import Position
from .authority import cash_forecast
from .leadership_history import LABELS,duties,record_change
from .leadership_pay import quote,apply

ROLES=('home_office_director','division_vp','corporate_services_vp')


def options(world,emp):
    c=Campaign(Engine(world))
    return [dict(id=b.id,name=b.name,cash=world.cash(b.id)) for b in world.businesses
            if b.industry=='office' and b.status=='operating' and c.controlled(b.id)]


def _apply(engine,args):
    rules=BusinessRules(engine);w=engine.world;s=w.systems;c=Campaign(engine)
    emp=rules.contract(args.get('employment_id',''));old=rules.company(emp.employer)
    if emp.status!='active':raise RuleError('Choose an active employee to promote.')
    office=rules.company(args.get('office_id',''));role=args.get('role','home_office_director')
    if office.industry!='office' or office.status!='operating':raise RuleError('Choose an operating home-office company. Create or finish opening a home office first.')
    if role not in ROLES:raise RuleError('Choose Home Office Director, Division VP or VP of Corporate Services.')
    if any(a['active'] and a['employment_id']==emp.id for a in s.get('assignments',[])):
        raise RuleError('End this employee’s shared-service assignments before moving their employment to the home office.')
    if any(emp.id in d['staff'] for d in s.get('departments',{}).values()):
        raise RuleError('Remove this employee from named department staffing before changing their role. Review home-office service capacity first.')
    if s.get('executives',{}).get(emp.id,{}).get('active'):
        raise RuleError('This employee already has a separate executive appointment. This transfer is for managers and directors; review their executive appointment first.')
    records=s.setdefault('directors',[])
    record=next((r for r in records if r['employment_id']==emp.id and r['active']),None)
    roots=set(record['business_ids'] if record else [old.id])|{office.id}
    if any(r is not record and r['active'] and roots.intersection(r['business_ids']) for r in records):
        raise RuleError('Another director is explicitly assigned to a business in this promotion. Review those director appointments first.')
    pos=rules.position(emp.position_id);previous=duties(w,emp)
    if old.id==office.id and pos.role==role and record and record.get('role')==role:
        raise RuleError('This employee already holds that home-office leadership position.')
    supervisor=args.get('supervisor_id','')
    if supervisor:
        parent=rules.contract(supervisor);rules.company(parent.employer)
        if parent.status!='active' or parent.id==emp.id:raise RuleError('Choose another active employee as the primary supervisor.')
    # The same authority key preserves saved contracts, parent links and spending.
    if not record:
        from .manager_defaults import director_limit
        record=dict(employment_id=emp.id,active=True,limit=director_limit(old),day=w.date,spent=0,business_ids=[])
        records.append(record)
    record.update(role=role,business_ids=sorted(roots),employer=office.id,
                  authority_key='director:'+emp.id,appointed=record.get('appointed',w.date))
    old_position=emp.position_id
    number=w.next_position_id;w.next_position_id+=1
    new_position=Position('position-new-'+str(number),office.id,role)
    w.positions.append(new_position)
    annual_baseline=max(emp.start_date,old.acquired_on or emp.start_date,emp.last_pay_review or emp.start_date)
    past=s.get('employment_transfers',{}).get(emp.id,[])
    if past:annual_baseline=max(emp.start_date,past[-1]['review_baseline'],emp.last_pay_review or emp.start_date)
    emp.employer=office.id;emp.position_id=new_position.id;emp.supervisor_id=supervisor or None
    from .director_scope import workload
    load=workload(w,emp)
    if load['overloaded']:raise RuleError('This executive scope exceeds scheduled capacity: '+str(load['count'])+' businesses. Allow 30 minutes per business plus three hours for leadership work; maximum eight businesses.')
    q=quote(w,emp,role,load['businesses']);apply(rules,emp,q)
    # A title change inside the office should not leave an obsolete VP vacancy.
    if old.id==office.id and pos.role in ROLES:
        s.setdefault('closed_positions',{})[old_position]=dict(date=w.date,business_id=old.id,reason='Leadership role changed')
        for child in w.positions:
            if child.reports_to==old_position:child.reports_to=new_position.id
    for request in s.get('time_off_requests',[]):
        if request['employment_id']==emp.id and request['status'] in ('pending','approved'):
            request['entity']=office.id
            request['history'].append(dict(date=w.date,event='Employment transferred to '+office.name+'; approved dates and leave reservations retained.'))
    transfer=dict(date=w.date,from_employer=old.id,to_employer=office.id,from_position=old_position,
                  to_position=new_position.id,from_role=pos.role,to_role=role,review_baseline=annual_baseline)
    s.setdefault('employment_transfers',{}).setdefault(emp.id,[]).append(transfer)
    rules.validate()  # Includes the cross-company primary-supervisor cycle check.
    from .money_display import money
    detail=(rules.person(emp.person_id).name+' promoted to '+LABELS[role]+' at '+office.name+'. '
            +old.name+' no longer employs them in the '+pos.role.replace('_',' ')+' position. '
            +'Future payroll is paid by '+office.name+'; existing payroll liabilities stay with the original employer. '
            +'Existing business oversight, authority limits and spending history are retained. '
            +'One employment and primary supervisor; earned leave, approved time off and annual review date are retained. ')
    if old.id!=office.id:detail+='The old position is vacant. Hire a replacement manager for daily coverage; the leader can provide existing director fallback until then. '
    rules.record(emp.person_id,detail);record_change(rules,emp,previous,'Promoted and transferred to home-office leadership.')
    engine.event('Home-office leadership promotion',detail)
    from .workforce import Workforce
    wf=Workforce(engine);benefits=wf.benefit_cost(emp,wf.effective(office.id,emp)[0])
    detail+='Home-office cash on hand: '+money(w.cash(office.id))+'. Future employer benefits: '+money(benefits)+'/month, under the new employer’s policies and retained individual agreements. '
    names={b.id:b.name for b in w.businesses}
    return (rules.person(emp.person_id).name+' → '+LABELS[role]+' at '+office.name+'. '
            +'Monthly base pay: '+money(q['current'])+' → '+money(q['salary'])+' (increase '+money(q['increase'])+'). '
            +'Future payroll is paid by '+office.name+'; employer taxes are additional. '
            +'Oversees '+', '.join(names[bid] for bid in load['businesses'])+'. '
            +('The prior executive position is replaced by the new role. ' if old.id==office.id and pos.role in ROLES else 'The old position is vacant; hire a replacement for daily coverage. Existing director fallback remains available. ')
            +'Past payroll stays with '+old.name+'. Leave, annual review timing, authority limits and spent budgets are retained. '
            +'Reports to '+(rules.person(rules.contract(supervisor).person_id).name if supervisor else 'Player / owner')+'. '
            +'New employer benefits: '+money(benefits)+'/month; employer policies and individual agreements apply.')


def promote(engine,args):
    """Preview every dependency before changing the caller's world."""
    trial=Engine(copy.deepcopy(engine.world));result=_apply(trial,args);trial.validate()
    office=args['office_id']
    # Forecast new salary, benefits and known obligations, without assuming receipts.
    forecast=cash_forecast(trial.world,office,30)
    if forecast['available']<0:
        from .money_display import money
        raise RuleError('Fund the home office before promotion: '+money(trial.world.cash(office))+' cash does not cover '+money(forecast['obligations'])+' of known obligations and 30 days of payroll. No employee was moved.')
    return _apply(engine,args)
