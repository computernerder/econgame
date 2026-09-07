import copy
import json
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_new_industries import purchase
from test_parallel_projects import fixture_engine
from test_authority import contract
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.business_rules import BusinessRules
from economic_simulation.revenue_kits import RevenueKits,CATALOG,state,capacity,tag,commitment
from economic_simulation.project_portfolio import jobs,remaining
from economic_simulation.engineering import accept,next_offer
from economic_simulation.authority import cash_forecast,Authority
from economic_simulation.application import Game


def prepared(game,industry='engineering'):
    if industry in ('engineering','factory'):e,b=fixture_engine(game,industry)
    else:
        bid=purchase(game,industry);e=Engine(copy.deepcopy(game.world));b=next(b for b in e.world.businesses if b.id==bid)
        e.world.date='2026-01-12'
    e.action('fund_business',dict(business_id=b.id,amount=50000000),'test-kit-funding')
    b.auto_restock=False;b.auto_projects=False
    return e,b


def change(e,b,key,**args):
    return e.action('revenue_policy',dict(dict(business_id=b.id,kit=key,enabled=True,weight=50,price_percent=100),**args),'policy-'+key+str(len(e.events)))


def buy(e,b,key):return e.action('buy_revenue_kit',dict(business_id=b.id,kit=key),'kit-'+key)


def operate(e,b):
    BusinessRules(e).operate(b,date.fromisoformat(e.world.date));e.validate()


def test_kit_purchase_is_capitalized_setup_gated_and_preview_read_only(game):
    e,b=prepared(game)
    initial=copy.deepcopy(e.world.to_dict());cash=e.world.cash(b.id);equipment=b.equipment
    preview=Engine(copy.deepcopy(e.world));buy(preview,next(x for x in preview.world.businesses if x.id==b.id),'embedded_design')
    assert e.world.to_dict()==initial
    buy(e,b,'embedded_design');q=CATALOG[b.industry]['embedded_design']
    assert e.world.cash(b.id)==cash-q['cost'] and b.equipment==equipment+q['cost']
    assert e.world.accounts[b.id]['asset:equipment']==b.equipment
    upkeep=next(row for row in cash_forecast(e.world,b.id,30)['rows'] if row['detail']=='Installed revenue-kit upkeep and tools')
    assert upkeep['amount']==q['monthly']
    with pytest.raises(RuleError,match='already'):buy(e,b,'embedded_design')
    with pytest.raises(RuleError,match='being set up'):accept(BusinessRules(e),b,kit_key='embedded_design')
    e.validate()


def test_purchase_rejects_insufficient_uncommitted_cash(game):
    e,b=prepared(game);account=e.world.accounts[b.id];account['asset:cash']=1200000
    before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError,match='known obligations'):buy(e,b,'embedded_design')
    assert e.world.to_dict()==before


def test_unpurchased_specialty_is_not_available(game):
    e,b=prepared(game);change(e,b,'pcb_design')
    with pytest.raises(RuleError,match='Purchase'):change(e,b,'drawing_review')
    with pytest.raises(RuleError,match='not installed'):accept(BusinessRules(e),b,kit_key='drawing_review')


def test_gas_groceries_use_inventory_and_share_existing_staff(game):
    e,b=prepared(game,'gas_station');baseline=Engine(copy.deepcopy(e.world));base_b=next(x for x in baseline.world.businesses if x.id==b.id)
    operate(baseline,base_b)
    buy(e,b,'convenience_grocery');e.world.date='2026-01-19'
    e.action('restock_stream',dict(business_id=b.id,kit='convenience_grocery',units=100),'stock-test')
    operate(e,b);row=state(e.world,b)['last']['convenience_grocery']
    assert 0<row['output']<=row['capacity']
    assert row['stock']==100-row['output']
    assert e.world.accounts[b.id]['income:convenience_grocery']==-row['revenue']
    assert b.last_day['capacity']<base_b.last_day['capacity']
    assert e.world.accounts[b.id]['asset:stream_inventory:convenience_grocery']==row['stock']*750


def test_disabled_sales_stop_revenue_but_inventory_spoils(game):
    e,b=prepared(game,'gas_station');buy(e,b,'convenience_grocery')
    e.action('restock_stream',dict(business_id=b.id,kit='convenience_grocery',units=10),'stock-test')
    change(e,b,'convenience_grocery',enabled=False)
    e.world.date='2026-01-20';operate(e,b)
    row=state(e.world,b)['last']['convenience_grocery']
    assert row['output']==0 and row['spoiled']==10 and row['stock']==0
    assert e.world.accounts[b.id]['expense:spoilage:convenience_grocery']==7500


def test_license_and_absence_gate_drawing_stamps(game):
    e,b=prepared(game);buy(e,b,'drawing_review');e.world.date='2026-01-19'
    r=BusinessRules(e);bucket,management=r.work(b,date.fromisoformat(e.world.date))
    engineers=[x for x in r.staff(b.id) if r.position(x.position_id).role=='engineer']
    for emp in engineers:r.person(emp.person_id).licenses.pop('professional_engineer',None)
    assert capacity(r,b,bucket,management)['drawing_review']==0
    for emp in engineers:r.person(emp.person_id).licenses['professional_engineer']='2027-01-01'
    assert capacity(r,b,bucket,management)['drawing_review']>0
    for emp in engineers:emp.leave_until='2026-02-01'
    bucket,management=r.work(b,date.fromisoformat(e.world.date))
    assert capacity(r,b,bucket,management)['drawing_review']==0


def test_prices_and_disabling_do_not_reprice_accepted_jobs(game):
    e,b=prepared(game);change(e,b,'pcb_design');original=jobs(b)
    change(e,b,'pcb_design',price_percent=150)
    assert jobs(b)==original
    offered=next_offer(e.world,b,'pcb_design');assert offered['fee']>0
    change(e,b,'pcb_design',enabled=False)
    assert jobs(b)==original
    before=remaining(b);operate(e,b)
    assert remaining(b)<before
    assert next_offer(e.world,b).get('blocked')


def test_factory_kit_materials_are_cash_funded_and_income_is_separate(game):
    e,b=prepared(game,'factory');buy(e,b,'electronics_assembly');e.world.date='2026-01-19'
    # A small accepted order exercises actual production, rather than relying
    # on the candidate quote fitting the small acquired team's planning window.
    b.parallel_projects.append(dict(number=2,fee=240000,minutes=600,progress=0,earned=0))
    state(e.world,b)['jobs']['2']=dict(kit='electronics_assembly',materials=12000)
    before=e.world.cash(b.id);operate(e,b)
    row=state(e.world,b)['last']['electronics_assembly']
    assert row['output']>0 and row['revenue']>0
    assert e.world.cash(b.id)<before
    assert e.world.accounts[b.id]['expense:project_materials:electronics_assembly']==row['output']*12000//60
    assert e.world.accounts[b.id]['income:electronics_assembly']==-row['revenue']
    assert e.world.accounts[b.id]['asset:unbilled']==sum(j['earned'] for j in jobs(b))
    assert commitment(e.world,b)>0
    assert any('revenue-stream' in x['detail'] for x in cash_forecast(e.world,b.id)['rows'])


def test_factory_no_material_cash_means_no_unfunded_output(game):
    e,b=prepared(game,'factory');change(e,b,'general_production')
    cash=e.world.cash(b.id);e.post(b.id,'test-cash-shortage','Test cash shortage',{'asset:cash':-cash,'expense:test':cash})
    before=remaining(b);operate(e,b)
    assert remaining(b)==before


def test_stream_stock_respects_manager_cumulative_authority(game):
    e,b=prepared(game,'gas_station');buy(e,b,'convenience_grocery');e.world.date='2026-01-19';b.auto_restock=True
    contract(e,b,transaction_limit=100,period_limit=100)
    before=e.world.cash(b.id);operate(e,b)
    requests=[r for r in e.world.systems['management_requests'] if r['action']=='restock_stream' and r['status']=='open']
    assert requests and requests[0]['cost']==45*3*750
    assert state(e.world,b)['last']['convenience_grocery']['stock']==0
    assert e.pause_reasons


def test_configured_pages_and_save_reload_keep_stable_streams(game):
    e,b=prepared(game);buy(e,b,'embedded_design')
    game.store.commit(e,game.world.revision);game.world=e.world
    game.store.audit(game.world)
    reloaded=Game(game.store.path)
    try:assert reloaded.world.to_dict()==json.loads(json.dumps(game.world.to_dict()))
    finally:reloaded.close()
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html=client.get('/?page=business&business_id='+b.id).text
        assert 'Revenue streams and equipment kits' in html and 'data-action="buy_revenue_kit"' in html
        assert 'Setup until' in html and 'PCB design projects' in html
    assert game.world.to_dict()==before


def test_configured_daily_steps_match_reload_between_days(game,tmp_path):
    e,b=prepared(game,'gas_station');buy(e,b,'convenience_grocery');b.auto_restock=True
    a=Engine(copy.deepcopy(e.world));c=Engine(copy.deepcopy(e.world))
    from economic_simulation.domain import World
    for _ in range(9):
        a.advance_day();a.validate()
        c=Engine(World.from_dict(json.loads(json.dumps(c.world.to_dict()))));c.advance_day();c.validate()
    assert a.world.to_dict()==c.world.to_dict()


def test_price_demand_and_maintenance_change_stream_capacity(game):
    e,b=prepared(game);change(e,b,'pcb_design',weight=100)
    change(e,b,'support',enabled=False);change(e,b,'consulting',enabled=False)
    r=BusinessRules(e);buckets,management=r.work(b,date.fromisoformat(e.world.date))
    before=capacity(r,b,buckets,management)['pcb_design']
    change(e,b,'pcb_design',price_percent=175,weight=100)
    assert capacity(r,b,buckets,management)['pcb_design']<before
    change(e,b,'pcb_design',weight=100)
    from economic_simulation.industry_operations import IndustryOperations
    condition=IndustryOperations(e).state(b);condition['equipment_condition']=40
    damaged=capacity(r,b,buckets,management)['pcb_design']
    e.action('local_improvement',dict(business_id=b.id,kind='maintenance'),'kit-maintenance')
    assert capacity(r,b,buckets,management)['pcb_design']>damaged


def test_specialties_share_work_and_invoice_each_contract_once(game):
    e,b=prepared(game);buy(e,b,'drawing_review');e.world.date='2026-01-19'
    r=BusinessRules(e)
    for emp in r.staff(b.id):
        if r.position(emp.position_id).role=='engineer':r.person(emp.person_id).licenses['professional_engineer']='2027-01-01'
    b.parallel_projects.append(dict(number=2,fee=180000,minutes=600,progress=0,earned=0))
    state(e.world,b)['jobs']['2']=dict(kit='drawing_review',materials=0)
    original={j['number']:j['fee'] for j in jobs(b)}
    simultaneous=False
    for offset in range(25):
        e.world.date=(date(2026,1,19)+timedelta(days=offset)).isoformat()
        operate(e,b)
        records=state(e.world,b)['last']
        simultaneous |= records['pcb_design']['output']>0 and records['drawing_review']['output']>0
        assert sum(row['output'] for row in records.values())<=b.last_day['qualified_capacity']
    assert simultaneous and not jobs(b)
    completed=[h for h in b.project_history if h['number'] in original]
    assert len(completed)==2
    assert {h['stream'] for h in completed}=={'pcb_design','drawing_review'}
    assert sum(h['fee'] for h in completed)==sum(original.values())
    assert e.world.accounts[b.id]['asset:unbilled']==0
    assert len({p['source'] for p in e.postings if p['source'].startswith('project_invoice:')})==2


def test_existing_factory_finished_goods_are_used_without_buying_them_twice(game):
    e,b=prepared(game,'factory')
    from economic_simulation.industry_operations import IndustryOperations
    operations=IndustryOperations(e).state(b)
    cost=10000
    e.post(b.id,'test-finished-goods','Existing prepaid finished goods',{'asset:cash':-cost,'asset:finished_goods':cost})
    operations.update(finished_units=2,finished_cost=cost)
    change(e,b,'general_production')
    cash=e.world.cash(b.id);e.post(b.id,'test-cash-drain','Test shortage',{'asset:cash':-cash,'expense:test':cash})
    before=remaining(b);operate(e,b)
    assert remaining(b)==before-120
    assert e.world.accounts[b.id]['asset:finished_goods']==0
    assert operations['finished_units']==0 and operations['finished_cost']==0


@pytest.mark.parametrize('industry',['gas_station','factory'])
def test_staffing_guide_includes_added_sales_and_factory_recipe(game,industry):
    e,b=prepared(game,industry)
    from economic_simulation.staffing import staffing_plan
    before=staffing_plan(e.world,b.id)
    buy(e,b,'convenience_grocery' if industry=='gas_station' else 'electronics_assembly')
    after=staffing_plan(e.world,b.id)
    assert ('convenience streams' if industry=='gas_station' else '30 machine-operator minutes') in after['workload']
    assert after!=before


def test_automatic_jobs_skip_unstaffed_specialty(game):
    e,b=prepared(game);buy(e,b,'drawing_review');e.world.date='2026-01-19';b.auto_projects=True
    r=BusinessRules(e)
    for emp in r.staff(b.id):r.person(emp.person_id).licenses.pop('professional_engineer',None)
    from economic_simulation.project_portfolio import autofill
    autofill(r,b,1000)
    assert len(jobs(b))>1
    assert all(tag(e.world,b,j['number'])['kit']=='pcb_design' for j in jobs(b))
    e.validate()


def test_fuel_price_controls_stay_in_sync_and_preserve_franchise_bounds(game):
    e,b=prepared(game,'gas_station');change(e,b,'fuel',price_percent=125)
    assert b.price_percent==125
    e.action('business_policy',dict(business_id=b.id,price_percent=110),'legacy-fuel-price')
    assert state(e.world,b)['offers']['fuel']['price_percent']==110
    e.world.systems['franchises'].append(dict(operator=b.id,status='active'))
    with pytest.raises(RuleError):change(e,b,'fuel',price_percent=140)
    assert b.price_percent==110
