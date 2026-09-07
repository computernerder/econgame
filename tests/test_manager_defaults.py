import copy
import pytest
from datetime import date,timedelta
from test_game import game,act,step
from test_leadership import setup
from test_business import acquire
from test_authority import contract
from test_manager_routines import invoice,owned_property
from test_specialists import add_specialist
from test_employee_management import request
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.leadership import Leadership
from economic_simulation.authority import Authority,cash_forecast
from economic_simulation.operating_automation import OperatingAutomation
from economic_simulation.routine_management import RoutineManagement
from economic_simulation.time_off import TimeOff,blockers,review_reason
from economic_simulation.decision_inbox import items
from economic_simulation.manager_defaults import limits


def test_manager_starts_daily_work_without_headquarters_or_policy_setup(game):
    e,l,b,manager,_=setup(game)
    assert 'enabled' not in b.authority
    assert l.actor(b)==(None,manager)
    r=invoice(e,b)
    before=e.world.cash(b.id)
    RoutineManagement(e).tick()
    assert r['recovery']['method']=='reminder' and e.world.cash(b.id)==before
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    assert 'authority_contracts' not in e.world.systems
    e.validate()


def test_default_pricing_scheduling_and_repairs_execute_real_actions(game):
    from economic_simulation.property_operations import PropertyOperations,systems_for
    e,l,b,manager,_=setup(game)
    emp=next(x for x in l.rules.staff(b.id) if x.id!=manager.id);emp.shift_start=10
    b.last_day.update(output=100,capacity=100,demand=160)
    prop=owned_property(e,b);prop.region=b.region
    e.world.systems.setdefault('property_systems',{})[prop.id]=copy.deepcopy(systems_for(e.world,prop))
    for system in e.world.systems['property_systems'][prop.id].values():system['condition']=80
    e.world.systems['property_systems'][prop.id]['interior']['condition']=20
    # Other routine care is separately controlled; test the physical repair.
    b.authority['routine_management']={'property_care':False}
    before=e.world.cash(b.id);OperatingAutomation(e).tick()
    assert b.price_percent==102 and emp.shift_start==8
    jobs=e.world.systems['property_work'];assert len(jobs)==1
    assert jobs[0]['system']=='interior' and jobs[0]['status']=='working'
    assert e.world.cash(b.id)<before
    assert {r['action'] for r in e.world.systems['authority_audit'] if r['actor']==manager.id}>={'business_policy','employment_terms','property_work'}
    e.validate()


def test_limit_question_is_attributed_deduplicated_and_stops_skip(game):
    e,l,b,manager,_=setup(game)
    b.authority['purchasing_limit']=0
    r=invoice(e,b);r['recovery_attempts']=['reminder','plan']
    RoutineManagement(e).tick();RoutineManagement(e).tick()
    questions=[x for x in items(e.world) if x['kind']=='management']
    assert len(questions)==1 and l.rules.person(manager.person_id).name in questions[0]['detail']
    assert questions[0]['source']['action']=='recover_invoice'
    assert not any(x['kind']=='invoice' and x['targets'].get('invoice_id')==r['id'] for x in items(e.world))
    assert not r.get('recovery')
    game.store.commit(e,game.world.revision);game.world=e.world
    act(game,'advance',period='week');game.worker.join(timeout=10)
    assert game.progress['completed']==0
    with client_for(game) as client:
        html=client.get('/?page=inbox').text
        assert 'asks:' in html and 'Review customer collections' in html and 'Change collection limits' in html
        assert '#routine-policy-'+b.id in html


def test_default_grant_rejects_other_company_debt_and_unfunded_spending(game):
    e,l,b,manager,second=setup(game,True)
    a=Authority(e)
    assert 'scope' in a.check(b,None,'restock',{'business_id':second},100)
    assert 'approval' in a.check(b,None,'borrow',{'entity':b.id},100)
    before=e.world.cash(b.id)
    e.post(b.id,'test-due','Dated test obligation',{'expense:test':before,'liability:payable':-before})
    accounts=copy.deepcopy(e.world.accounts)
    assert not l.perform(b,'cash-test','restock',dict(business_id=b.id,units=1),b.unit_cost,True,'Stock needed')
    assert 'Known obligations' in e.world.systems['management_requests'][-1]['detail']
    assert e.world.accounts==accounts


def test_default_grant_counts_prior_monthly_commitments_when_settings_change(game):
    from economic_simulation.manager_defaults import contract as default_contract
    e,l,b,manager,_=setup(game)
    a=Authority(e);cap=default_contract(e.world,b)['period_limit']
    used=a.spent('manager:'+b.id)
    a.record(b,None,manager,'hire',cap-used,30000,'Existing annual hiring commitment')
    assert 'Cumulative' in a.check(b,None,'restock',dict(business_id=b.id),1)
    b.authority['enabled']=True
    assert 'Cumulative' in a.check(b,None,'restock',dict(business_id=b.id),1)


def test_manager_fills_existing_vacancy_without_new_layer(game):
    e,l,b,manager,_=setup(game)
    l.rules.action('create_position',dict(business_id=b.id,role='cashier'),'vacancy')
    count=len(e.world.employments)
    l.start_day()
    assert len(e.world.employments)==count+1
    entry=e.world.systems['authority_audit'][-1]
    assert entry['actor']==manager.id and entry['action']=='hire' and entry['commitment']>30000
    assert e.world.employments[-1].status=='joining'
    e.validate()


def test_safe_leave_goes_to_manager_and_coverage_exception_goes_to_inbox(game):
    e,l,b,manager,_=setup(game)
    peer,_=add_specialist(e,b.id,'cashier')
    cashier=next(x for x in l.rules.staff(b.id) if x.id!=peer.id and l.rules.position(x.position_id).role=='cashier')
    r=request(e,cashier,start='2026-01-14',end='2026-01-14')
    assert review_reason(e.world,r)[0]=='' and not blockers(e.world)
    TimeOff(e).tick()
    assert r['status']=='approved' and r['reviewer']==l.rules.person(manager.person_id).name
    own=request(e,manager,start='2026-01-15',end='2026-01-15')
    assert own in blockers(e.world)
    row=next(i for i in items(e.world) if i['kind']=='time_off')
    assert 'Manager review:' in row['detail'] and 'coverage' in row['detail']


def test_pending_routine_leave_does_not_preempt_long_skip_before_manager_review(game):
    e,l,b,manager,_=setup(game)
    peer,_=add_specialist(e,b.id,'cashier')
    cashier=next(x for x in l.rules.staff(b.id) if x.id!=peer.id and l.rules.position(x.position_id).role=='cashier')
    r=request(e,cashier,start='2026-01-15',end='2026-01-15')
    game.store.commit(e,game.world.revision);game.world=e.world
    act(game,'advance',period='week');game.worker.join(timeout=10)
    saved=next(x for x in game.world.systems['time_off_requests'] if x['id']==r['id'])
    assert game.progress['completed']>0 and saved['status'] in ('approved','completed')
    game.store.audit(game.world)


def test_explicit_opt_out_and_budgets_survive_enable_and_views(game):
    from economic_simulation.workforce import Workforce
    e,l,b,manager,_=setup(game)
    b.authority.update(enabled=False,purchasing_limit=70000,salary_limit=480000,training_budget=12000,auto_raises=False,staffing_target=6)
    e.world.systems['operating_automation']={b.id:dict(pricing=False,scheduling=False,property_operations=False)}
    r=invoice(e,b);RoutineManagement(e).tick();assert not r.get('recovery')
    Workforce(e).action('delegation',dict(business_id=b.id,enabled=True),'enable')
    assert b.authority['purchasing_limit']==70000 and b.authority['salary_limit']==480000 and b.authority['training_budget']==12000
    assert not b.authority['auto_raises'] and b.authority['staffing_target']==6
    price=b.price_percent;b.last_day.update(output=100,capacity=100,demand=160)
    OperatingAutomation(e).tick();assert b.price_percent==price and r['recovery']['method']=='reminder'
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        assert 'Daily management is enabled' in client.get('/?page=business&business_id='+b.id).text
        assert 'Default manager authority is active' in client.get('/?page=management').text
    assert game.world.to_dict()==before


def test_default_manager_actions_replay_save_and_reconcile(game):
    e,l,b,manager,_=setup(game);invoice(e,b)
    game.store.commit(e,game.world.revision);game.world=e.world
    batched=Engine(copy.deepcopy(game.store.load()))
    for _ in range(8):batched.advance_day()
    step(game,4);game.world=game.store.load();step(game,4)
    batched.world.revision=game.world.revision
    assert batched.world.to_dict()==game.world.to_dict()
    assert any(x.get('actor')==manager.id for x in game.world.systems['authority_audit'])
    game.store.audit(game.world)


@pytest.mark.parametrize('limit',[0,250000])
def test_new_tenant_request_gets_same_day_manager_review_before_pause(game,limit):
    from economic_simulation.property_requests import PropertyRequests
    from economic_simulation.property_operations import PropertyOperations
    e,l,b,manager,_=setup(game);p=owned_property(e,b)
    ops=PropertyOperations(e);ops.action('advertise_space',dict(property_id=p.id),'advertise')
    e.world.date=e.world.systems['vacancies'][-1]['due'];ops.tick()
    offer=next(o for o in e.world.systems['tenant_offers'] if o['property_id']==p.id)
    ops.action('accept_tenant',dict(property_id=p.id,offer_id=offer['id'],rent=offer['rent']),'tenant')
    while date.fromisoformat(e.world.date).weekday()>4:
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    for fact in ops.ensure(p).values():fact['condition']=80
    ops.ensure(p)['interior']['condition']=10
    b.authority['purchasing_limit']=limit
    e.pause_reasons.clear();PropertyRequests(e).tick()
    ticket=e.world.systems['property_requests'][-1]
    assert ticket['severity']=='urgent'
    assert any(r.get('request_id')==ticket['id'] for r in e.pause_reasons)
    e.event('Unrelated safety issue','Separate review still required',True)
    cash=e.world.cash(b.id);OperatingAutomation(e).review_new_requests()
    assert any(r['title']=='Unrelated safety issue' for r in e.pause_reasons)
    if limit:
        assert ticket['status']=='working' and e.world.cash(b.id)<cash
        assert not any(r.get('request_id')==ticket['id'] for r in e.pause_reasons)
        assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    else:
        assert ticket['status']=='open' and e.world.cash(b.id)==cash
        rows=items(e.world)
        assert any(r['kind']=='management' and r['source']['args'].get('request_id')==ticket['id'] for r in rows)
        assert not any(r['kind']=='repair' and r['targets'].get('request_id')==ticket['id'] for r in rows)
    e.validate()


def test_default_manager_resolves_small_operating_decision_and_logs_actual_work(game):
    from economic_simulation.campaign import Campaign
    e,l,b,manager,_=setup(game)
    decision=Campaign(e).decision('test-repair','Small equipment repair','Repair needed',b.id,{'repair':'Repair equipment'},cost=25000)
    before=e.world.cash(b.id)
    assert l.resolve_decisions() and decision['status']=='resolved'
    assert e.world.cash(b.id)==before-25000
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    e.validate()


def test_tomorrows_safe_leave_is_approved_before_attendance_and_entitlement_use(game):
    from economic_simulation.time_off import absent
    e,l,b,manager,_=setup(game);peer,_=add_specialist(e,b.id,'cashier')
    cashier=next(x for x in l.rules.staff(b.id) if x.id!=peer.id and l.rules.position(x.position_id).role=='cashier')
    r=request(e,cashier,start='2026-01-13',end='2026-01-13')
    before=cashier.leave_balance
    assert not blockers(e.world)
    e.advance_day()
    assert r['status']=='approved' and r['resolution']=='2026-01-12'
    assert r['used_dates']==['2026-01-13'] and cashier.leave_balance==before-1
    assert absent(e.world,cashier) and r['reviewer']==l.rules.person(manager.person_id).name
    e.validate()
