"""Named property service plans, delivery records and staffing bottlenecks."""
from .campaign_views import choices,field,hidden,form,table,money
from .business_views import entity_names
from .property_services import SERVICES,care,presentation,protection


def property_service_view(world,scope):
    names=entity_names(world);properties={p.id:p for p in world.properties}
    owned=[p for p in world.properties if p.owner in names and p.status not in ('sold','expired')]
    owned.sort(key=lambda p:(p.owner!=scope,p.name))
    businesses=[b for b in world.businesses if b.id in names and b.industry in SERVICES]
    jobs=[j for j in world.systems.get('property_service_jobs',[]) if j['owner'] in names]
    view=dict(page='property_services',title='Property service businesses',intro='Choose outside expertise or your own cleaning, landscaping and security crews. Staff, supplies, travel and equipment limit delivery; property plans use capacity that could serve outside customers.',forms=[],tables=[],metrics=[],notes=[],links=[])
    from .routine_management_views import controls
    owners={p.owner for p in owned}
    for business in world.businesses:
        if business.id in owners and business.id in names:view['forms'].append(controls(world,business))
    view['notes'].append('Routine visits are managed by the property-owning business’s manager, with director cover when no manager is available. Personal properties remain owner-managed. Manual cancellation stops renewal until you book another plan. Review manager policies and activity below.')
    view['forms'].append(form('property_service','Book a property service plan','The property owner prepays the complete plan. The manager can renew completed visits when routine care and renewal are enabled; cancelling a plan stops its renewal. Internal companies must fund supplies before delivery releases payment. Internal quoted rates are 80% of the outside rate; actual wages and supplies still determine group cost.',[
        field('property_id','Property / paying owner','','select',choices({p.id:p.name+' / '+names[p.owner] for p in owned})),
        field('kind','Service','cleaning','select',choices({k:k.title() for k in SERVICES})),
        field('provider','Provider','outside','select',choices({'outside':'Outside specialists',**{b.id:b.name+' / '+b.industry for b in businesses if b.status=='operating'}})),
        field('visits','Number of visits',4,'number',minimum=1,maximum=20),field('interval','Days between completed visits',7,'number',minimum=1,maximum=30),field('priority','Priority (1 is highest)',2,'number',minimum=1,maximum=5)]))
    view['forms'].append(form('cancel_property_service','Cancel undelivered visits','Unused prepaid money returns to the original payer. Delivered work and partial-visit costs remain expenses.',[field('job_id','Plan','','select',choices({j['id']:properties[j['property_id']].name+' / '+j['kind']+' / '+j['id'] for j in jobs if j['status']=='working'}))]))
    positions={p.id:p for p in world.positions};people={p.id:p for p in world.people}
    guards=[emp for emp in world.employments if emp.employer in names and emp.status=='active' and positions[emp.position_id].role=='security_guard']
    if guards:
        view['forms'].append(form('renew_license','Renew a guard credential','The employer pays $250 for a 30-day credential course. Expired coverage stays unavailable until completion; managers can also propose renewal within their authority.',[field('employment_id','Guard / current expiry','','select',choices({emp.id:people[emp.person_id].name+' / '+names[emp.employer]+' / '+people[emp.person_id].licenses.get('security_guard','Missing') for emp in guards})),hidden('license','security_guard')]))
    view['tables'].append(table('Property care and patrol coverage',['Property / owner','Cleanliness','Grounds','Vacancy offer factor','Recent patrol risk reduction'],[(p.name+' / '+names[p.owner],str(care(world,p)['cleanliness'])+'/100',str(care(world,p)['grounds'])+'/100',str(presentation(world,p))+'%',str(protection(world,p))+' percentage points') for p in owned],'Condition declines with time and use. Completed visits improve presentation or recent patrol coverage; care cannot repair a damaged roof or guarantee tenant demand or safety.'))
    view['tables'].append(table('Service plans',['Property / service','Provider','Visits / status','Next visit / deadline','Reserved / spent / refunded','Result'],[(properties[j['property_id']].name+' / '+j['kind'],names.get(j['provider'],'Outside specialists'),str(j['completed_visits'])+'/'+str(j['visits'])+' / '+j['status'],j['next_visit']+' / '+j['due'],money(j['prepaid'])+' / '+money(j['expense'])+' / '+money(j['refunded']),j['outcome']) for j in jobs]))
    view['tables'].append(table('Provider operations',['Business','Date','Internal / external hours','Travel hours','Unused hours','Supplies consumed','Constraint'],[(b.name,b.last_day.get('date','No operating day'),round(b.last_day.get('internal_minutes',0)/60,1).__str__()+' / '+str(round(b.last_day.get('external_minutes',0)/60,1)),round(b.last_day.get('travel_minutes',0)/60,1),round(b.last_day.get('unused_capacity',0)/60,1),money(b.last_day.get('supplies',0)),b.last_day.get('bottleneck','Inspect the team to plan opening roles and workload.')) for b in businesses]))
    view['links']=[dict(label='Manager policies and action log',url='/?page=management#business-policies'),dict(label='Buy or start a service company',url='/?page=business_market&scope='+scope),dict(label='Property repairs and renovations',url='/?page=property_workbench&scope='+scope)]
    return view
