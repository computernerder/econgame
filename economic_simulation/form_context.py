"""Read-only field dependencies shared by initial HTML and interactive forms."""
from .business_views import entity_names
from .business_models import INDUSTRY_ROLES
from .industries import SALES


def matches(conditions, values):
    if isinstance(conditions, list):
        return any(matches(condition, values) for condition in conditions)
    return all(values.get(key, '') in (allowed if isinstance(allowed, list) else [allowed])
               for key, allowed in conditions.items())


def initial_state(form):
    """Use the same ordered dependencies as the browser, without mutating the world."""
    for field in form['fields']:
        if field['kind']=='select' and field['name'] not in form['field_context']:
            if field['value'] not in [o['value'] for o in field['options']]:
                field['value']=field['options'][0]['value'] if field['options'] else ''
    values={f['name']:str(f['value']) for f in form['fields']}
    for field in form['fields']:
        rule=form['field_context'].get(field['name'])
        if not rule:continue
        field['hidden']=not matches(rule.get('show',{}),values)
        field['required']=rule.get('required',False) and not field['hidden']
        if 'options' in rule:
            field['options']=[o for o in rule['options'] if matches(o.get('when',{}),values)]
            if field['value'] not in [o['value'] for o in field['options']]:
                field['value']=field['options'][0]['value'] if field['options'] else ''
            values[field['name']]=field['value']
        for label in rule.get('labels',[]):
            if matches(label['when'],values):field['label']=label['text'];break
    form['context_errors']=[rule['empty'] for field in form['fields']
        if (rule:=form['field_context'].get(field['name'])) and field.get('required')
        and field['kind']=='select' and not field['options']]
    form['context_notes_current']=[note['text'] for note in form.get('context_notes',[]) if matches(note.get('when',{}),values)]


def attach_service(form,world):
    fields={f['name']:f for f in form['fields']}
    # Invoice-specific quick actions have fixed values; keep that exact target.
    if 'mode' not in fields or 'provider' not in fields:return
    names=entity_names(world)
    businesses={b.id:b for b in world.businesses if b.id in names}
    employees=[e for e in world.employments if e.employer in businesses and e.status=='active']
    people={p.id:p for p in world.people}
    tasks=world.systems.get('service_tasks',[])
    product=fields.get('product',{}).get('value','')
    generic=not product
    context={}
    def rule(name,**kwargs):
        if name in fields:context[name]=kwargs
    def option(value,label,**when):return dict(value=value,label=label,when=when)

    if generic:
        # Closing representation has a dedicated, property-specific request.
        fields['department']['options']=[o for o in fields['department']['options'] if o['value']!='real_estate_agent']
        for o in fields['department']['options']:
            if o['value']=='legal':o['label']='Legal services'
        rule('matter',show={'department':'legal'},required=True,
             options=fields['matter']['options'],empty='Choose the legal work needed.')
        form['description']='Choose the receiving account and service, then how to deliver the work. Only relevant people, transactions and departments are offered.'
    if form.get('shared_provider'):
        from .service_products import PRODUCTS
        if product in PRODUCTS and product!='property_representation':
            detail=form['description'].split('. ',1)[-1]
            form['description']=f"{PRODUCTS[product][2]//60} qualified hours from {names[form['shared_provider']]}. Paid staff time is charged as delivered; no outside reservation. "+detail
        elif generic:
            form['description']='Choose the receiving account for this team’s work. Internal staff time is charged as delivered. Only relevant targets are offered.'
    recipients=[]
    for o in fields['recipient']['options']:
        b=businesses.get(o['value'])
        if product in ('role_search','assessment','succession','onboarding','pos_deployment','inventory_integration','system_support'):
            if not b or b.status!='operating':continue
        if product in ('pos_deployment','inventory_integration'):
            if b.industry not in SALES or product in world.systems.get('deployed_systems',{}).get(b.id,{}):continue
            if any(t.get('product')==product and t['recipient']==b.id and t['status'] in ('queued','working') for t in tasks):continue
        if product=='system_support' and not world.systems.get('deployed_systems',{}).get(b.id):continue
        when={'department':['accounting','finance','legal']} if generic and not b else {}
        recipients.append({**o,'when':when})
    rule('recipient',options=recipients,required=True,empty='No eligible receiving account for this work. Choose another service or complete its required setup first.')

    providers=[]
    from .internal_property_services import agent_department
    departments=dict(world.systems.get('departments',{}))
    for b in businesses.values():
        department=agent_department(world,b)
        if department:departments.setdefault(department['id'],department)
    for dept in departments.values():
        b=businesses.get(dept['provider'])
        if not b or b.status!='operating':continue
        if form.get('shared_provider') and b.id!=form['shared_provider']:continue
        recipients_in_range=[]
        for r in recipients:
            receiver=businesses.get(r['value'])
            # Personal property work determines its county from the target below.
            if receiver is None or receiver.region in dept['regions'] or dept['role']=='real_estate_agent':recipients_in_range.append(r['value'])
        providers.append(option(b.id,b.name,department=dept['role'],recipient=recipients_in_range))
    rule('provider',show={'mode':['internal','mixed']},options=providers,required=True,
         empty='No configured department covers this service and receiving business. Configure a department with county coverage, or choose outsourced delivery.')
    if fields['provider']['kind']!='hidden':fields['provider']['label']='Delivering internal department'
    if 'role' in fields:
        roles={role:[] for b in businesses.values() for role in INDUSTRY_ROLES[b.industry]}
        for b in businesses.values():
            for role in INDUSTRY_ROLES[b.industry]:roles[role].append(b.id)
        from .ui_workflows import role_label
        rule('role',options=[option(r,role_label(r),recipient=ids) for r,ids in roles.items()],required=True,
             empty='No eligible role for this receiving business.')

    if 'target_id' in fields and fields['target_id']['kind']!='hidden':
        targets=[];show={};labels=[]
        if generic:
            show=[{'department':'training'},{'department':'legal','matter':['negotiation','collection','dispute']}]
            labels=[dict(when={'department':'training'},text='Employee to develop'),
                    dict(when={'matter':'negotiation'},text='Purchase offer to negotiate'),
                    dict(when={'matter':['collection','dispute']},text='Overdue balance or open claim')]
            for b in world.businesses:
                if b.status=='market' and not b.owner and not b.market_parent and not any(t['target_id']==b.id and t['matter']=='negotiation' for t in tasks):
                    targets.append(option(b.id,b.name,department='legal',matter='negotiation'))
            for p in world.properties:
                if p.status=='market' and not p.owner and not any(t['target_id']==p.id and t['matter']=='negotiation' for t in tasks):
                    targets.append(option(p.id,p.name,department='legal',matter='negotiation'))
            from .customer_collections import overdue,busy
            for b in businesses.values():
                for invoice in b.receivables:
                    done=any(t['recipient']==b.id and t['target_id']==invoice['id'] and t['department']=='legal'
                             and t['matter'] in ('collection','dispute') and t['status']=='complete' for t in tasks)
                    if overdue(world,invoice) and not busy(world,b.id,invoice) and not done:
                        targets.append(option(invoice['id'],b.name+' / '+invoice['id']+' / overdue invoice',recipient=b.id,department='legal',matter=['collection','dispute']))
            for lease in world.systems.get('leases',[]):
                if lease['owner'] in names and lease['tenant']=='external' and lease['arrears']>0:
                    targets.append(option(lease['id'],lease['tenant_name']+' / overdue rent',recipient=lease['owner'],department='legal',matter=['collection','dispute']))
            for claim in world.systems.get('legal_claims',[]):
                if claim['owner'] in names and claim['status']=='open':
                    targets.append(option(claim['id'],claim['id']+' / documented claim',recipient=claim['owner'],department='legal',matter=['collection','dispute']))
        if generic or product=='onboarding':
            for emp in employees:
                if product=='onboarding' and any(t.get('product')==product and t['target_id']==emp.id and t['status']!='cancelled' for t in tasks):continue
                when={'recipient':emp.employer}
                if generic:when['department']='training'
                targets.append(option(emp.id,people[emp.person_id].name+' / '+names[emp.employer],**when))
        elif product=='assessment':
            targets=[option(p.id,p.name) for p in world.people if p.candidate]
        elif product in ('property_representation','transaction_review','transfer_consent'):
            for p in world.properties:
                allowed=[]
                for r in recipients:
                    rid=r['value']
                    if product=='property_representation':
                        if p.owner and p.owner!=rid:continue
                        if not p.owner and p.status!='market':continue
                        if any(t.get('product')==product and t['recipient']==rid and t['target_id']==p.id and t['status'] in ('queued','working') for t in tasks):continue
                    else:
                        terms=world.systems.get('transaction_terms',{}).get(p.id)
                        if p.owner or p.status!='market' or not terms:continue
                        if product=='transfer_consent':
                            if not terms['consent_required'] or rid not in terms['reviews']:continue
                            if any(t.get('product')==product and t['target_id']==p.id and t['recipient']==rid and t['status']!='cancelled' and not t.get('requires_specialist') for t in tasks):continue
                    allowed.append(rid)
                if allowed:
                    when={'recipient':allowed}
                    if product=='property_representation':when['provider']=[d['provider'] for d in departments.values() if d['role']=='real_estate_agent' and p.region in d['regions']]
                    targets.append(option(p.id,p.name,**when))
        else:targets=fields['target_id']['options']
        rule('target_id',show=show,options=targets,labels=labels,required=True,
             empty='No eligible target for this account and work. Select another account or work type; existing work and completed attempts are excluded.')

    # Resolve choices in dependency order on both server and browser.
    order=['department','product','recipient','mode','provider','matter','role','target_id']
    form['fields']=sorted(form['fields'],key=lambda f:order.index(f['name']) if f['name'] in order else len(order))
    form['field_context']=context
    form['context_notes']=[
        dict(when={'mode':'outside'},text='Outside specialists deliver this work. Standard reservations cost $90 per qualified hour; the review shows the actual reserve and any purchased service credit.'),
        dict(when={'mode':'internal'},text='The configured department uses paid staff time. Other queued work, county coverage, qualifications and availability determine completion.'),
        dict(when={'mode':'mixed'},text='Internal staff and reserved outside capacity share the work. The review includes the outside reserve; unused standard outside capacity is refunded.'),
    ]
    if generic:
        form['context_notes'] += [
            dict(when={'department':'accounting'},text='Prepares a dated report from this account’s recorded revenue, expenses, profitability and cash. No transaction or employee target is needed.'),
            dict(when={'department':'legal','matter':'template'},text='Prepares a routine transaction template for the receiving account. No individual transaction is needed.'),
            dict(when={'department':'legal','matter':'negotiation'},text='Negotiates an existing purchase offer. The counterparty can refuse; future concessions are not cash received.'),
        ]
    initial_state(form)


def attach(form,world):
    if form['action']=='service_request':attach_service(form,world)
    elif form['action']=='property_work':
        form['field_context']={'use':dict(show={'kind':'conversion'})}
        if form.get('shared_department'):
            fields={f['name']:f for f in form['fields']}
            form['field_context']['property_id']=dict(required=True,options=fields['property_id']['options'],
                empty='No owned building is in this team’s county coverage. Change coverage or use another contractor.')
            form['context_notes']=[dict(text='This repair uses the selected internal company. Electrical, plumbing and HVAC work require a current license. The review checks qualified staff, materials and current conditions.')]
        initial_state(form)
    elif form['action']=='respond_property_request':
        fields={f['name']:f for f in form['fields']}
        requests={r['id']:r for r in world.systems.get('property_requests',[])}
        form['field_context']={'request_id':dict(required=True,empty='No open maintenance request for this property.',
            options=[{**o,'when':{'property_id':requests[o['value']]['property_id']}} for o in fields['request_id']['options'] if o['value'] in requests])}
        initial_state(form)
