import copy,json,sqlite3
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_new_industries import purchase
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError,new_game,PREVIOUS_CONTENT_VERSION
from economic_simulation.business_rules import BusinessRules
from economic_simulation.property_services import PropertyServices,SERVICES,care,presentation,protection


def property_for(e,owner='personal'):
    p=next(p for p in e.world.properties if p.status=='market' and not p.id.startswith('covenant-'))
    e.action('buy',dict(property_id=p.id,entity=owner),'property-purchase-'+p.id)
    return p


def request(e,p,kind='cleaning',provider='outside',**kwargs):
    e.action('property_service',dict(property_id=p.id,kind=kind,provider=provider,**kwargs),'care-'+str(e.world.systems['next_id']))
    return e.world.systems['property_service_jobs'][-1]


def next_day(e):
    e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()


@pytest.mark.parametrize('industry',tuple(SERVICES))
def test_service_industry_acquisition_staffing_startup_and_real_operations(game,industry):
    bid=purchase(game,industry);step(game,10);b=next(b for b in game.world.businesses if b.id==bid)
    from economic_simulation.staffing import staffing_plan
    assert SERVICES[industry]['role'] in {r['role'] for r in staffing_plan(game.world,bid)['rows']}
    assert game.world.accounts[bid]['income:property_services']<0 and game.world.accounts[bid]['expense:property_service_supplies']>0
    assert b.receivables and game.world.accounts[bid]['asset:receivable']>0
    with client_for(game) as client:
        page=client.get('/?page=business&business_id='+bid)
        assert page.status_code==200 and 'Property service work' in page.text and 'Staff divide' in page.text
        if industry=='security':assert 'Renew a guard credential' in client.get('/?page=property_services').text
    act(game,'start_business',industry=industry,name='New '+industry,region='Rutland County')
    assert game.world.businesses[-1].status=='developing'
    game.store.audit(game.world)


def test_personal_property_services_need_no_company_and_only_completed_visit_has_effect(game):
    e=Engine(copy.deepcopy(game.world));p=property_for(e);p.usable_area=2400
    service=PropertyServices(e);before=e.world.cash('personal');job=request(e,p,visits=1)
    assert before-e.world.cash('personal')==job['paid'] and care(e.world,p)['cleanliness']==70
    e.world.date='2026-01-05';service.tick()
    assert job['worked']==240 and job['completed_visits']==0 and care(e.world,p)['cleanliness']==70
    next_day(e);service.tick()
    assert job['status']=='complete' and care(e.world,p)['cleanliness']>70 and job['prepaid']==0
    assert e.world.systems['property_cost_totals'][p.id]['services']==job['expense']
    e.validate()


def test_internal_plan_displaces_outside_revenue_and_eliminates_internal_profit(game):
    bid=purchase(game,'cleaning');base=Engine(copy.deepcopy(game.world));p=property_for(base);p.usable_area=3600;base.world.date='2026-01-19'
    baseline=copy.deepcopy(base.world);job=request(base,p,provider=bid,visits=1)
    from economic_simulation.business_views import group_profit
    before=group_profit(base.world,['personal',bid]);b=next(b for b in base.world.businesses if b.id==bid)
    rules=BusinessRules(base);rules.operate(b,date.fromisoformat(base.world.date))
    control=Engine(baseline);control_b=next(b for b in control.world.businesses if b.id==bid);BusinessRules(control).operate(control_b,date.fromisoformat(control.world.date))
    assert b.last_day['internal_minutes']>0 and b.last_day['external_minutes']<control_b.last_day['external_minutes']
    assert b.last_day['output']+b.last_day['travel_minutes']<=b.last_day['capacity']
    assert base.world.accounts['personal']['expense:internal_property_services:'+bid]==-base.world.accounts[bid]['income:internal_property_services:personal']
    external=sum(v for k,v in base.world.accounts[bid].items() if k.startswith(('income:','expense:')) and not k.startswith('income:internal_'))
    personal=-sum(v for k,v in base.world.accounts['personal'].items() if k.startswith(('income:','expense:')) and not k.startswith('expense:internal_'))
    assert group_profit(base.world,['personal',bid])==personal-external
    assert job['supplies']>0 and job['travel']==30
    base.validate()


def test_internal_jobs_share_capacity_by_priority_and_require_supply_cash(game):
    bid=purchase(game,'cleaning');e=Engine(copy.deepcopy(game.world));p=property_for(e);q=property_for(e);p.usable_area=q.usable_area=3600
    first=request(e,p,provider=bid,visits=1,priority=3);second=request(e,q,provider=bid,visits=1,priority=1)
    e.world.date='2026-01-19';b=next(b for b in e.world.businesses if b.id==bid)
    BusinessRules(e).operate(b,date.fromisoformat(e.world.date))
    assert second['status']=='complete' and 0<first['worked']<first['effort']
    e.post(bid,'empty-provider','Reserve withdrawal',{'asset:cash':-e.world.cash(bid),'equity:distributions':e.world.cash(bid)})
    before=first['worked'];next_day(e);BusinessRules(e).operate(b,date.fromisoformat(e.world.date))
    assert first['worked']==before
    e.validate()


def test_cancel_partial_work_refunds_only_undelivered_reserve(game):
    e=Engine(copy.deepcopy(game.world));p=property_for(e);p.usable_area=3600;job=request(e,p,visits=2)
    e.world.date='2026-01-05';PropertyServices(e).tick();spent=job['expense'];prepaid=job['prepaid'];cash=e.world.cash('personal')
    e.action('cancel_property_service',dict(job_id=job['id']),'cancel')
    assert job['status']=='cancelled' and job['expense']==spent and e.world.cash('personal')==cash+prepaid
    assert job['paid']==job['expense']+job['refunded'];e.validate()


def test_owner_or_provider_change_ends_plan_without_serving_new_owner(game):
    bid=purchase(game,'cleaning');e=Engine(copy.deepcopy(game.world));p=property_for(e);job=request(e,p,provider=bid)
    b=next(b for b in e.world.businesses if b.id==bid);b.status='closed'
    PropertyServices(e).tick();assert job['status']=='cancelled' and job['refunded']==job['paid']
    second=request(e,p);p.owner=bid;PropertyServices(e).tick()
    assert second['status']=='cancelled' and second['worked']==0


def test_wrong_provider_duplicate_and_insufficient_cash_rejected_without_reserve(game):
    e=Engine(copy.deepcopy(game.world));p=property_for(e)
    with pytest.raises(RuleError):request(e,p,provider='business-1')
    first=request(e,p)
    with pytest.raises(RuleError,match='unfinished'):request(e,p)
    assert len(e.world.systems['property_service_jobs'])==1
    e.action('cancel_property_service',dict(job_id=first['id']),'cancel')
    e.post('personal','cash-out','Test distribution',{'asset:cash':-e.world.cash('personal'),'equity:distributions':e.world.cash('personal')})
    with pytest.raises(RuleError):request(e,p)
    e.validate()


def test_security_license_removes_capacity_until_renewal(game):
    bid=purchase(game,'security');e=Engine(copy.deepcopy(game.world));e.world.date='2026-01-19';r=BusinessRules(e);b=r.company(bid)
    for emp in r.staff(bid):
        if r.position(emp.position_id).role=='security_guard':r.person(emp.person_id).licenses['security_guard']='2025-01-01'
    r.operate(b,date.fromisoformat(e.world.date));assert b.last_day['capacity']==0 and b.last_day['output']==0
    emp=next(emp for emp in r.staff(bid) if r.position(emp.position_id).role=='security_guard')
    e.action('renew_license',dict(employment_id=emp.id,license='security_guard'),'renew')
    assert any(p['kind']=='license' and p['person_id']==emp.person_id for p in e.world.systems['plans'])


def test_landscaping_weather_delays_work_and_security_coverage_expires(game):
    e=Engine(copy.deepcopy(game.world));p=property_for(e);service=PropertyServices(e);job=request(e,p,'landscaping',visits=1)
    while date.fromisoformat(e.world.date).weekday()>4 or not service.weather(p.region):next_day(e)
    service.tick();assert job['worked']==0
    while date.fromisoformat(e.world.date).weekday()>4 or service.weather(p.region):next_day(e)
    service.tick();assert job['worked']>0
    patrol=request(e,p,'security',visits=1);service.tick();assert patrol['status']=='complete' and protection(e.world,p)>0
    e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=9)).isoformat();assert protection(e.world,p)==0


def test_delayed_work_surfaces_deadline_and_daily_reentry_does_not_duplicate_delivery(game):
    e=Engine(copy.deepcopy(game.world));p=property_for(e);job=request(e,p,visits=20)
    e.world.date='2026-01-05';service=PropertyServices(e);service.tick();paid=job['expense'];service.tick();assert job['expense']==paid
    job['due']='2026-01-01';next_day(e);service.tick()
    assert job['warned'] and any(r['title']=='Property service deadline missed' for r in e.pause_reasons)


def test_plan_full_cost_and_property_scope_checked_before_delegation(game):
    from test_leadership import setup
    from test_authority import contract
    e,l,b,_,_=setup(game)
    e.action('fund_business',dict(business_id=b.id,amount=10000000),'property-capital')
    p=property_for(e,b.id);e.world.date='2026-01-19'
    contract(e,b,period_limit=1000);before=copy.deepcopy(e.world.accounts)
    assert not l.perform(b,'property-care','property_service',dict(property_id=p.id,visits=20),0,True,'Book cleaning')
    assert before==e.world.accounts and not e.world.systems.get('property_service_jobs')


def test_property_service_pages_and_forecasts_are_read_only(game):
    act(game,'buy',property_id=next(p.id for p in game.world.properties if p.status=='market' and not p.id.startswith('covenant-')))
    before=game.world.to_dict()
    with client_for(game) as client:
        for page in ('property_services','business_market','overview'):
            response=client.get('/?page='+page);assert response.status_code==200
            if page=='property_services':assert 'Book a property service plan' in response.text and 'Cleanliness' in response.text
    assert game.world.to_dict()==before


def test_old_content_migrates_once_and_preserves_existing_people_accounts_and_rng(tmp_path):
    from economic_simulation.persistence import Store
    e=new_game();e.world.content_version=PREVIOUS_CONTENT_VERSION;e.world.systems.update(version=4);e.world.systems.pop('property_services_version')
    before=copy.deepcopy(e.world);path=tmp_path/'old.sqlite3';Store(path,initial=e);after=Store(path).load()
    assert after.accounts==before.accounts and after.employments==before.employments and after.date==before.date
    assert after.systems['streams']==before.systems['streams'] and after.systems['version']==5
    assert len(list(tmp_path.glob('old.before-property-services-*.sqlite3')))==1
    assert Store(path).load().to_dict()==after.to_dict()


def test_daily_step_and_reload_have_identical_service_delivery(game,tmp_path):
    from economic_simulation.persistence import Store
    p=next(p for p in game.world.properties if p.status=='market' and not p.id.startswith('covenant-'))
    act(game,'buy',property_id=p.id);act(game,'property_service',property_id=p.id,kind='cleaning',visits=3,interval=2)
    with game.store.connection() as db,sqlite3.connect(tmp_path/'replay.sqlite3') as dest:db.backup(dest)
    store=Store(tmp_path/'replay.sqlite3');left=copy.deepcopy(game.world);right=store.load()
    for _ in range(10):
        e=Engine(left);e.advance_day();e.validate();left=e.world
        e=Engine(right);e.advance_day();store.commit(e,right.revision);right=store.load()
    left.revision=right.revision;assert json.loads(json.dumps(left.to_dict()))==right.to_dict();store.audit(right)


def test_property_presentation_changes_single_home_offer_after_actual_cleaning(game):
    e=Engine(copy.deepcopy(game.world));p=property_for(e);p.condition=70
    original=p.suggested_rent;job=request(e,p,visits=1)
    e.world.date='2026-01-05';PropertyServices(e).tick()
    assert job['status']=='complete' and presentation(e.world,p)>100
    e.action('rent',dict(property_id=p.id),'find-tenant')
    assert p.rent==original*presentation(e.world,p)//100 and p.rent>original
    saved_rent=p.rent;next_day(e);PropertyServices(e).tick();assert p.rent==saved_rent


def test_manager_property_care_requires_explicit_authority_before_auto_booking(game):
    from test_leadership import setup
    from test_authority import contract
    from economic_simulation.operating_automation import OperatingAutomation
    e,l,b,_,_=setup(game);e.action('fund_business',dict(business_id=b.id,amount=15000000),'fund-property')
    p=property_for(e,b.id);e.world.date='2026-01-19'
    PropertyServices(e).initialize();e.world.systems['property_care'][p.id]['cleanliness']=20
    contract(e,b,period_limit=1000);automation=OperatingAutomation(e)
    automation.action(dict(business_id=b.id,property_operations=True));before=e.world.cash(b.id);automation.tick()
    assert not e.world.systems.get('property_service_jobs') and e.world.cash(b.id)==before
    assert any(r['action']=='property_service' and r['status']=='open' for r in e.world.systems['management_requests'])
    # Expanding the limit does not silently approve an existing exception.
    assert any(r['title']=='Owner approval needed' for r in e.pause_reasons)


def test_equipment_improvement_expands_ceiling_but_cannot_create_worker_hours(game):
    bid=purchase(game,'cleaning');base=copy.deepcopy(game.world);results=[]
    for capacity,staff_minutes in ((100,3000),(110,3000),(110,120)):
        e=Engine(copy.deepcopy(base));b=BusinessRules(e).company(bid);b.capacity_percent=capacity
        result=PropertyServices(e).operate(BusinessRules(e),b,{'cleaner':[staff_minutes]+[0]*23},100,True)
        results.append(result['capacity']);e.validate()
    assert results[1]>results[0] and results[2]<=120
