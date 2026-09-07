"""One inbox assembled from saved decisions and outstanding operating records.

Reading the inbox never creates decisions, spends money, or advances randomness.
Source records remain authoritative, so actions elsewhere clear their inbox items.
"""
from datetime import date, timedelta
from urllib.parse import urlencode


def items(world,manager_care=None):
    from .business_views import entity_names
    from .domain import Engine
    from .distress import Distress
    from .property_operations import systems_for

    names=entity_names(world);props={p.id:p for p in world.properties if p.owner in names}
    businesses={b.id:b for b in world.businesses if b.id in names}
    s=world.systems;result=[];today=world.date
    soon=(date.fromisoformat(today)+timedelta(days=60)).isoformat()

    def add(kind,key,entity,title,detail,page='operations_center',action='',targets=None,due='',amount=None,
            priority=1,status='open',source=None):
        if entity not in names:return
        identifier=kind+':'+key
        route=dict(page=page,scope=entity,inbox_item=identifier)
        if page=='business':route['business_id']=entity
        if page in ('workforce','employee') and targets and targets.get('employment_id'):route['employment_id']=targets['employment_id']
        result.append(dict(id=identifier,kind=kind,entity=entity,entity_name=names[entity],title=title,
            detail=detail,page=page,action=action,targets=targets or {},due=due or '',amount=amount,
            priority=0 if due and due<today and status!='deferred' else priority,status=status,source=source,
            url='/?'+urlencode(route)+'#inbox-target'))

    from .director_scope import overloaded
    for emp,load in overloaded(world):
        person=next(p for p in world.people if p.id==emp.person_id)
        add('director_capacity',emp.id,emp.employer,'Director workload · '+person.name,
            f"{load['count']} businesses, including inherited subsidiaries, require {load['minutes']} oversight minutes per working day; {load['available']} minutes remain after the employee's regular-role allowance. Maximum {load['maximum']} businesses. Appoint another director for a branch or adjust inheritance and schedules.",page='management')
        result[-1]['url']='/?page=management#business-policies'
    from .time_off import blockers as leave_blockers, coverage, KINDS, review_status
    for request in leave_blockers(world):
        emp=next(e for e in world.employments if e.id==request['employment_id'])
        person=next(p for p in world.people if p.id==emp.person_id)
        impact=coverage(world,emp,request)
        review=review_status(world,request)
        add('time_off',request['id'],emp.employer,'Time off · '+person.name,
            f"{KINDS[request['kind']]}: {request['start']} to {request['end']}. {impact['hours']:g} scheduled hours unavailable if approved; up to {impact['max_absent_percent']}% of this team's scheduled staff absent. "+('No same-role colleague covers at least one requested day. ' if impact['role_gap'] else '')+request['reason']+' Manager review: '+review['reason'],
            'employee','time_off_decide',dict(employment_id=emp.id,request_id=request['id']),due=request['start'],source=request)
        if result and result[-1]['id']=='time_off:'+request['id']:
            result[-1]['url']=result[-1]['url'].replace('#inbox-target','#employee-time-off')
            result[-1]['leave_review']=review
    for d in s.get('decisions',[]):
        if d['status']=='open':
            src=d.get('source','');page='operations_center';action='';targets={}
            if src.startswith('tax-filing:'):
                if world.accounts.get(d['entity'],{}).get('liability:income_tax',0)>=0:continue
                page='financing';action='file_taxes';targets=dict(entity=d['entity'])
            elif src.startswith(('loan-shortfall:','covenant:')):
                loan=next((l for l in s.get('loans',[]) if l['id']==src.split(':')[1]),None)
                if not loan or loan['status']!='active' or (src.startswith('loan-shortfall:') and not loan.get('arrears')):continue
                page='financing';action='repay_loan';targets=dict(entity=d['entity'],loan_id=loan['id'])
            elif src.startswith('tenant-arrears:'):
                lease=next((l for l in s.get('leases',[]) if l['id']==src.split(':')[1]),None)
                if not lease or not lease['arrears'] or lease.get('payment_plan'):continue
                page='spaces';action='lease_response' if lease['status']=='active' else 'write_off_rent';targets=dict(lease_id=lease['id'])
            elif src.startswith('license:'):
                emp=next((e for e in world.employments if e.id==src.split(':')[1] and e.status=='active'),None)
                if not emp:continue
                from .specialists import LICENSES
                pos=next(p for p in world.positions if p.id==emp.position_id)
                person=next(p for p in world.people if p.id==emp.person_id)
                license=pos.required_license or LICENSES.get(pos.role)
                if not license or person.licenses.get(license,'')>=today:continue
                if any(p['kind']=='license' and p.get('person_id')==person.id and p['status']=='active' for p in s.get('plans',[])):continue
                page='workforce';action='renew_license';targets=dict(employment_id=emp.id,license=license)
            elif src.startswith(('retirement:','retention:','opening-staff:')):page='people'
            add('decision',d['id'],d['entity'],d['title'],d['detail'],page,action,targets,due=d['due'],amount=d['cost'],source=d)
    from .routine_management import ready_property_care
    if manager_care is None:manager_care=ready_property_care(world)
    for r in s.get('management_requests',[]):
        if r['status'] in ('open','deferred') and r['id'] not in manager_care:
            add('management',r['id'],r['business_id'],'Management approval',((r.get('actor_name') or 'Management')+' asks: '+r['detail']),
                'management',due=r.get('deferred_until') if r['status']=='deferred' else r.get('due',''),
                amount=r['cost'],status=r['status'],source=r)

    working_targets={t.get('target_id') for t in s.get('service_tasks',[]) if t['status'] in ('queued','working')}
    latest_ads={v['space_id']:v for v in s.get('vacancies',[])}
    for vacancy in latest_ads.values():
        p=props.get(vacancy['property_id'])
        if not p or vacancy['status']!='no_interest':continue
        if any(l['space_id']==vacancy['space_id'] and l['status']=='active' for l in s.get('leases',[])):continue
        add('vacancy_price',vacancy['id'],p.owner,'Vacancy needs repricing · '+p.name,
            'The advertising campaign attracted no applicants at the asking rent. Review comparable rent, lower the ask and advertise again.',
            'property_workbench','advertise_space',dict(property_id=p.id,space_id=vacancy['space_id'],rent_dollars=vacancy['asking']/100))
    for offer in s.get('tenant_offers',[]):
        p=props.get(offer['property_id'])
        if not p or offer['status']!='open':continue
        if any(l['space_id']==offer['space_id'] and l['status']=='active' for l in s.get('leases',[])):continue
        add('tenant_offer',offer['id'],p.owner,'Tenant proposal · '+p.name,
            f"{offer['name']}: ${offer['rent']/100:,.2f}/month for {offer['months']} months; reliability {offer['reliability']}/100, required area {offer['area']} m². Improvement allowance ${offer['improvement']/100:,.2f}. Compare other applicants before choosing.",
            'property_workbench','accept_tenant',dict(property_id=p.id,offer_id=offer['id'],rent_dollars=offer['rent']/100),amount=offer['improvement'])
    for pid,listing in s.get('property_listings',{}).items():
        p=props.get(pid)
        if not p:continue
        if listing['status']=='marketing':
            for offer in listing.get('offers',[]):
                if offer['status']!='open':continue
                add('sale_offer',offer['id'],p.owner,'Property purchase offer · '+p.name,
                    f"Offer ${offer['price']/100:,.2f}; concession ${offer['concession']/100:,.2f}; financing failure risk {offer['finance_risk']}%. Closing takes 14 days. No proceeds have arrived.",
                    'property_workbench','accept_property_offer',dict(property_id=pid,offer_id=offer['id']))
        if listing['status']=='closing' and listing.get('due','9999')<=today:
            offer=next((o for o in listing['offers'] if o['id']==listing['accepted']),None)
            if not offer:continue
            gross=offer['price']-offer['concession'];net=gross-gross*3//100
            leases=[l for l in s.get('leases',[]) if l['property_id']==pid and l['status']=='active']
            debt=sum(l['principal']+l['interest_due'] for l in s.get('loans',[]) if l['entity']==p.owner and l.get('property_id')==pid and l['status']=='active')
            shortage=max(0,debt+sum(l['deposit_remaining'] for l in leases)-net-world.cash(p.owner))
            if shortage or sum(l['arrears'] for l in leases)>gross:
                add('closing',pid,p.owner,'Property closing blocked · '+p.name,
                    'Review secured debt, protected deposits and lease receivables. The sale cannot close until the recorded funding or collection gap is resolved.',
                    due=listing['due'],amount=shortage,priority=0)
    for ticket in s.get('property_requests',[]):
        p=props.get(ticket['property_id'])
        if not p or ticket['status'] not in ('open','overdue'):continue
        if systems_for(world,p)[ticket['system']]['condition']>=40:continue
        if any(w['property_id']==p.id and w['system']==ticket['system'] and w['status']=='working' for w in s.get('property_work',[])):continue
        if any(r['status'] in ('open','deferred') and r['args'].get('request_id')==ticket['id'] for r in s.get('management_requests',[])):continue
        add('repair',ticket['id'],p.owner,'Tenant repair request · '+p.name,
            ticket['system'].replace('_',' ').title()+': '+ticket.get('outcome','Repair needs a response. Request resolution requires actual completed work.'),
            'property_workbench','respond_property_request',dict(property_id=p.id,request_id=ticket['id'],kind='emergency' if ticket['severity']=='urgent' else 'repair'),
            due=ticket['due'],priority=0 if ticket['severity']=='urgent' else 1)
    for lease in s.get('leases',[]):
        p=props.get(lease['property_id'])
        if not p:continue
        if lease['status']=='active' and lease['tenant']=='external' and today<lease['end_date']<=soon:
            add('renewal',lease['id'],p.owner,'Lease renewal · '+p.name,
                lease['tenant_name']+' is approaching lease expiry. Decide whether to renew, negotiate rent, or let the existing lease expire.',
                'property_workbench','renew_property_lease',dict(property_id=p.id,lease_id=lease['id'],rent_dollars=lease['rent']/100),due=lease['end_date'],priority=2)
        # Normal daily accrued rent is not overdue; only missed collections/ended leases need recovery.
        missed=any(d.get('source','').startswith('tenant-arrears:'+lease['id']+':') for d in s.get('decisions',[]))
        if lease.get('arrears',0)>0 and (lease['status']=='ended' or missed) and not lease.get('payment_plan') and not lease.get('vacate_on'):
            if not any(d['status']=='open' and d.get('source','').startswith('tenant-arrears:'+lease['id']+':') for d in s.get('decisions',[])):
                add('rent_arrears',lease['id'],p.owner,'Overdue rent · '+lease['tenant_name'],
                    'Choose a collection plan, legal recovery or a documented write-off. Acknowledging an earlier alert did not settle the receivable.',
                    'spaces','lease_response' if lease['status']=='active' else 'write_off_rent',dict(property_id=p.id,lease_id=lease['id']),amount=lease['arrears'])
        if lease['status']=='ended' and lease.get('deposit_remaining',0)>0:
            add('deposit',lease['id'],p.owner,'Tenant deposit return · '+p.name,'Fund the owner account to return the remaining protected deposit; normal lease settlement processes the refund.',amount=lease['deposit_remaining'],priority=0)
    for claim in s.get('legal_claims',[]):
        if claim['status']=='open' and claim['id'] not in working_targets:
            add('claim',claim['id'],claim['owner'],'Documented warranty claim',claim['fact'],
                'home_office','service_request',dict(recipient=claim['owner'],department='legal',matter='dispute',target_id=claim['id']),amount=claim['amount'])
    for offer in s.get('supplier_offers',[]):
        if offer['status']=='open' and offer['valid_until']>=today:
            add('supplier_offer',offer['id'],offer['buyer'],'Supplier quote · '+offer['supplier'],
                f"{offer['department'].title()}: {offer['minutes']//60} prepaid service hours. Compare expected usage; unused capacity expires under the agreement.",
                'commercial_contracts','accept_supplier_contract',dict(entity=offer['buyer'],offer_id=offer['id']),due=offer['valid_until'],amount=offer['minutes']*offer['rate'],priority=2)
    for task in s.get('service_tasks',[]):
        if task['status'] in ('queued','working') and task['due']<today:
            add('service',task['id'],task['recipient'],'Service work overdue · '+task['department'].title(),
                f"{task['remaining']/60:g} hours remain. Review capacity, priority, or outsourcing; elapsed time does not create staff hours.",
                'home_office','outsource_service',dict(task_id=task['id']),due=task['due'])
    for job in s.get('property_service_jobs',[]):
        if job['status']=='working' and job['due']<today:
            add('property_service',job['id'],job['owner'],'Property service delivery overdue',job['outcome'],
                'property_services','cancel_property_service',dict(job_id=job['id']),due=job['due'])
    for covenant in s.get('property_covenants',[]):
        p=props.get(covenant['property_id'])
        if not p or covenant['status'] not in ('active','open','breached'):continue
        if systems_for(world,p)[covenant['system']]['condition']>=covenant['target']:continue
        if any(w['property_id']==p.id and w['system']==covenant['system'] and w['status']=='working' for w in s.get('property_work',[])):continue
        add('covenant',covenant['id'],p.owner,'Required property work · '+p.name,
            f"The purchase terms require {covenant['system']} condition {covenant['target']}. Missed-deadline charge ${covenant['charge']/100:,.2f}.",
            'property_workbench','property_work',dict(property_id=p.id,system=covenant['system']),due=covenant['due'],amount=covenant['charge'])
    for pid,flip in s.get('flip_progress',{}).items():
        p=props.get(pid)
        if not p:continue
        if flip['phase']=='funded':
            add('flip',pid,p.owner,'Funded flip ready for work · '+p.name,
                f"${flip['reserve']/100:,.2f} remains reserved. Review the work quote; approve extra capital if it exceeds the reserve.",
                'property_workbench','flip_work',dict(property_id=pid))
        elif flip['phase'] in ('working','ready') and not any(j['property_id']==pid and j['status']=='working' for j in s.get('property_work',[])) and s.get('property_listings',{}).get(pid,{}).get('status') not in ('marketing','closing','sold'):
            add('flip',pid,p.owner,'Flip work complete · '+p.name,'Choose further work or market the property. Sale proceeds and profits depend on an actual closing.',
                'property_workbench','market_property',dict(property_id=pid,asking_dollars=p.value/100))
    for job in s.get('property_work',[]):
        p=props.get(job['property_id'])
        if p and job['status']=='working' and job['provider']!='outside':
            provider=businesses.get(job['provider'])
            # An unavailable provider is a definite block; other internal work may simply be queued.
            if not provider or provider.status=='closed':
                add('work',job['id'],p.owner,'Repair provider unavailable · '+p.name,
                    f"{job['remaining']/60:g} hours remain with a provider that is no longer operating. Arrange an outside contractor.",
                    'property_workbench','outsource_property_work',dict(property_id=p.id,work_id=job['id']))

    for entity in names:
        overdue=[r for r in Distress(Engine(world)).obligations(entity) if r['remaining']>0 and r['due']<today]
        if overdue:
            add('obligations',entity,entity,'Overdue obligations · '+names[entity],
                'Review funding, payment, supplier terms, debt restructuring or asset sales. These amounts remain owed until settled.',
                'operations_center','settle_obligations',dict(entity=entity),due=min(r['due'] for r in overdue),amount=sum(r['remaining'] for r in overdue),priority=0)
    for b in businesses.values():
        if b.status=='developing':
            from .business_models import OPENING_ROLES
            positions={p.id:p for p in world.positions}
            present={positions[e.position_id].role for e in world.employments if e.employer==b.id and e.status in ('active','joining')}
            missing=OPENING_ROLES[b.industry]-present
            if missing and not any(d['status']=='open' and d.get('source')=='opening-staff:'+b.id for d in s.get('decisions',[])):
                add('opening',b.id,b.id,'Opening needs staff · '+b.name,'Recruit the required roles: '+', '.join(sorted(missing))+'. Existing rent and payroll continue during setup.',
                    'people',due=b.opening_on)
        if b.status=='operating':
            from .industries import PROJECTS, SALES
            if b.industry in PROJECTS and not b.project_active and not b.auto_projects:
                add('project',b.id,b.id,'Choose the next project · '+b.name,
                    'The previous job has ended and automatic job acceptance is disabled. Review the next quote or change the job policy.',
                    'business',targets=dict(business_id=b.id),priority=2)
            if b.industry in SALES and b.inventory_units==0 and not b.auto_restock:
                add('stock',b.id,b.id,'Stock purchasing needed · '+b.name,
                    'Inventory is empty and automatic purchasing is disabled. Decide how much to order or change purchasing policy.',
                    'business',targets=dict(business_id=b.id))
        from .staffing import vacancies
        for plan in s.get('plans',[]):
            if plan.get('kind')=='recruitment' and plan.get('entity')==b.id and plan['status']=='complete' and vacancies(world,b.id,plan['role']):
                # One staffing decision per role, even after multiple recruiting campaigns.
                if not any(r['id']=='recruitment:'+b.id+':'+plan['role'] for r in result):
                    add('recruitment',b.id+':'+plan['role'],b.id,'Recruitment ready · '+b.name,
                        plan['role'].replace('_',' ').title()+' applicants have arrived. Review candidates, hire within your budget, or remove an unwanted vacancy.',
                        'people',targets=dict(business_id=b.id),priority=2)
        from .customer_collections import busy
        for invoice in b.receivables:
            if invoice.get('defaulted') or invoice.get('overdue_since') or invoice['due']<today:
                if invoice['id'] in working_targets or busy(world,b.id,invoice):continue
                if any(r['status'] in ('open','deferred') and r['business_id']==b.id and r['args'].get('invoice_id')==invoice['id'] for r in s.get('management_requests',[])):continue
                from .routine_management import assigned_collection
                if assigned_collection(world,b,invoice):continue
                add('invoice',invoice['id'],b.id,'Customer collection · '+b.name+' · '+invoice['id'],
                    ('Customer default recorded. Review is needed even if the scheduled due date has not arrived. ' if invoice.get('defaulted') else 'Payment overdue since '+str(invoice.get('overdue_since') or invoice['due'])+'. ')+
                    'Choose a free reminder, installments, a contingency collection agency, legal work or a last-resort write-off. A promised late payment retries automatically on its scheduled date.',
                    'operations_center','recover_invoice',dict(entity=b.id,invoice_id=invoice['id']),due=invoice['due'],amount=invoice['amount'])
        if b.status=='closed' and not any(p['entity']==b.id and p['status']=='marketing' for p in s.get('asset_liquidations',[])):
            if sum(Distress(Engine(world)).liquidation_accounts(b.id).values())>0:
                add('closure',b.id,b.id,'Closed business assets · '+b.name,'Decide whether to market remaining equipment, inventory or customer-loan assets. Buyer completion is not guaranteed.',
                    'operations_center','liquidate_assets',dict(entity=b.id))
        from .authority import Authority, cash_forecast
        from .leadership import Leadership
        authority=Authority(Engine(world));record,_=Leadership(Engine(world)).director(b.id,False)
        keys={'manager:'+b.id,authority.key(b,record)}
        if b.status!='closed':
            contracts=[c for key in sorted(keys) if key in authority.contracts() for _,c in authority.chain(key)]
            for contract in contracts:
                forecast=cash_forecast(world,b.id,contract['horizon'])
                if forecast['available']<contract['cash_reserve']:
                    add('reserve',b.id,b.id,'Delegated cash reserve breached · '+b.name,
                        'Known obligations leave less cash than your authority policy permits. Review funding or reduce commitments.',
                        'management',amount=contract['cash_reserve']-forecast['available'],priority=0)
                    break
    from .specialists import LICENSES
    from .leadership import review
    positions={p.id:p for p in world.positions};people={p.id:p for p in world.people}
    for emp in world.employments:
        if emp.employer not in names or emp.status!='active':continue
        person=people[emp.person_id];pos=positions[emp.position_id]
        license=pos.required_license or LICENSES.get(pos.role)
        if license and person.licenses.get(license,'')<today:
            in_progress=any(p['kind']=='license' and p.get('person_id')==person.id and p['status']=='active' for p in s.get('plans',[]))
            already_open=any(d['status']=='open' and d.get('source','').startswith('license:'+emp.id+':') for d in s.get('decisions',[]))
            proposed=any(r['status'] in ('open','deferred') and r['action']=='renew_license' and r['args'].get('employment_id')==emp.id for r in s.get('management_requests',[]))
            if not in_progress and not already_open and not proposed:
                add('license',emp.id,emp.employer,'Credential renewal · '+person.name,
                    license.replace('_',' ').title()+' is missing or expired. Qualified duties remain unavailable until the credential is valid.',
                    'workforce','renew_license',dict(employment_id=emp.id,license=license),amount=25000)
        pay=review(world,emp)
        if pay['overdue'] and not any(r['status'] in ('open','deferred') and r['key']=='raise:'+emp.id for r in s.get('management_requests',[])):
            add('raise',emp.id,emp.employer,'Annual pay review · '+person.name,
                f"Expected raise {pay['percent']}%; adds ${pay['increase']/100:,.2f} to monthly base pay. Review compensation and funding.",
                'employee',targets=dict(employment_id=emp.id),due=pay['due'],amount=pay['annual_cost'])
    # Stable source IDs prevent repeat visits/days from creating duplicate inbox records.
    result.sort(key=lambda r:(r['status']=='deferred',r['priority'],r['due'] or '9999',r['entity_name'],r['id']))
    return result


def count(world):
    return sum(r['status']=='open' for r in items(world))


def focus(view, world, identifier):
    # Keep the same invoice visible after a request clears its inbox entry.
    # Cards already contain only records under the player's ownership and scope.
    if identifier.startswith('invoice:'):
        for card in view.get('collection_cards',[]):
            if card['id']==identifier[len('invoice:'):]:
                card['focused']=True
                if card['forms'] and card['forms'][0]['action']=='recover_invoice':
                    card['forms'][0].update(anchor='invoice-recovery-choice',expanded=True)
        return
    row=next((r for r in items(world) if r['id']==identifier and r['page']==view['page']),None)
    if not row:return
    for f in view['forms']:
        if f['action']!=row['action']:continue
        if any(field['kind']=='hidden' and field['name'] in row['targets'] and field['value']!=row['targets'][field['name']] for field in f['fields']):continue
        for field in f['fields']:
            if field['name'] not in row['targets']:continue
            value=row['targets'][field['name']]
            if field['kind'] in ('select','multiselect') and value not in {o['value'] for o in field['options']}:continue
            field['value']=value
        f['focused']=True
        view['notes'].insert(0,'From your decision inbox: '+row['title']+'. '+row['detail'])
        break


def decline_offer(engine, identifier):
    from .domain import RuleError
    row=next((r for r in items(engine.world) if r['id']==identifier and r['kind'] in ('tenant_offer','sale_offer','supplier_offer')),None)
    if not row:raise RuleError('This offer is no longer available under your ownership.')
    key=identifier.split(':',1)[1];s=engine.world.systems
    pool=(s.get('tenant_offers',[]) if row['kind']=='tenant_offer' else s.get('supplier_offers',[]) if row['kind']=='supplier_offer'
          else [o for listing in s.get('property_listings',{}).values() for o in listing.get('offers',[])])
    offer=next(o for o in pool if o['id']==key)
    offer.update(status='declined',declined_on=engine.world.date)
    engine.event('Offer declined',row['title']+'. No contract or payment was committed.')
    return 'Offer declined. Other offers remain available; no cash was spent.'


def inbox_view(world):
    from .campaign_views import form, hidden, field, choices, table
    from .business_views import entity_names
    from .routine_management import ready_property_care
    manager_care=ready_property_care(world)
    names=entity_names(world);rows=items(world,manager_care)
    properties={p.id:p for p in world.properties}
    care_queue=[dict(business=names[r['business_id']],property=properties[r['args']['property_id']].name,
                     kind=r['args']['kind'],url='/?page=property&property_id='+r['args']['property_id']+'&scope='+r['business_id'])
                for r in world.systems.get('management_requests',[]) if r['id'] in manager_care]
    for row in rows:
        row['forms']=[]
        if row['kind']=='time_off':
            row['forms'].append(form('time_off_decide','Review time-off request','Paid leave preserves wages. Unpaid leave removes wage accrual for the approved calendar dates; benefits continue. Approval reserves entitlement and reduces scheduled work only on those dates.',
                [hidden('request_id',row['source']['id']),field('choice','Decision','approve','select',choices({'approve':'Approve','decline':'Decline'}))]))
        if row['kind']=='decision':
            d=row['source']
            row['forms'].append(form('decide','Respond to '+d['title'],d.get('default',''),
                [hidden('decision_id',d['id']),field('choice','Response',next(iter(d['options'])),'select',choices(d['options']))]))
        if row['kind']=='license' or (row['kind']=='decision' and row['action']=='renew_license'):
            row['forms'].append(form('renew_license','Renew the required credential','The employer pays $250. Training takes 30 days; licensed coverage remains unavailable until completion.',
                [hidden(k,v) for k,v in row['targets'].items()],button='Review credential renewal →'))
        elif row['kind']=='management':
            r=row['source'];row['detail']+=' '+r.get('recommendation','')+' '+r.get('risk','')
            from .recovery_navigation import recovery_links
            row['resolution_links']=recovery_links(world,r['detail'],r['args'])
            if r['status']=='open':
                row['forms'].append(form('management_approve','Review management approval','The action rechecks funding, staff and current conditions.',[hidden('request_id',r['id'])],button='Review approval →'))
                row['forms'].append(form('management_defer','Defer for seven days','No approval is granted; existing obligations still apply.',[hidden('request_id',r['id'])],button='Review deferral →'))
            else:
                row['forms'].append(form('management_reopen','Return request to review','Bring this deferred request back to the inbox without approving it.',[hidden('request_id',r['id'])],button='Return to review'))
        elif row['kind'] in ('tenant_offer','sale_offer','supplier_offer'):
            row['forms'].append(form('inbox_decline_offer','Decline this offer','Declines only this offer. Other choices and existing obligations remain.',[hidden('inbox_id',row['id'])],button='Review decline →'))
    history=[(names[d['entity']],d['title'],d['options'].get(d.get('choice'),''),d.get('resolved',''))
             for d in reversed(world.systems.get('decisions',[])) if d['status']=='resolved' and d['entity'] in names][:100]
    people={p.id:p.name for p in world.people};employments={e.id:e for e in world.employments}
    for r in reversed(world.systems.get('time_off_requests',[])):
        if r['status']!='pending' and r['entity'] in names:
            emp=employments[r['employment_id']]
            history.append((names[r['entity']],'Time off · '+people[emp.person_id],r['status'].title()+' · '+r['reviewer'],r['resolution']))
    history=sorted(history,key=lambda row:row[3],reverse=True)[:100]
    from .time_off import review_status
    manager_leave=[]
    for r in world.systems.get('time_off_requests',[]):
        if r['status']!='pending' or r['entity'] not in names or employments[r['employment_id']].status!='active':continue
        review=review_status(world,r)
        if review['state']=='manager':
            manager_leave.append(dict(name=people[employments[r['employment_id']].person_id],business=names[r['entity']],
                review=review,url='/?page=employee&employment_id='+r['employment_id']+'&scope='+r['entity']+'#employee-time-off'))
    return dict(page='inbox',title='Decision inbox',intro='Every outstanding approval, proposal and operating issue in one place. Items follow their saved records and clear when handled here or on the relevant screen.',
        metrics=[('Needs your attention',sum(r['status']=='open' for r in rows)),('Overdue',sum(bool(r['due']) and r['due']<world.date and r['status']=='open' for r in rows)),('Deferred',sum(r['status']=='deferred' for r in rows))],
        inbox_items=rows,manager_leave=manager_leave,manager_care=care_queue,forms=[],notes=['All owned businesses and personal property are included. Cash exposure can be an amount owed, proposed spending or a claim; it is not a combined bill.'],links=[],
        tables=[table('Resolved decisions',['Account','Title','Choice','Resolved'],history)])
