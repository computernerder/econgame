"""Read-only company and employee views, including consolidated ownership totals."""
from .positions import open_positions
from .industries import SALES, PROJECTS
from dataclasses import asdict
from datetime import date, timedelta

from .business_models import BENEFITS, INDUSTRY_NAMES, INDUSTRY_ROLES, ROLE_PAY, ROLE_SKILLS
from .business_rules import BusinessRules
from .domain import Engine


def entity_names(world):
    from .campaign import Campaign
    controlled=Campaign(Engine(world)).controlled
    from .holding_company import exists, name
    return {"personal":"Personal portfolio",**({"company":name(world)} if exists(world) else {}),**{b.id:b.name for b in world.businesses if controlled(b.id)}}


def descendants(world, entity):
    result=[entity]
    for parent in result:
        from .holding_company import exists
        if parent=="personal" and exists(world):result.append("company")
        result.extend(b.id for b in world.businesses if b.owner==parent and b.id not in result)
    return result


def own_equity(world,entity,market=True):
    accounts=world.accounts[entity]
    value=sum(v for k,v in accounts.items() if k.startswith(("asset:","liability:")) and not k.startswith("asset:investment"))
    if market:value+=sum(p.value-p.basis for p in world.properties if p.owner==entity)
    return value


def eliminated(account,entities):
    return account=='income:dividends' or (account.startswith(('income:internal_','expense:internal_','asset:intercompany:','liability:intercompany:','asset:internal_loan:','asset:internal_interest:','liability:internal_loan:','liability:internal_interest:')) and account.split(':',2)[2] in entities)


def group_profit(world,entities):
    return -sum(v for entity in entities for k,v in world.accounts[entity].items() if k.startswith(('income:','expense:')) and not eliminated(k,entities))


def employee_view(rules,emp):
    person=rules.person(emp.person_id);pos=rules.position(emp.position_id)
    today=date.fromisoformat(rules.w.date);born=date.fromisoformat(person.birth_date)
    b=rules.company(emp.employer,owned=False)
    overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
    from .leadership import review
    from .workforce import Workforce
    from .time_off import absent, active_request, KINDS
    wf=Workforce(rules.e);benefits=wf.benefit_cost(emp,wf.effective(b.id,emp)[0]) if rules.w.systems else BENEFITS[b.benefits]
    leave=active_request(rules.w,emp)
    status_label=KINDS[leave["kind"]]+" until "+leave["end"] if leave else "On leave" if absent(rules.w,emp) else emp.status.title()
    from .employee_reporting import supervisor
    parent=supervisor(rules.w,emp)
    supervisor_label=(rules.person(parent.person_id).name+" · "+rules.company(parent.employer,owned=False).name) if parent else "Owner / company leadership"
    from .leadership_history import duties
    from .ui_workflows import role_label
    from .leadership_transfer import options as office_options
    from .employee_reporting import options as supervisor_options
    return dict(home_offices=office_options(rules.w,emp),transfer_supervisors=supervisor_options(rules.w,emp),leadership_duties=duties(rules.w,emp),supervisor_label=supervisor_label,status_label=status_label,pay_review=review(rules.w,emp),id=emp.id,person_id=person.id,name=person.name,business_id=b.id,business_name=b.name,role=pos.role,role_label=role_label(pos.role),position_id=pos.id,reports_to=pos.reports_to,salary=emp.salary,weekly_hours=emp.weekly_hours,shift_start=emp.shift_start,shift_end=f"{(emp.shift_start*60+emp.weekly_hours*60//len(emp.days))//60:02}:{(emp.weekly_hours*60//len(emp.days))%60:02}",status=emp.status,start_date=emp.start_date,end_date=emp.end_date,leave_until=emp.leave_until,leave_balance=emp.leave_balance,morale=person.morale,engagement=person.engagement,burnout=person.burnout,age=today.year-born.year-((today.month,today.day)<(born.month,born.day)),qualifications=person.qualifications,known_skills={s:person.skills.get(s,30) for s in person.demonstrated},unknown_skills=[s for s in person.skills if s not in person.demonstrated],ambition=person.ambition,experience=person.experience,history=list(reversed(person.history)),training_until=person.training_until,total_cost=emp.salary+overtime+benefits,severance=emp.salary*12//52 if emp.status=="active" else 0,market_pay=ROLE_PAY[pos.role]*emp.weekly_hours//40,days=", ".join(("Mon","Tue","Wed","Thu","Fri","Sat","Sun")[d] for d in emp.days))


def company_view(rules,b):
    w=rules.w
    item=asdict(b)
    staff=[employee_view(rules,e) for e in w.employments if e.employer==b.id and e.status in ("active","joining","seller")]
    occupied={e["position_id"] for e in staff}
    vacancies=[asdict(p) for p in open_positions(w,b.id) if p.id not in occupied]
    properties=[p for p in w.properties if p.owner==b.id or (b.owner is None and p.reserved_for==b.id)]
    accounts=w.accounts.get(b.id,{})
    profit=-sum(v for k,v in accounts.items() if k.startswith(("income:","expense:")))
    cutoff=(date.fromisoformat(w.date)-timedelta(days=29)).isoformat()
    financial={}
    for day,balances in b.financial_days.items():
        if day>=cutoff:
            for account,value in balances.items():financial[account]=financial.get(account,0)+value
    streams={k[7:]:-v for k,v in financial.items() if k.startswith('income:')}
    revenue=sum(streams.values())
    expense=sum(v for k,v in financial.items() if k.startswith('expense:'))
    days=min(30,(date.fromisoformat(w.date)-date.fromisoformat(b.acquired_on)).days+1) if b.acquired_on else 0
    cash=accounts.get("asset:cash",0)
    costs=sum(e["total_cost"] for e in staff)
    average=lambda key: round(sum(e[key] for e in staff)/len(staff)) if staff else None
    item.update(industry_name=INDUSTRY_NAMES[b.industry],staff=staff,vacancies=vacancies,properties=[{**asdict(p),"value":p.value,"suggested_rent":p.suggested_rent} for p in properties],cash=cash,monthly_payroll=costs,monthly_cost=costs+b.monthly_lease+b.monthly_overhead+sum(p.upkeep for p in properties),morale=average("morale"),engagement=average("engagement"),burnout=average("burnout"),culture=average("morale"),profit=profit,group_profit=group_profit(w,descendants(w,b.id)) if b.owner else 0,distributable=max(0,min(cash,profit-accounts.get("equity:distributions",0))),receivable=accounts.get("asset:receivable",0),unbilled=accounts.get("asset:unbilled",0),payroll_owed=-accounts.get("liability:payroll",0),payable=-accounts.get("liability:payable",0),streams=streams,revenue_30=revenue,profit_30=revenue-expense,history_days=days,quote=rules.quote(b.id),roles=INDUSTRY_ROLES[b.industry],role_pay={role:ROLE_PAY[role] for role in INDUSTRY_ROLES[b.industry]},parent_name=entity_names(w).get(b.owner or b.reserved_by,"Seller"),subsidiaries=[{"id":c.id,"name":c.name} for c in w.businesses if c.owner==b.id or (c.market_parent==b.id and not b.owner)],equity=sum(own_equity(w,e) for e in descendants(w,b.id)) if b.owner else 0,project_percent=b.project_progress*100//max(1,b.contract_minutes),owned=b.id in entity_names(w))
    from .premises import arrangement
    premises=arrangement(w,b)
    item.update(premises=premises['rows'],premises_rent=premises['monthly_rent'])
    item['monthly_cost']+=premises['monthly_rent']-b.monthly_lease
    controlled=entity_names(w)
    from .real_estate import required_category
    item['premises_category']=required_category(b)
    from .real_estate import compatible
    eligible=[p for p in w.properties if compatible(p.category,b) if p.owner in controlled and p.region==b.region and p.status=='vacant' and not p.spaces and p.condition>=40]
    item['own_premises_options']=[dict(id=p.id,name=p.name) for p in eligible if p.owner==b.id]
    item['lease_premises_options']=[dict(id=p.id,name=p.name,owner=controlled[p.owner]) for p in eligible if p.owner!=b.id]
    item['can_relocate']=not any(row['kind'] in ('Company owned','Leased') for row in premises['rows'])
    from .logistics import group_benefits
    item['group_benefits']=group_benefits(w,b)
    from .manager_defaults import limits
    item['authority']=limits(b)
    from .leadership import Leadership
    item['leadership']=Leadership(rules.e).view(b) if b.owner else {}
    from .specialists import view as specialist_view, recruitment_quote
    item['specialists']=specialist_view(w,b)
    item['recruitment']=recruitment_quote(w,b.id)
    item['sales_model']=b.industry in SALES
    item['project_model']=b.industry in PROJECTS
    if b.industry=='bank':
        from .banking import bank_view
        item['bank']=bank_view(w,b)
    if b.industry in PROJECTS:
        from .engineering import next_offer
        from .project_portfolio import jobs,remaining,acceptance_reason
        item['active_projects']=[{**j,'percent':j['progress']*100//j['minutes']} for j in jobs(b)]
        item['total_project_remaining']=remaining(b)
        item['total_project_earned']=sum(j['earned'] for j in jobs(b))
        item['total_project_progress']=sum(j['progress'] for j in jobs(b))
        item['next_project_offer']=next_offer(w,b)
        from .revenue_kits import state as kit_state
        item['next_project_blocker']=acceptance_reason(w,b,item['next_project_offer']) if kit_state(w,b) else ''
        item['project_hourly_value']=b.contract_fee*60//max(1,b.contract_minutes)
        item['project_remaining_minutes']=max(0,b.contract_minutes-b.project_progress)
        pending={invoice['id'] for invoice in b.receivables}
        item['project_invoices']=[{**row,'status':'Awaiting payment' if row['invoice_id'] in pending else 'Paid'} for row in reversed(b.project_history)]
    from .revenue_kits import view as kit_view,tag as kit_tag,CATALOG as KIT_CATALOG
    item['revenue_kits']=kit_view(w,b)
    if item['revenue_kits'] and b.industry in PROJECTS:
        for job in item['active_projects']:
            job['stream_label']=KIT_CATALOG[b.industry][kit_tag(w,b,job['number'])['kit']]['label']
    return item


def business_context(world,scope):
    rules=BusinessRules(Engine(world));names=entity_names(world)
    business_views=[company_view(rules,b) for b in world.businesses]
    employees=[employee_view(rules,e) for e in world.employments if e.employer in names and e.status in ("active","joining")]
    candidates=[dict(id=p.id,name=p.name,qualifications=p.qualifications,experience=p.experience,ambition=p.ambition,known_skills={s:p.skills[s] for s in p.demonstrated},unknown_skills=[s for s in p.skills if s not in p.demonstrated]) for p in world.people if p.candidate]
    grouped=descendants(world,scope)
    return dict(entities=[{"id":key,"name":name} for key,name in names.items()],scope_name=names[scope],business_market=[b for b in business_views if b["status"] in ("market","closing") and not b.get("market_parent")],businesses=[b for b in business_views if b["owned"]],employees=employees,candidates=candidates,group_entities=grouped,group_profit=group_profit(world,grouped),all_business_profit=group_profit(world,[e for e in names if e!="personal"]),all_business_wealth=sum(own_equity(world,e) for e in names if e!="personal"),group_wealth=sum(own_equity(world,e) for e in grouped),total_wealth=sum(own_equity(world,e) for e in names),personal_book=sum(own_equity(world,e,False) for e in names),average_morale=round(sum(e["morale"] for e in employees)/len(employees)) if employees else None,benefit_options=BENEFITS,industry_names=INDUSTRY_NAMES)
