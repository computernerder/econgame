import copy
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_campaign_product import client_for
from economic_simulation.domain import new_game,Engine,World,RuleError
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_models import Position,Employment
from economic_simulation.property_development import Development,BLUEPRINTS,representation
from economic_simulation.property_operations import PropertyOperations,systems_for
from economic_simulation.service_office import ServiceOffice

def funded():
    e=new_game(23);e.post('personal','test-funds','Test capital',{'asset:cash':1000000000,'equity:capital':-1000000000})
    return e

def buy(e,land=False):
    p=next(p for p in e.world.properties if p.status=='market' and (p.category=='land')==land and not p.id.startswith('covenant'))
    e.action('buy',dict(property_id=p.id),'test-buy-'+p.id);return p

def employee(e,role='electrician'):
    # Use the established startup action, then attach a test employment to that employer.
    e.action('start_business',dict(industry='office',name='Test Home Office',region='Rutland County',entity='personal'),'office-start')
    b=e.world.businesses[-1];b.status='operating';b.opening_on=None
    rules=BusinessRules(e);person=rules.make_person(role);pos=Position(id='test-pos-'+role,business_id=b.id,role=role)
    e.world.positions.append(pos)
    emp=Employment(id='test-emp-'+role,person_id=person.id,employer=b.id,position_id=pos.id,salary=400000,weekly_hours=40,status='active',start_date=e.world.date)
    e.world.employments.append(emp)
    return b,emp,person,rules

@pytest.mark.parametrize('blueprint',list(BLUEPRINTS))
def test_buildings_are_funded_real_assets_with_compatible_industries(blueprint):
    e=funded();p=buy(e,True);d=Development(e);basis=p.basis
    d.action(dict(property_id=p.id,blueprint=blueprint,level=1),'build')
    job=e.world.systems['developments'][-1]
    assert p.status=='building' and p.full_rent==0
    assert e.world.accounts['personal']['asset:development_reserve']==job['total']
    with pytest.raises(RuleError):e.action('rent',dict(property_id=p.id),'no-rent')
    with pytest.raises(RuleError):d.action(dict(property_id=p.id),'double-build')
    for i in range(job['days']):
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat();d.tick()
    assert p.status=='vacant' and p.category==BLUEPRINTS[blueprint][1]
    assert p.specialization==list(BLUEPRINTS[blueprint][2]) and p.basis==basis+job['spent']
    assert job['spent']+job['refunded']==job['total'] and job['prepaid']==0
    assert all(v['age']==0 for v in systems_for(e.world,p).values())
    assert not any(l['property_id']==p.id for l in e.world.systems['leases'])
    e.validate()

def test_scale_limits_and_insufficient_funding():
    e=new_game();p=buy(e,True);d=Development(e)
    assert d.quote(p,'boutique',2)['area']==d.quote(p,'boutique',1)['area']*2
    with pytest.raises(RuleError,match='small'):d.quote(p,'factory',3)
    before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError,match='cash'):d.action(dict(property_id=p.id,blueprint='factory',level=1),'no-funds')
    assert e.world.to_dict()==before

def test_owner_repairs_consume_materials_time_and_decision_capacity():
    e=funded();p=buy(e);ops=PropertyOperations(e);condition=ops.ensure(p)['interior']['condition'];cash=e.world.cash('personal')
    e.action('property_work',dict(property_id=p.id,provider='owner',system='interior',kind='repair'),'owner-repair')
    job=e.world.systems['property_work'][-1]
    assert cash-e.world.cash('personal')==job['materials']
    e.action('inspect_property',dict(property_id=p.id),'decision-one')
    e.action('inspect_property',dict(property_id=p.id),'decision-two')
    with pytest.raises(RuleError,match='two discretionary'):e.action('inspect_property',dict(property_id=p.id),'decision-three')
    ops.tick();assert job['remaining']==480
    e.action('outsource_property_work',dict(property_id=p.id,work_id=job['id']),'outsource')
    e.action('inspect_property',dict(property_id=p.id),'time-restored')
    for _ in range(2):
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat();ops.tick()
    assert job['status']=='complete' and ops.ensure(p)['interior']['condition']>condition
    assert job['actual_cost']==job['materials']+48000
    e.validate()

@pytest.mark.parametrize('system,license_name',[('electrical','electrical'),('plumbing','plumbing'),('heating_cooling','hvac')])
def test_trade_license_not_replaceable_by_unlicensed_capacity(system,license_name):
    e=funded();p=buy(e);b,emp,person,rules=employee(e);person.skills['maintenance']=90
    person.licenses={};args=dict(property_id=p.id,provider=b.id,system=system,kind='repair')
    with pytest.raises(RuleError,match='license'):e.action('property_work',args,'unlicensed')
    with pytest.raises(RuleError,match='Owner work'):e.action('property_work',{**args,'provider':'owner'},'owner-trade')
    person.licenses.update({license_name:'2030-01-01','electrical':'2030-01-01'})
    e.action('property_work',args,'licensed');job=e.world.systems['property_work'][-1]
    e.world.date='2026-01-12';buckets,_=rules.work(b,date.fromisoformat(e.world.date));before=sum(buckets['electrician'])
    PropertyOperations(e).deliver(rules,b,buckets)
    assert job['remaining']<720 and sum(buckets['electrician'])<before
    assert job['staff']==[emp.id] and job['actual_cost']>job['materials']
    # Expiration stops the same job even if someone supplies an unrelated bucket.
    person.licenses[license_name]='2020-01-01';remaining=job['remaining']
    PropertyOperations(e).deliver(rules,b,{'electrician':[999]*24,'maintenance':[999]*24})
    assert job['remaining']==remaining
    e.validate()

def test_agent_queue_consumes_work_before_one_specific_closing_discount():
    e=funded();b,emp,p,rules=employee(e,'real_estate_agent');office=ServiceOffice(e)
    prop=next(p for p in e.world.properties if p.status=='market');ordinary=e.quote('buy',prop.id)['fee']
    office.action('department_configure',dict(provider=b.id,department='real_estate_agent',staff=emp.id,tools=1,regions=prop.region),'department')
    office.action('service_request',dict(provider=b.id,recipient='personal',department='real_estate_agent',product='property_representation',mode='internal',target_id=prop.id),'request')
    assert e.quote('buy',prop.id)['fee']==ordinary
    job=e.world.systems['service_tasks'][-1];e.world.date='2026-01-12'
    for _ in range(6):
        buckets,_=rules.work(b,date.fromisoformat(e.world.date));office.deliver(rules,b,buckets)
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    assert job['status']=='complete' and job['staff']==[emp.id] and job['internal_cost']>0
    quote=e.quote('buy',prop.id);assert quote['fee']<ordinary
    assert e.quote('buy',prop.id,b.id)['fee']==ordinary
    e.action('buy',dict(property_id=prop.id),'represented-buy')
    assert job['fee_avoided']==ordinary-quote['fee'] and not representation(e.world,prop,'personal')
    e.validate()

def test_selected_expired_agent_cannot_borrow_valid_agent_hours():
    e=funded();b,emp,p,rules=employee(e,'real_estate_agent');p.licenses['real_estate']='2020-01-01'
    office=ServiceOffice(e);office.action('department_configure',dict(provider=b.id,department='real_estate_agent',staff=emp.id),'dept')
    prop=next(p for p in e.world.properties if p.status=='market')
    office.action('service_request',dict(provider=b.id,recipient='personal',department='real_estate_agent',product='property_representation',mode='internal',target_id=prop.id),'request')
    e.world.date='2026-01-12';office.deliver(rules,b,{'real_estate_agent':[480]*24})
    assert e.world.systems['service_tasks'][-1]['worked']==0

def test_hr_capacity_changes_recruiting_and_screening_without_free_stats():
    from economic_simulation.workforce import Workforce
    e=funded();b,emp,person,rules=employee(e,'hr');e.world.date='2026-01-12'
    wf=Workforce(e);candidate=rules.make_person('manager',True);skills=copy.deepcopy(candidate.skills)
    wf.action('recruit',dict(business_id=b.id,role='manager'),'ordinary')
    ordinary=e.world.systems['plans'][-1]
    e.world.systems.setdefault('specialist_work',{})[b.id]=[dict(date=e.world.date,remaining={'hr':360},worked={'hr':360})]
    wf.action('recruit',dict(business_id=b.id,role='manager'),'supported')
    supported=e.world.systems['plans'][-1]
    assert supported['cost']<ordinary['cost'] and supported['due']<ordinary['due']
    assert supported['applicants_count']==5 and ordinary['applicants_count']==3
    wf.action('screen_candidate',dict(business_id=b.id,person_id=candidate.id,role='manager'),'screen')
    screening=e.world.systems['hr_screenings'][-1]
    assert screening['minutes']==120 and screening['cost']==2500 and screening['high']-screening['low']==5
    assert candidate.skills==skills
    from economic_simulation.specialists import available
    assert available(e.world,b.id,'hr')==0
    e.validate()

def test_one_licensed_employee_cannot_supply_two_full_days_of_work():
    e=funded();p=buy(e);b,emp,person,rules=employee(e);person.skills['maintenance']=90
    person.licenses['plumbing']='2030-01-01';e.world.date='2026-01-12'
    ops=PropertyOperations(e)
    for system in ('electrical','plumbing'):
        ops.action('property_work',dict(property_id=p.id,system=system,kind='replacement',provider=b.id),'work-'+system)
    buckets,_=rules.work(b,date.fromisoformat(e.world.date));available=sum(buckets['electrician'])
    ops.deliver(rules,b,buckets)
    assert sum(j['labor_used'] for j in e.world.systems['property_work'])<=available
    assert sum(buckets['electrician'])==0
    spent=sum(j['actual_cost']-j['materials'] for j in e.world.systems['property_work'] if j['labor_used'])
    assert spent<=sum(v for k,v in e.world.accounts[b.id].items() if k in ('expense:wages','expense:benefits','expense:payroll_tax'))

def test_absent_trade_employee_cannot_work_and_can_be_replaced():
    e=funded();p=buy(e);b,emp,person,rules=employee(e);person.skills['maintenance']=90
    ops=PropertyOperations(e);ops.action('property_work',dict(property_id=p.id,system='electrical',provider=b.id),'electrical')
    e.world.date='2026-01-12';emp.leave_until='2026-02-01';buckets,_=rules.work(b,date.fromisoformat(e.world.date))
    ops.deliver(rules,b,buckets);job=e.world.systems['property_work'][-1];assert job['remaining']==720
    ops.action('outsource_property_work',dict(property_id=p.id,work_id=job['id']),'rescue')
    ops.tick();assert job['remaining']==480
    e.validate()

def test_development_persists_and_daily_replay_reconciles(game):
    p=next(p for p in game.world.properties if p.category=='land')
    act(game,'buy',property_id=p.id);act(game,'develop_property',property_id=p.id,blueprint='homes',level=1)
    initial=copy.deepcopy(game.world);replay=Engine(copy.deepcopy(initial))
    for _ in range(3):replay.advance_day()
    step(game,3)
    actual=copy.deepcopy(game.world.to_dict());expected=replay.world.to_dict();actual['revision']=expected['revision']
    assert actual==expected
    assert game.store.load().to_dict()==game.world.to_dict();game.store.audit(game.world)
    with client_for(game) as client:
        for url in ('/?page=property&property_id='+p.id,'/?page=property_workbench','/?page=home_office','/?page=market&category=land'):
            response=client.get(url);assert response.status_code==200 and 'Restart Empire Manager' not in response.text
        assert 'Construction projects' in client.get('/?page=property_workbench').text
