"""Optional service-company setup and financial views over existing ledgers."""
from datetime import date, timedelta
from .business_views import entity_names
from .navigation import url


def companies(world):
    names=entity_names(world)
    start=(date.fromisoformat(world.date)-timedelta(days=29)).isoformat()
    rows=[]
    for b in world.businesses:
        if b.industry!='office' or b.id not in names:continue
        accounts=world.accounts[b.id];period={}
        for day,entries in b.financial_days.items():
            if start<=day<=world.date:
                for key,value in entries.items():period[key]=period.get(key,0)+value
        payroll=sum(period.get(key,0) for key in ('expense:wages','expense:benefits','expense:payroll_tax'))
        costs=sum(value for key,value in period.items() if key.startswith('expense:'))
        revenue=-sum(value for key,value in period.items() if key.startswith('income:'))
        departments=[d for d in world.systems.get('departments',{}).values() if d['provider']==b.id]
        tasks=[t for t in world.systems.get('service_tasks',[]) if t['provider']==b.id]
        rows.append(dict(id=b.id,name=b.name,owner=names.get(b.owner,b.owner),status=b.status,
            cash=world.cash(b.id),payroll_due=max(0,-accounts.get('liability:payroll',0)),
            internal_earned=-sum(v for k,v in period.items() if k.startswith('income:internal_services:')),
            payroll=payroll,other_costs=costs-payroll,profit=revenue-costs,
            receivable=sum(v for k,v in accounts.items() if k.startswith('asset:intercompany:')),
            payable=-sum(v for k,v in accounts.items() if k.startswith('liability:intercompany:')),
            departments=len(departments),queued=sum(t['status'] in ('queued','working') for t in tasks),
            unused_minutes=sum(max(0,d.get('last_capacity',0)-d.get('last_used',0)) for d in departments),
            from_date=start,through=world.date,
            services_url=url('home_office',b.id,action_focus='department_configure')+'#task-focus',
            business_url=url('business',b.id,business_id=b.id),
            finance_url=url('finance',b.id),people_url=url('people',b.id,business_id=b.id),
            capital_url=url('business',b.id,business_id=b.id)+'#business-capital'))
    return rows


def extend(view,world,scope):
    from .campaign_views import field,hidden,form,choices,money,table
    from .expansion import Expansion
    from .domain import Engine
    rows=companies(world);names=entity_names(world)
    q=Expansion(Engine(world)).opening_quote('office')
    view['office_companies']=rows
    view['office_creation']=form('start_business','Create a separate home-office company',
        'Optional: this creates its own legal ownership, cash account, payroll and books. '
        f"Default startup funding is {money(q['total'])}: deposit {money(q['deposit'])}, fit-out {money(q['fitout'])}, setup expense {money(q['expense'])}, and cash reserve {money(q['reserve'])}. "
        f"Opening takes at least {q['days']} days and requires a manager. Changing the reserve changes the total shown at review. "
        'Hire specialists and configure departments after formation. Existing staff, departments and balances stay with their current employers.',
        [hidden('industry','office'),field('name','Company name','Group Shared Services'),
         field('entity','Funding owner','personal','select',choices(names)),
         field('region','Office county','Rutland County','select',choices({r['id']:r['id'] for r in world.systems['regions']})),
         field('reserve_dollars','Opening cash reserve ($)',q['reserve']/100,'number',minimum=q['reserve']//2/100)],
        button='Review company formation →')
    available=[r for r in rows if r['status']!='closed']
    default=scope if scope in {r['id'] for r in available} else available[0]['id'] if available else scope if scope in names and scope not in ('personal','company') else ''
    for f in view['forms']:
        if f['action']=='department_configure':
            f['anchor']='department-setup'
            f['expanded']=scope in {r['id'] for r in available}
            for item in f['fields']:
                if item['name']=='provider':item.update(value=default,label='Employing company / department provider')
                if item['name']=='regions' and default:
                    provider=next((b for b in world.businesses if b.id==default),None)
                    if provider:item['value']=provider.region
    if scope in {r['id'] for r in rows}:
        balances=[]
        for entity,label in names.items():
            owed_to=world.accounts[scope].get('asset:intercompany:'+entity,0)
            owed_by=-world.accounts[scope].get('liability:intercompany:'+entity,0)
            if owed_to or owed_by:balances.append((label,money(owed_to),money(owed_by)))
        view['tables'].insert(0,table('Selected home-office company · internal balances',
            ['Counterparty','Receivable from this account','Payable to this account'],balances,
            'Recorded balances include services and other internal transactions. Daily settlement transfers only available debtor cash; unpaid balances remain.'))
