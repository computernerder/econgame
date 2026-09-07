"""Read-only financial drilldowns from asset records and the actual journal."""
from collections import defaultdict
from urllib.parse import urlencode
from .business_views import entity_names
from .domain import Engine, GAME_RULES
from .workforce import Workforce

PAYROLL_ACCOUNTS = ('expense:wages', 'expense:benefits', 'expense:incentives',
                    'expense:severance', 'expense:payroll_tax', 'expense:bonus')
LABELS = {'asset:cash':'Cash by account', 'asset:property':'Owned properties',
          'asset:equipment':'Equipment purchases and fit-out',
          'asset:equipment_accumulated':'Equipment depreciation',
          'liability:payroll':'Payroll still owed', 'asset:receivable':'Customer invoices',
          'asset:unbilled':'Earned work not yet invoiced'}


def link(page, entity, **kwargs):
    return '/?' + urlencode(dict(page=page, scope=entity, **kwargs))


def detail_view(world, store, entities, balances, since):
    names=entity_names(world)
    businesses={b.id:b for b in world.businesses}
    properties={p.id:p for p in world.properties}
    employees={e.id:e for e in world.employments}
    people={p.id:p for p in world.people};positions={p.id:p for p in world.positions}
    slots=','.join('?' for _ in entities)
    # No 100-entry journal limit here: current balances can originate years ago.
    with store.connection() as db:
        equipment=[dict(r) for r in db.execute(f"""SELECT j.id,j.entity,j.source,j.date,j.memo,l.account,l.amount
            FROM journal j JOIN lines l ON l.journal_id=j.id
            WHERE j.entity IN ({slots}) AND l.account IN ('asset:equipment','asset:equipment_accumulated')
            ORDER BY j.id""",entities)]
        pay=[dict(r) for r in db.execute(f"""SELECT j.id,j.entity,j.source,j.date,j.memo,l.account,l.amount
            FROM journal j JOIN lines l ON l.journal_id=j.id
            WHERE j.entity IN ({slots}) AND j.date>=? AND j.date<=?
            AND l.account IN ('expense:wages','expense:benefits','expense:incentives','expense:severance','expense:payroll_tax','expense:bonus')
            ORDER BY j.id""",(*entities,since,world.date))]

    def identify(entity,source,memo=''):
        # Stable employment IDs survive renames, promotions and termination.
        parts=source.split(':')
        match=next((employees[p] for p in parts if p in employees and (employees[p].employer==entity or any(t['from_employer']==entity for t in world.systems.get('employment_transfers',{}).get(p,[])))),None)
        if match:return match.id
        # Older immediately-paid severance entries named the person in the memo.
        matches=[e.id for e in employees.values() if e.employer==entity and memo=='Severance: '+people[e.person_id].name]
        return matches[0] if len(matches)==1 else ''

    def person_row(entity,eid):
        emp=employees.get(eid)
        former=next((t for t in reversed(world.systems.get('employment_transfers',{}).get(eid,[])) if t['from_employer']==entity),None) if emp and emp.employer!=entity else None
        return dict(entity=entity,owner=names.get(entity,entity),employment_id=eid,
            name=people[emp.person_id].name if emp else 'Unassigned historical payroll',
            role=(former['from_role'] if former else positions[emp.position_id].role).replace('_',' ').title() if emp else 'No employee recorded',
            url=link('employee',entity,employment_id=eid) if emp else link('finance',entity),
            status=emp.status if emp else 'historical')

    def row(entity,name,amount,description='',url='',date=''):
        return dict(owner=names.get(entity,entity),entity=entity,name=name,amount=amount,
                    description=description,url=url,date=date)

    outstanding=defaultdict(int);sections=[]
    for account,total in balances.items():
        if not total:continue
        rows=[];notes=[]
        for entity in entities:
            expected=world.accounts[entity].get(account,0)
            if not expected:continue
            b=businesses.get(entity);group=[]
            if account=='asset:cash':
                description=('Bank liquidity, including funds backing customer deposits; lending still requires reserves and capital.' if b and b.industry=='bank' else 'Cash held in this entity’s operating account. Commitments and debts are not deducted here.')
                group.append(row(entity,names.get(entity,entity),expected,description,link('finance',entity)))
                notes=['Cash is tracked by entity. Individual bank accounts and physical cash locations are not modeled. Escrows, reserves and deposits appear separately below.']
            elif account=='asset:property':
                for p in world.properties:
                    if p.owner!=entity:continue
                    occupancy=names.get(p.occupant,p.occupant) if p.occupant else p.tenant or p.status.replace('_',' ')
                    group.append(row(entity,p.name,p.basis,f'{p.category.replace("_"," ").title()} · {p.region} · {occupancy} · Condition {p.condition}/100',link('property',entity,property_id=p.id),p.bought_on or ''))
                    group[-1]['market_value']=p.value
                notes=['Amounts are recorded purchase/improvement cost. Estimated market values are shown separately. Owning a building does not mean owning its tenant.']
            elif account=='asset:equipment':
                for entry in equipment:
                    if entry['entity']==entity and entry['account']==account and entry['amount']:
                        group.append(row(entity,entry['memo'],entry['amount'],f'{b.industry.replace("_"," ").title() if b else "Entity"} equipment / fit-out pool',link('business',entity,business_id=entity) if b else '',entry['date']))
                notes=['The game records equipment in purchase/fit-out pools, not individual machines. Rows show every capitalized addition and disposal. Depreciation is separate; cash spent on expensed maintenance or local improvements is not added to asset cost.']
            elif account=='asset:equipment_accumulated':
                history=[x for x in equipment if x['entity']==entity and x['account']==account]
                gross=world.accounts[entity].get('asset:equipment',0)
                group.append(row(entity,(b.name if b else names.get(entity,entity))+' equipment',expected,'Accumulated depreciation against the equipment pool; does not measure physical condition.',link('business',entity,business_id=entity) if b else ''))
                group[-1].update(gross=gross,net=gross+expected,condition=world.systems.get('industry_state',{}).get(entity,{}).get('equipment_condition'),history=history)
            elif account=='liability:payroll':
                grouped=defaultdict(lambda:dict(amount=0,due='',created=''))
                for lot in world.systems.get('obligation_lots',{}).get(entity,{}).get(account,[]):
                    eid=identify(entity,lot['source']);item=grouped[eid]
                    item['amount']-=lot['remaining']
                    item['due']=min(item['due'] or lot['due'],lot['due'])
                    item['created']=min(item['created'] or lot['created'],lot['created'])
                for eid,item in grouped.items():
                    person=person_row(entity,eid)
                    group.append(row(entity,person['name'],item['amount'],person['role']+' · Earliest payment due '+item['due'],person['url'],item['created']))
                    outstanding[(entity,eid)]+=-item['amount']
                gap=expected-sum(r['amount'] for r in group)
                if gap:outstanding[(entity,'')]+=-gap
                notes=['Unpaid wage, benefit and incentive obligations by employee. Settlements reduce the oldest due accruals using the simulation’s payment allocation. Employer payroll tax is in payables, not in this liability. Older unidentified balances remain unassigned.']
            elif account=='asset:receivable' and b:
                for invoice in b.receivables:
                    group.append(row(entity,invoice['id'],invoice['amount'],'Due '+invoice['due']+(' · Defaulted' if invoice.get('defaulted') else ' · Overdue' if invoice['due']<world.date else ' · Awaiting payment'),link('operations_center',entity)+'#customer-collections'))
            elif account=='asset:unbilled' and b:
                from .industries import PROJECTS
                if b.industry in PROJECTS:
                    from .project_portfolio import jobs
                    for job in jobs(b):
                        group.append(row(entity,'Contract '+str(job['number']),job['earned'],f'{job["progress"]/60:.1f} of {job["minutes"]/60:g} qualified hours delivered; invoiced at completion.',link('business',entity,business_id=entity)))
            elif account.startswith('asset:lease_deposit:'):
                lid=account.split(':',2)[2]
                lease=next((x for x in world.systems.get('leases',[]) if x['id']==lid),None)
                prop=properties.get(lease.get('property_id')) if lease else None
                group.append(row(entity,prop.name if prop else lid,expected,'Security deposit paid to the landlord; separate from available cash.',link('property',entity,property_id=prop.id) if prop else '',lease.get('start','') if lease else ''))
            elif account.startswith('liability:'):
                for lot in world.systems.get('obligation_lots',{}).get(entity,{}).get(account,[]):
                    group.append(row(entity,lot['source'],-lot['remaining'],'Due '+lot['due'],'',lot['created']))
            # Retain every cent even when an older save lacks a supporting record.
            gap=expected-sum(r['amount'] for r in group)
            if gap:
                group.append(row(entity,'Unassigned historical balance' if group or account in LABELS else account.replace(':',' / ').replace('_',' ').title(),gap,
                    'Recorded in the ledger; individual supporting detail is not available.' if group or account in LABELS else 'Recorded balance in this entity’s account.',link('finance',entity)))
            rows.extend(group)
        sections.append(dict(account=account,title=LABELS.get(account,account.replace(':',' / ').replace('_',' ').title()),total=total,rows=rows,notes=notes,
            expanded=account in ('asset:cash','asset:property','asset:equipment','liability:payroll')))

    payroll={}
    for entry in pay:
        eid=identify(entry['entity'],entry['source'],entry['memo']);key=(entry['entity'],eid)
        if key not in payroll:payroll[key]={**person_row(*key),**{k:0 for k in ('wages','benefits','incentives','severance','bonus','payroll_tax')},'total':0,'owed':outstanding[key]}
        payroll[key][entry['account'].split(':')[1]]+=entry['amount'];payroll[key]['total']+=entry['amount']
    for key,amount in outstanding.items():
        if key not in payroll:payroll[key]={**person_row(*key),**{k:0 for k in ('wages','benefits','incentives','severance','bonus','payroll_tax','total')},'owed':amount}
    payroll_rows=sorted(payroll.values(),key=lambda x:(x['owner'],x['name'],x['employment_id']))
    totals={key:sum(x[key] for x in payroll_rows) for key in ('wages','benefits','incentives','severance','bonus','payroll_tax','total','owed')}

    workforce=Workforce(Engine(world));contracts=[]
    for emp in employees.values():
        if emp.employer not in entities or emp.status not in ('active','joining'):continue
        policy=workforce.effective(emp.employer,emp)[0]
        overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
        premium=emp.compensation.get('shift_premium',0);benefits=workforce.benefit_cost(emp,policy)
        salary=emp.salary+overtime+premium
        # Daily tax rounding is used by the simulation, so this is explicitly a run rate.
        tax=salary*GAME_RULES['tax']['payroll_percent']//100
        contracts.append({**person_row(emp.employer,emp.id),'base':emp.salary,'overtime':overtime,'premium':premium,'benefits':benefits,'tax':tax,
                          'total':salary+benefits+tax,'hours':emp.weekly_hours,'start':emp.start_date})
    return dict(sections=sections,payroll=payroll_rows,payroll_totals=totals,contracts=contracts,since=since,
                contract_total=sum(x['total'] for x in contracts if x['status']=='active'),
                joining_total=sum(x['total'] for x in contracts if x['status']=='joining'))
