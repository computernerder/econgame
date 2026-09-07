import copy
import json
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_models import Position,Employment,ROLE_PAY
from economic_simulation.restaurant import Restaurant,settings,active,capacity,expected,SCALES
from economic_simulation.restaurant_staffing import staffing_plan,suggestions,hiring_role
from economic_simulation.authority import cash_forecast


def setup(game):
    bid=acquire(game,1)
    act(game,'restaurant_plan',business_id=bid,days='0,1,2,3,4,5,6',opens=10,closes=22,planning_covers=100,auto_schedule=True)
    return next(b for b in game.world.businesses if b.id==bid)


def team(world,b,counts):
    rules=BusinessRules(Engine(world))
    for emp in world.employments:
        if emp.employer==b.id:emp.status='ended'
    for role,count in counts.items():
        for i in range(count):
            person=rules.make_person(role);ident=f'qa-{role}-{i}'
            world.positions.append(Position(ident,b.id,role,None))
            world.employments.append(Employment(ident,person.id,ident,b.id,ROLE_PAY[role],40,world.date,status='active'))
    b.authority['staffing_target']=sum(counts.values());b.authority['operating_policy']={'hiring':'freeze','training':False}


def buckets(chef=60,server=60,prep=0,dish=0,host=0):
    return {r:[value]*24 for r,value in dict(manager=120,chef=chef,server=server,prep_cook=prep,dishwasher=dish,host=host).items()}


def test_new_plan_persists_without_headquarters_or_mutating_get(game):
    b=setup(game);before=copy.deepcopy(game.world.to_dict())
    plan=staffing_plan(game.world,b)
    assert len(plan['projections'])==7
    assert {'prep_cook','dishwasher','host'}<={r['role'] for r in plan['rows']}
    with client_for(game) as client:
        html=client.get('/',params={'page':'business','business_id':b.id,'scope':b.id}).text
        assert 'Weekly restaurant roster' in html and 'Review balanced shifts now' in html
        assert 'Monthly employer cost' in html
        assert 'name="days" multiple' in html and 'name="staffing_target"' in html
    assert before==game.world.to_dict()
    assert game.store.load().to_dict()==game.world.to_dict()


def test_legacy_restaurant_keeps_old_model_until_plan_is_saved(game):
    bid=acquire(game,1);b=next(b for b in game.world.businesses if b.id==bid)
    assert not active(game.world,b)
    with client_for(game) as client:
        html=client.get('/',params={'page':'business','business_id':bid,'scope':bid}).text
        assert 'Enable the restaurant plan' in html
    assert not active(game.world,b)


def test_support_roles_consume_real_minutes_and_free_frontline_staff(game):
    b=setup(game)
    bare=capacity(game.world,b,buckets(),300,stock=1000)
    full=capacity(game.world,b,buckets(prep=60,dish=60,host=60),300,stock=1000)
    no_chef=capacity(game.world,b,buckets(chef=0,prep=600,dish=600,host=600),300,stock=1000)
    assert full['output']>bare['output']>0 and no_chef['output']==0
    assert sum(h['served'] for h in full['hourly'])==full['output']
    assert full['output']<=sum(h['demand'] for h in full['hourly'])==300


def test_weekends_trade_selected_closed_days_do_not_and_stock_is_finite(game):
    b=setup(game);rules=BusinessRules(Engine(game.world));plan=game.world.systems['restaurants'][b.id]
    plan['days']=[5,6];game.world.date='2026-02-07'
    for emp in rules.staff(b.id):emp.days=[0,1,2,5,6];emp.shift_start=12
    b.auto_restock=False;b.inventory_units=4
    rules.operate(b,date.fromisoformat(game.world.date));assert 0<b.last_day['output']<=4
    assert b.last_day['demand']>0 and b.last_day['hourly']
    game.world.date='2026-02-09';rules.operate(b,date.fromisoformat(game.world.date))
    assert b.last_day['output']==b.last_day['demand']==0
    assert b.last_day['expenses']>0


def test_large_team_scales_and_rota_improves_real_service_coverage(game):
    b=setup(game);plan=game.world.systems['restaurants'][b.id];plan.update(level=4,audience=950,planning_covers=950)
    team(game.world,b,dict(manager=5,chef=12,prep_cook=5,server=10,dishwasher=5,host=3))
    before=staffing_plan(game.world,b);original={e.id:(e.salary,e.weekly_hours) for e in game.world.employments}
    for change in suggestions(game.world,b):Restaurant(Engine(game.world)).action('restaurant_rota',change,'qa-rota')
    after=staffing_plan(game.world,b)
    assert sum(d['capacity'] for d in after['projections'])>sum(d['capacity'] for d in before['projections'])*1.3
    assert sum(d['capacity'] for d in after['projections'])>3000
    assert 30<=sum(r['target_hours'] for r in after['rows'])/40<=50
    assert {e.id:(e.salary,e.weekly_hours) for e in game.world.employments}==original
    assert len([e for e in game.world.employments if e.employer==b.id and e.status=='active'])==40
    assert len({e.name for e in game.world.people})==len(game.world.people)


def test_pinned_rota_persists_and_rejects_unworkable_days(game):
    b=setup(game);emp=next(e for e in game.world.employments if e.employer==b.id and e.status=='active')
    act(game,'restaurant_rota',employment_id=emp.id,days='2,3,4,5,6',shift_start=12,manager_schedule=False)
    b=next(x for x in game.world.businesses if x.id==b.id)
    assert emp.id not in {r['employment_id'] for r in suggestions(game.world,b)}
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError):act(game,'restaurant_rota',employment_id=emp.id,days='6',shift_start=12)
    assert before==game.world.to_dict()


def test_leave_lowers_forecast_and_scheduling_does_not_remove_leave(game):
    b=setup(game);act(game,'restaurant_schedule',business_id=b.id)
    b=next(x for x in game.world.businesses if x.id==b.id)
    before=staffing_plan(game.world,b)
    chef=next(e for e in game.world.employments if e.employer==b.id and next(p.role for p in game.world.positions if p.id==e.position_id)=='chef')
    chef.leave_until=(date.fromisoformat(game.world.date)+timedelta(days=8)).isoformat()
    after=staffing_plan(game.world,b)
    assert sum(p['capacity'] for p in after['projections'])<sum(p['capacity'] for p in before['projections'])
    assert chef.leave_until


def test_expansion_is_prepaid_delayed_and_does_not_create_demand(game):
    b=setup(game);engine=Engine(game.world)
    engine.post(b.id,'qa-capital','Test capital',{'asset:cash':100000000,'equity:capital':-100000000})
    cash=game.world.cash(b.id);audience=settings(game.world,b).get('audience',b.daily_demand);oldcost=b.monthly_overhead
    Restaurant(engine).action('restaurant_expand',{'business_id':b.id},'qa-expand')
    assert game.world.cash(b.id)==cash-SCALES[2]['cost']
    assert settings(game.world,b)['level']==1
    assert settings(game.world,b).get('audience',b.daily_demand)==audience
    assert game.world.accounts[b.id]['asset:construction_in_progress']==SCALES[2]['cost']
    due=settings(game.world,b)['expansion']['due'];game.world.date=due
    Restaurant(engine).begin_day(b,date.fromisoformat(due))
    assert settings(game.world,b)['level']==2 and game.world.accounts[b.id]['asset:construction_in_progress']==0
    assert b.monthly_overhead==oldcost+SCALES[2]['overhead']
    assert all(sum(p['lines'].values())==0 for p in engine.postings)
    with pytest.raises(RuleError):
        game.world.accounts[b.id]['asset:cash']=0
        Restaurant(engine).action('restaurant_expand',{'business_id':b.id},'qa-no-cash')


def test_ads_and_future_overhead_count_in_cash_forecast(game):
    b=setup(game);before=cash_forecast(game.world,b.id,30)['available']
    act(game,'restaurant_plan',business_id=b.id,marketing_monthly=300000)
    assert cash_forecast(game.world,b.id,30)['available']<before-200000
    b=next(x for x in game.world.businesses if x.id==b.id);engine=Engine(game.world)
    Restaurant(engine).begin_day(b,date.fromisoformat(game.world.date))
    assert any('expense:marketing' in p['lines'] for p in engine.postings)


def test_restaurant_hiring_targets_largest_role_shortage(game):
    b=setup(game);game.world.systems['restaurants'][b.id]['planning_covers']=900
    assert hiring_role(game.world,b)=='chef'
    game.world.systems['restaurants'][b.id]['planning_covers']=20
    assert hiring_role(game.world,b) in ('manager','prep_cook','dishwasher','host','server')


def test_daily_steps_save_load_and_audit_with_mealtime_operations(game):
    b=setup(game);act(game,'restaurant_schedule',business_id=b.id)
    act(game,'management_policy',target=b.id,hiring='freeze',training=False)
    original=copy.deepcopy(game.world)
    step(game,7)
    other=Engine(original)
    for _ in range(7):other.advance_day()
    # Revision and journal IDs belong to commits; all simulation records must agree.
    assert next(x for x in other.world.businesses if x.id==b.id).history==next(x for x in game.world.businesses if x.id==b.id).history
    assert other.world.accounts==game.world.accounts
    assert json.dumps(game.store.load().to_dict(),sort_keys=True)==json.dumps(game.world.to_dict(),sort_keys=True)
    game.store.audit(game.world)


def test_manager_schedules_are_logged_and_explicit_staffing_block_goes_to_inbox(game):
    from economic_simulation.operating_automation import OperatingAutomation
    from economic_simulation.authority import Authority
    b=setup(game);engine=Engine(game.world);game.world.date='2026-02-02'
    OperatingAutomation(engine).tick()
    assert any(r['action']=='restaurant_rota' for r in game.world.systems.get('authority_audit',[]))
    plan=game.world.systems['restaurants'][b.id];plan.update(opens=6,closes=18,rota_requested=True)
    Authority(engine).set_contract(dict(target='manager:'+b.id,staffing='prohibit',headcount_limit=100,horizon=1))
    before={e.id:(e.days[:],e.shift_start) for e in game.world.employments}
    OperatingAutomation(engine).tick()
    assert before=={e.id:(e.days,e.shift_start) for e in game.world.employments}
    assert any(r['status']=='open' and r['action']=='restaurant_rota' for r in game.world.systems['management_requests'])
    game._run(7)
    assert game.progress['completed']==0 and 'approval' in game.progress['message'].lower()


def test_cross_employment_overlap_and_shared_reserved_schedule_are_protected(game):
    b=setup(game);rules=BusinessRules(Engine(game.world));emp=rules.staff(b.id)[0]
    from economic_simulation.restaurant_staffing import suggestions
    second=copy.deepcopy(emp);second.id='qa-second-job';second.shift_start=18;second.weekly_hours=10
    game.world.employments.append(second)
    with pytest.raises(RuleError):Restaurant(Engine(game.world)).action('restaurant_rota',dict(employment_id=emp.id,shift_start=16),'qa-conflict')
    game.world.employments.remove(second)
    # The scheduler never moves an employee with a standing shared assignment.
    game.world.systems['assignments'].append(dict(active=True,employment_id=emp.id))
    assert emp.id not in {r['employment_id'] for r in suggestions(game.world,b)}


def test_expansion_forecast_reserves_future_utilities_without_double_counting_paid_fitout(game):
    b=setup(game);e=Engine(game.world)
    e.post(b.id,'qa-fund','Test capital',{'asset:cash':100000000,'equity:capital':-100000000})
    baseline=cash_forecast(game.world,b.id,30)
    Restaurant(e).action('restaurant_expand',dict(business_id=b.id),'qa-expansion')
    after=cash_forecast(game.world,b.id,30)
    extra=baseline['available']-after['available']-SCALES[2]['cost']
    assert 0<extra<SCALES[2]['overhead']*2


def test_completed_fitout_reconciles_in_saved_game(game):
    b=setup(game)
    act(game,'fund_business',business_id=b.id,amount=10000000)
    act(game,'restaurant_expand',business_id=b.id)
    step(game,14)
    b=next(x for x in game.world.businesses if x.id==b.id)
    assert settings(game.world,b)['level']==2
    assert game.world.accounts[b.id]['asset:construction_in_progress']==0
    game.store.audit(game.world)


def test_overstaffing_low_volume_loses_money_and_meals_reconcile(game):
    b=setup(game);team(game.world,b,dict(manager=5,chef=12,prep_cook=5,server=10,dishwasher=5,host=3))
    game.world.date='2026-02-02';b.auto_restock=False
    e=Engine(game.world);rules=BusinessRules(e)
    rules.operate(b,date.fromisoformat(game.world.date))
    assert b.last_day['profit']<0
    assert b.last_day['output']==sum(h['served'] for h in b.last_day['hourly'])
    assert b.last_day['streams']['meal_sales']==b.last_day['output']*b.unit_price*b.price_percent//100
    assert all(sum(p['lines'].values())==0 for p in e.postings)


def test_manager_hires_for_workload_and_counts_joining_employees_at_limit(game):
    from economic_simulation.leadership import Leadership
    b=setup(game)
    act(game,'fund_business',business_id=b.id,amount=10000000)
    act(game,'restaurant_plan',business_id=b.id,planning_covers=900)
    act(game,'management_policy',target=b.id,hiring='grow',staffing_target=5,training=False)
    b=next(x for x in game.world.businesses if x.id==b.id);game.world.date='2026-01-05'
    e=Engine(game.world);leader=Leadership(e)
    leader.start_day()
    incoming=[emp for emp in game.world.employments if emp.employer==b.id and emp.status=='joining']
    assert len(incoming)==1 and leader.rules.position(incoming[0].position_id).role=='chef'
    assert any(row['action']=='hire_for_role' for row in game.world.systems['authority_audit'])
    leader.start_day()
    assert len([emp for emp in game.world.employments if emp.employer==b.id and emp.status in ('active','joining')])==5
    e.validate()
