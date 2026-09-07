"""Named service project controls and recorded delivery outcomes."""
from .campaign_views import field, hidden, choices, form, table, money
from .service_products import PRODUCTS


def extend(view, world, names, businesses, employees, props, scope):
    boptions = choices({b.id:b.name for b in businesses if b.status=='operating'})
    people = {p.id:p for p in world.people}
    recipient = scope if any(b.id==scope for b in businesses) else businesses[0].id if businesses else ''
    providers = choices({'outside':'Outside specialists', **{b.id:b.name for b in businesses if b.status=='operating'}})
    if view['page']=='home_office':
        from .business_models import INDUSTRY_ROLES
        roles=choices({r:r.replace('_',' ').title() for b in businesses for r in INDUSTRY_ROLES[b.industry]})
        for product,(department,title,effort) in PRODUCTS.items():
            if product=='property_representation':continue
            fields=[hidden('department',department),hidden('product',product),field('recipient','Receiving business',recipient,'select',boptions),
                    field('provider','Service provider','outside','select',providers),field('mode','Delivery arrangement','outside','select',choices({'outside':'Outsourced','internal':'Internal','mixed':'Mixed'}))]
            if product in ('role_search','assessment','succession'):
                fields.append(field('role','Role being filled or assessed','manager','select',roles))
            if product=='assessment':
                fields.append(field('target_id','Candidate','','select',choices({p.id:p.name for p in world.people if p.candidate})))
            elif product=='onboarding':
                fields.append(field('target_id','Employee','','select',choices({e.id:people[e.person_id].name+' / '+names[e.employer] for e in employees})))
            fields += [field('priority','Priority (1 highest)',2,'number',minimum=1,maximum=5),field('days','Deadline in days',14,'number',minimum=1,maximum=180)]
            detail=f'{effort//60} provider hours; outside reservation {money(effort*150)}. '
            detail += {'role_search':'Applicants retain ordinary abilities and offer expectations.',
                'assessment':'Records uncertain skill estimates and actual credentials; no guaranteed hire.',
                'onboarding':'Reserves two paid employee hours, at most one per scheduled day, as well as HR delivery.',
                'succession':'Ranks existing employees and credential gaps. Promotion requires a separate offer into a vacancy.',
                'pos_deployment':'Improves staffed checkout throughput. Use wears the system down; support requires paid work.',
                'inventory_integration':'Uses observed demand to order smaller inventory batches, reducing committed stock cash.',
                'system_support':'Restores deployed system condition through qualified work.'}[product]
            view['forms'].append(form('service_request',title,detail,fields))
        unfinished={t['id']:t['id']+' / '+t.get('product',t['department']) for t in world.systems.get('service_tasks',[]) if t['status'] in ('queued','working')}
        view['forms'].append(form('cancel_service','Cancel unfinished service work','Delivered labor remains an expense. Unused prepaid outside capacity returns as cash; no work product is granted.',[field('task_id','Project','','select',choices(unfinished))]))
        view['tables'].append(table('Succession shortlists',['Review / role','Employee','Estimated skill','Credentials','Development / next action'],
            [(t['id']+' / '+t['role'],people[r['person_id']].name,str(r['low'])+'–'+str(r['high']),'Eligible' if r['eligible'] else 'Gap',r['development'])
             for t in world.systems.get('service_tasks',[]) for r in t.get('shortlist',[])], 'Dated assessments retain uncertainty. Vacancies, current credentials, pay and authority are checked when promoting.'))
        view['tables'].append(table('Deployed systems',['Business / system','Installed','Condition','Last support','Delivery source'],
            [(names.get(bid,bid)+' / '+PRODUCTS[k][1],s['installed'],str(s['condition'])+'/100',s['last_support'],s['source']) for bid,systems in world.systems.get('deployed_systems',{}).items() for k,s in systems.items()]))
        view['tables'].append(table('Onboarding participation',['Project','Employee','Provider minutes remaining','Paid employee minutes','Status'],
            [(t['id'],next((people[e.person_id].name for e in world.employments if e.id==t['target_id']),t['target_id']),t['remaining'],str(t['participant_done'])+' / '+str(t['participant_required']),t['status']) for t in world.systems.get('service_tasks',[]) if t.get('product')=='onboarding']))
    if view['page']=='property_workbench':
        prop_names={p.id:p.name for p in props}
        requests=[r for r in world.systems.get('property_requests',[]) if r['property_id'] in prop_names]
        view['tables'].insert(0,table('Tenant maintenance requests',['Request / property','System','Reported / current condition','Deadline','Status','Work / outcome'],
            [(r['id']+' / '+prop_names[r['property_id']],r['system'],str(r['observed_condition'])+' / '+str(r['current_condition']),r['due'],r['status'],r['work_id']+' '+r['outcome']) for r in requests],
            'Requests reflect existing occupied-property condition. Overdue unresolved requests lower the tenant’s renewal ceiling by 10%; completed work must restore serviceable condition.'))
        view['forms'].insert(0,form('respond_property_request','Respond to tenant maintenance request','Book real work for the reported system. Staff time, materials, downtime and quality still apply; booking does not resolve the request.',
            [field('property_id','Property','','select',choices(prop_names)),field('request_id','Request','','select',choices({r['id']:prop_names[r['property_id']]+' / '+r['system']+' / '+r['due'] for r in requests if r['status'] in ('open','overdue')})),
             field('kind','Work','repair','select',choices({'repair':'Routine repair','emergency':'Emergency repair','replacement':'Replace system'})),field('provider','Contractor','outside','select',providers)]))
