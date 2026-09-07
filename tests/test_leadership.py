import copy
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.leadership import Leadership,review
from economic_simulation.business_rules import BusinessRules
from economic_simulation.campaign import Campaign
from economic_simulation.skip_controls import should_pause


def setup(game,two=False):
    bid=acquire(game)
    second=acquire(game,1) if two else None
    engine=Engine(copy.deepcopy(game.world));engine.world.date='2026-01-12'
    leader=Leadership(engine);b=leader.rules.company(bid)
    manager=next(e for e in leader.rules.staff(bid) if leader.rules.position(e.position_id).role=='manager')
    return engine,leader,b,manager,second


def test_annual_raise_changes_only_future_pay_and_rejects_repeat(game):
    engine,leader,b,manager,_=setup(game)
    due=review(engine.world,manager)['due'];engine.world.date=due
    expected=review(engine.world,manager);before=copy.deepcopy(engine.world.accounts)
    leader.action('annual_raise',{'employment_id':manager.id},'annual-first')
    assert manager.salary==expected['salary'] and manager.last_pay_review==due
    assert engine.world.accounts==before and not review(engine.world,manager)['overdue']
    with pytest.raises(RuleError):leader.action('annual_raise',{'employment_id':manager.id},'annual-second')
    engine.validate()


def test_hourly_raise_updates_rate_and_monthly_base(game):
    engine,leader,b,manager,_=setup(game)
    manager.compensation={'pay_basis':'hourly','hourly_rate':2000}
    manager.salary=2000*manager.weekly_hours*52//12
    engine.world.date=review(engine.world,manager)['due']
    leader.action('annual_raise',{'employment_id':manager.id},'hourly-raise')
    assert manager.compensation['hourly_rate']==2060
    assert manager.salary==2060*manager.weekly_hours*52//12


def test_manager_approves_staff_raises_but_not_own_and_reviews_deduplicate(game):
    engine,leader,b,manager,_=setup(game)
    engine.world.date='2027-01-11'
    b.authority=dict(enabled=True,salary_limit=900000,auto_raises=True,staffing_target=3,purchasing_limit=0)
    before={e.id:e.salary for e in leader.rules.staff(b.id)}
    leader.start_day()
    assert manager.salary==before[manager.id]
    assert all(e.salary>before[e.id] for e in leader.rules.staff(b.id) if e.id!=manager.id)
    assert leader.morale_penalty(manager)>0
    requests=[r for r in engine.world.systems['management_requests'] if r['key']=='raise:'+manager.id]
    leader.start_day()
    assert len([r for r in engine.world.systems['management_requests'] if r['key']=='raise:'+manager.id])==1
    leader.action('management_approve',{'request_id':requests[0]['id']},'owner-raise')
    assert leader.morale_penalty(manager)==0
    engine.validate()


def test_director_is_one_employee_with_shared_authority_and_reserved_time(game):
    engine,leader,b,manager,second=setup(game,True)
    count=len(engine.world.employments);salary=manager.salary
    for bid in (b.id,second):leader.action('director_assign',dict(employment_id=manager.id,business_id=bid,limit=100000),'director-'+bid)
    record,_=leader.director(b.id)
    assert leader.director(second)[0] is record
    assert manager.employer==b.id and manager.salary==salary*115//100*105//100 and len(engine.world.employments)==count
    assert leader.reserved_minutes(manager)==120
    assert leader.stock_limit(b,100000//b.unit_cost)==100000//b.unit_cost
    other=leader.rules.company(second)
    # Daily management now defaults on; absence makes this a director-budget test.
    for employee in leader.rules.staff(second):
        if leader.rules.position(employee.position_id).role=='manager':employee.leave_until=engine.world.date
    assert leader.stock_limit(other,10)==0
    assert record['spent']<=record['limit']
    before=copy.deepcopy(engine.world.to_dict());leader.view(b)
    assert before==engine.world.to_dict()
    engine.validate()


@pytest.mark.parametrize('limit,expected',[(29999,False),(30000,True),(30001,True)])
def test_director_threshold_exact_boundary(game,limit,expected):
    engine,leader,b,manager,_=setup(game)
    leader.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=limit),'director-boundary')
    done=leader.perform(b,'stock-test','restock',dict(business_id=b.id,units=30000//b.unit_cost),30000,False,'Test stock commitment')
    assert done==expected
    assert leader.director(b.id)[0]['spent']==(30000 if expected else 0)


def test_director_annual_salary_commitment_escalates_without_hiring(game):
    engine,leader,b,manager,_=setup(game)
    leader.rules.action('create_position',dict(business_id=b.id,role='cashier'),'vacancy')
    leader.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=100000),'director-limited')
    count=len(engine.world.employments);leader.start_day()
    assert len(engine.world.employments)==count
    request=next(r for r in engine.world.systems['management_requests'] if r['action']=='hire')
    assert request['cost']==260000*12+30000
    assert request['status']=='open'


def test_absent_or_departed_director_cannot_spend(game):
    engine,leader,b,manager,_=setup(game)
    leader.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=100000),'director-absence')
    manager.leave_until=engine.world.date
    assert leader.director(b.id)[1] is None and leader.stock_limit(b,1)==0
    manager.leave_until=None;manager.status='resigned'
    assert leader.director(b.id)[1] is None
    with pytest.raises(RuleError):leader.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=100000),'director-resigned')


def test_routine_decision_handled_without_suppressing_unrelated_alert(game):
    engine,leader,b,manager,_=setup(game)
    leader.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=100000),'director-decision')
    decision=Campaign(engine).decision('test-repair','Small equipment repair','Repair needed',b.id,{'repair':'Repair equipment'},cost=25000)
    engine.event('Safety inspection','Owner attention',True)
    assert leader.resolve_decisions()
    assert decision['status']=='resolved'
    assert should_pause(engine,True) and engine.pause_reason_text=='Safety inspection'
    engine.validate()


def test_failed_delegated_action_is_atomic_and_logged(game):
    engine,leader,b,manager,_=setup(game)
    leader.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=100000000),'director-failure')
    accounts=copy.deepcopy(engine.world.accounts);stock=b.inventory_units
    assert not leader.perform(b,'too-much','restock',dict(business_id=b.id,units=10000000),100,True,'Impossible purchase')
    assert engine.world.accounts==accounts and b.inventory_units==stock
    assert leader.director(b.id)[0]['spent']==0


def test_business_ui_and_director_appointment_persist(game):
    bid=acquire(game);manager=next(e for e in game.world.employments if e.employer==bid and e.status=='active')
    with client_for(game) as c:
        response=c.post('/api/command',headers={'Origin':'http://testserver','X-Game-Token':'test-token'},json=dict(action='director_assign',args=dict(employment_id=manager.id,business_id=bid,limit_dollars='1000'),revision=game.world.revision,command_id='director-ui-command'))
        assert response.status_code==200
        page=c.get('/',params=dict(page='business',business_id=bid))
        assert page.status_code==200 and 'Leadership and annual raises' in page.text and '$1,000' in page.text
        page=c.get('/',params=dict(page='organization',chart='employees',business_id=bid))
        assert page.status_code==200 and 'Director:' in page.text
    restored=game.store.load()
    assert restored.systems['directors'][0]['limit']==100000
    game.store.audit(game.world)
