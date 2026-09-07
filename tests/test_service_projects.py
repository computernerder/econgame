import copy
from datetime import date, timedelta
import pytest
from test_game import game, act, step
from test_business import acquire
from test_leadership import setup
from test_campaign_product import client_for
from economic_simulation.domain import Engine, RuleError
from economic_simulation.service_office import ServiceOffice
from economic_simulation.service_products import ServiceProducts
from economic_simulation.property_requests import PropertyRequests
from economic_simulation.property_operations import PropertyOperations


def request(e,b,product,**args):
    from economic_simulation.service_products import PRODUCTS
    office=ServiceOffice(e)
    office.action('service_request',dict(recipient=b.id,department=PRODUCTS[product][0],product=product,
                 provider='outside',mode='outside',**args),'project-'+str(e.world.systems['next_id']))
    return office,e.world.systems['service_tasks'][-1]


def deliver(e,office,days):
    for _ in range(days):
        office.tick();e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()


def tenant(e):
    p=e.world.properties[0];e.action('buy',dict(property_id=p.id),'buy-property')
    ops=PropertyOperations(e);ops.action('advertise_space',dict(property_id=p.id),'advertise')
    e.world.date=e.world.systems['vacancies'][-1]['due'];ops.tick()
    offer=e.world.systems['tenant_offers'][0]
    ops.action('accept_tenant',dict(property_id=p.id,offer_id=offer['id'],rent=offer['rent']),'tenant')
    facts=ops.ensure(p)
    for value in facts.values():value['condition']=70
    facts['roof']['condition']=25
    return p,ops,e.world.systems['leases'][-1]


def test_role_search_preserves_candidate_uncertainty_and_offer_rules(game):
    e,l,b,_,_=setup(game);count=len(e.world.people)
    office,t=request(e,b,'role_search',role='cashier');deliver(e,office,3)
    assert t['status']=='complete' and len(e.world.people)==count+3
    assert all(l.rules.person(pid).candidate for pid in t['applicants'])
    l.rules.action('create_position',dict(business_id=b.id,role='cashier'),'vacancy')
    with pytest.raises(RuleError,match='declined'):
        l.rules.action('hire',dict(position_id=e.world.positions[-1].id,person_id=t['applicants'][0],amount=1),'bad-offer')
    e.validate()


def test_assessment_records_estimate_without_changing_true_ability(game):
    e,l,b,_,_=setup(game);person=next(p for p in e.world.people if p.candidate);skills=copy.deepcopy(person.skills)
    office,t=request(e,b,'assessment',target_id=person.id,role='manager');deliver(e,office,1)
    assert t['assessment']['low']<t['assessment']['high'] and person.skills==skills
    assert person.observations[-1]['source']=='HR assessment'
    e.validate()


def test_onboarding_requires_paid_participation_and_handles_leave(game):
    e,l,b,emp,_=setup(game);person=l.rules.person(emp.person_id);trust=person.trust
    office,t=request(e,b,'onboarding',target_id=emp.id)
    emp.leave_until='2026-02-01'
    l.rules.work(b,date.fromisoformat(e.world.date));deliver(e,office,2)
    assert t['remaining']==0 and t['status']=='working' and t['participant_done']==0 and person.trust==trust
    emp.leave_until=None
    for _ in range(2):
        l.rules.work(b,date.fromisoformat(e.world.date));office.tick()
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    assert t['status']=='complete' and t['participant_done']==120 and person.trust>trust
    assert t['outside_cost']==480*150
    e.validate()


def test_onboarding_cancel_refunds_only_unused_reserve(game):
    e,l,b,emp,_=setup(game);office,t=request(e,b,'onboarding',target_id=emp.id)
    office.tick();cash=e.world.cash(b.id)
    office.action('cancel_service',dict(task_id=t['id']),'cancel')
    assert e.world.cash(b.id)==cash+240*150 and t['status']=='cancelled'
    assert ServiceProducts(e).participant_minutes(emp,480)==0
    assert e.world.accounts[b.id]['expense:outside_services']==240*150
    assert e.world.accounts[b.id]['asset:prepaid_services']==0
    e.validate()


def test_succession_shortlist_does_not_promote_or_duplicate_employee(game):
    e,l,b,_,_=setup(game);before=copy.deepcopy(e.world.employments)
    office,t=request(e,b,'succession',role='manager');deliver(e,office,4)
    assert t['shortlist'] and e.world.employments==before
    assert all('low' in r and 'eligible' in r for r in t['shortlist'])
    e.validate()


def test_checkout_installation_consumes_work_and_wears_until_supported(game):
    e,l,b,_,_=setup(game);office,t=request(e,b,'pos_deployment')
    deliver(e,office,5);assert b.id not in e.world.systems.get('deployed_systems',{})
    deliver(e,office,1);products=ServiceProducts(e);system=e.world.systems['deployed_systems'][b.id]['pos_deployment']
    e.world.date='2026-02-02';buckets={'cashier':[100]*24};products.operate(b,buckets)
    assert sum(buckets['cashier'])>2400 and system['condition']==99
    system['condition']=0;system['last_used']='';buckets={'cashier':[100]*24};products.operate(b,buckets)
    assert sum(buckets['cashier'])==2400
    office,t=request(e,b,'system_support');deliver(e,office,2)
    assert system['condition']==75
    e.validate()


def test_inventory_integration_uses_observed_demand_without_inventing_stock(game):
    e,l,b,_,_=setup(game);products=ServiceProducts(e);initial=b.inventory_units
    b.history=[dict(demand=10),dict(demand=20)]
    office,t=request(e,b,'inventory_integration');deliver(e,office,6)
    assert products.stock_target(b)==30 and b.inventory_units==initial
    e.world.systems['deployed_systems'][b.id]['inventory_integration']['condition']=0
    assert products.stock_target(b)==b.daily_demand*5


def test_product_validation_rejects_wrong_department_or_employee_scope(game):
    e,l,b,_,other=setup(game,two=True)
    emp=l.rules.staff(other)[0]
    with pytest.raises(RuleError,match='receiving business'):request(e,b,'onboarding',target_id=emp.id)
    with pytest.raises(RuleError,match='belonging'):
        ServiceOffice(e).action('service_request',dict(recipient=b.id,department='hr',product='pos_deployment',mode='outside'),'wrong')


def test_tenant_requests_use_existing_facts_and_actual_completed_repairs(game):
    e,l,b,_,_=setup(game);p,ops,lease=tenant(e);requests=PropertyRequests(e)
    before=copy.deepcopy(ops.ensure(p));requests.tick();t=e.world.systems['property_requests'][0]
    assert before==ops.ensure(p) and t['system']=='roof' and t['observed_condition']==25
    requests.action(dict(property_id=p.id,request_id=t['id'],kind='replacement'),'respond')
    assert t['status']=='working' and ops.ensure(p)['roof']['condition']==25
    for i in range(8):
        ops.tick();requests.tick();e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    assert t['status']=='resolved' and ops.ensure(p)['roof']['condition']>=40
    assert e.world.accounts['personal']['asset:prepaid_works']==0
    e.validate()


def test_overdue_tenant_repair_changes_renewal_terms_and_surfaces_deadline(game):
    e,l,b,_,_=setup(game);p,ops,lease=tenant(e);requests=PropertyRequests(e);requests.tick()
    t=e.world.systems['property_requests'][0];e.world.date=(date.fromisoformat(t['due'])+timedelta(days=1)).isoformat()
    lease['end_date']=(date.fromisoformat(e.world.date)+timedelta(days=30)).isoformat();requests.tick()
    assert t['status']=='overdue' and t['notified']
    with pytest.raises(RuleError,match='declined'):ops.action('renew_property_lease',dict(property_id=p.id,lease_id=lease['id'],rent=lease['rent']),'renew')
    rent=lease['rent']*90//100;ops.action('renew_property_lease',dict(property_id=p.id,lease_id=lease['id'],rent=rent),'concession')
    assert lease['rent']==rent


def test_new_service_ui_and_daily_reload_are_consistent(game,tmp_path):
    from economic_simulation.persistence import Store
    import sqlite3
    bid=acquire(game)
    act(game,'service_request',recipient=bid,department='it',product='pos_deployment',mode='outside',provider='outside')
    original=copy.deepcopy(game.world)
    with game.store.connection() as source,sqlite3.connect(tmp_path/'replay.sqlite3') as dest:source.backup(dest)
    store=Store(tmp_path/'replay.sqlite3');right=store.load();left=copy.deepcopy(original)
    for _ in range(9):
        e=Engine(left);e.advance_day();e.validate();left=e.world
        e=Engine(right);e.advance_day();store.commit(e,right.revision);right=store.load()
    import json
    left.revision=right.revision;assert json.loads(json.dumps(left.to_dict()))==right.to_dict();store.audit(right)
    with client_for(game) as client:
        text=client.get('/?page=home_office&scope='+bid).text
        assert 'Prepare a succession shortlist' in text and 'Cancel unfinished service work' in text
    assert game.world.to_dict()==original.to_dict()


def test_service_migration_preserves_existing_records_and_backs_up(tmp_path):
    from economic_simulation.domain import new_game
    from economic_simulation.persistence import Store
    e=new_game();e.world.systems.update(version=2);e.world.systems.pop('service_projects_version')
    before=copy.deepcopy(e.world);path=tmp_path/'old.sqlite3';Store(path,initial=e)
    after=Store(path).load()
    assert after.date==before.date and after.accounts==before.accounts and after.employments==before.employments
    assert after.systems['version']==5 and len(list(tmp_path.glob('old.before-service-projects-*.sqlite3')))==1
    assert Store(path).load().to_dict()==after.to_dict()


def test_delegation_rejects_project_cost_and_property_outside_scope(game):
    from test_authority import contract
    e,l,b,_,_=setup(game);contract(e,b,period_limit=200000)
    before=copy.deepcopy(e.world.accounts)
    assert not l.perform(b,'deploy','service_request',dict(recipient=b.id,department='it',product='pos_deployment',provider='outside',mode='outside'),0,True,'Install checkout')
    assert e.world.accounts==before and not e.world.systems.get('service_tasks')
    p,ops,lease=tenant(e);PropertyRequests(e).tick();t=e.world.systems['property_requests'][0]
    e.world.date='2026-01-19'
    before=copy.deepcopy(e.world.accounts)
    assert not l.perform(b,'foreign-property','respond_property_request',dict(property_id=p.id,request_id=t['id']),0,True,'Property response')
    assert e.world.accounts==before and not e.world.systems.get('property_work')
    assert any('scope' in r['detail'] for r in e.world.systems['management_requests'])


def test_internal_project_overload_uses_one_employee_time_pool(game):
    from test_specialists import add_specialist
    e,l,b,_,_=setup(game);emp,person=add_specialist(e,b.id,'hr');person.skills['leadership']=80
    office=ServiceOffice(e);office.action('department_configure',dict(provider=b.id,department='hr',staff=emp.id,regions=b.region,industries=b.industry),'configure')
    for n in range(2):office.action('service_request',dict(recipient=b.id,provider=b.id,department='hr',product='role_search',role='cashier',mode='internal'),'search-'+str(n))
    buckets={'hr':[240]+[0]*23};office.deliver(l.rules,b,buckets)
    tasks=e.world.systems['service_tasks'];assert tasks[0]['worked']>0 and tasks[1]['worked']==0
    assert sum(buckets['hr'])==0 and tasks[0]['staff']==[emp.id]
    e.validate()


def test_promotion_cannot_bypass_target_license(game):
    from economic_simulation.workforce import Workforce
    e,l,b,manager,_=setup(game)
    l.rules.action('create_position',dict(business_id=b.id,role='legal'),'licensed-position')
    target=e.world.positions[-1]
    with pytest.raises(RuleError,match='license'):
        Workforce(e).action('promote',dict(employment_id=manager.id,position_id=target.id,amount=600000),'promote')


def test_onboarding_for_departed_employee_finishes_without_false_success(game):
    e,l,b,emp,_=setup(game);office,t=request(e,b,'onboarding',target_id=emp.id)
    emp.status='ended';deliver(e,office,2)
    assert t['status']=='complete' and 'left' in t['outcome'] and t['participant_done']==0


def test_enabled_manager_renews_deployed_system_through_authorized_queue(game):
    from test_authority import contract
    from economic_simulation.operating_automation import OperatingAutomation
    e,l,b,_,_=setup(game);office,t=request(e,b,'pos_deployment');deliver(e,office,6)
    e.world.date='2026-03-02';e.world.systems['deployed_systems'][b.id]['pos_deployment']['condition']=20
    contract(e,b)
    e.world.systems.setdefault('operating_automation',{})[b.id]=dict(service_renewals=True,service_roles=['it'])
    OperatingAutomation(e).tick()
    task=e.world.systems['service_tasks'][-1]
    assert task['product']=='system_support' and task['status']=='queued'
    assert e.world.systems['authority_audit'][-1]['commitment']==72000
    e.validate()


def test_tenant_deadline_stops_skip_despite_large_financial_threshold(game):
    from economic_simulation.skip_controls import should_pause
    e,l,b,_,_=setup(game);p,ops,lease=tenant(e);requests=PropertyRequests(e);requests.tick()
    task=e.world.systems['property_requests'][0]
    e.pause_reasons.clear();e.world.systems['settings']['financial_pause_threshold']=100000000
    e.world.date=(date.fromisoformat(task['due'])+timedelta(days=1)).isoformat();requests.tick()
    assert should_pause(e) and e.pause_reason_text=='Tenant repair deadline missed'
