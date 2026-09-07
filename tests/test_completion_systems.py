import copy
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_business import acquire
from test_leadership import setup
from test_specialists import add_specialist
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.distress import Distress
from economic_simulation.service_office import ServiceOffice
from economic_simulation.property_operations import PropertyOperations,systems_for
from economic_simulation.industry_operations import IndustryOperations
from economic_simulation.banking import bank_view


def test_dated_lots_settle_fifo_and_reconcile(game):
    e=Engine(copy.deepcopy(game.world))
    e.post('personal','first','Supplier invoice',{'expense:test':10000,'liability:payable':-10000})
    e.world.date='2026-01-02'
    e.post('personal','second','Supplier invoice',{'expense:test':5000,'liability:payable':-5000})
    e.post('personal','payment','Partial payment',{'asset:cash':-12000,'liability:payable':12000})
    lots=Distress(e).obligations('personal')
    assert len(lots)==1 and lots[0]['source']=='second' and lots[0]['remaining']==3000
    e.validate()


def test_subsidiary_closes_without_billing_parent_and_retains_people(game):
    e,l,b,manager,_=setup(game)
    parent=copy.deepcopy(e.world.accounts[b.owner]);identity=manager.person_id
    e.post(b.id,'missed-pay','Earned wages',{'expense:wages':10000,'liability:payroll':-10000})
    e.world.date='2026-03-20';Distress(e).tick()
    assert b.status=='closed' and manager.status=='ended' and manager.person_id==identity
    assert e.world.accounts[b.owner]==parent
    assert e.world.accounts[b.id]['liability:payroll']<0
    assert not e.world.systems.get('campaign_outcome')
    e.validate()


def test_distress_recovery_and_parent_campaign_ending(game):
    e=Engine(copy.deepcopy(game.world))
    e.post('personal','invoice','Debt',{'expense:test':10000,'liability:payable':-10000})
    e.world.date='2026-01-20';Distress(e).tick()
    assert e.world.systems['distress']['personal']['phase']=='impaired'
    Distress(e).action('settle_obligations',dict(entity='personal'),'settle')
    Distress(e).tick();assert e.world.systems['distress']['personal']['phase']=='healthy'
    e.post('personal','second-invoice','Debt',{'expense:test':10000,'liability:payable':-10000})
    e.world.date='2026-05-01';Distress(e).tick()
    assert e.world.systems['campaign_outcome']['status']=='insolvent'
    with pytest.raises(RuleError,match='insolvency'):e.advance_day()
    e.validate()


def test_qualified_department_queue_overload_and_consumed_time(game):
    e,l,b,_,_=setup(game)
    emp,_=add_specialist(e,b.id,'accounting')
    office=ServiceOffice(e)
    office.action('department_configure',dict(provider=b.id,department='accounting',staff=emp.id,regions=b.region,industries=b.industry),'dept')
    for _ in range(3):office.action('service_request',dict(provider=b.id,recipient=b.id,department='accounting',mode='internal'),'task')
    buckets={role:[0]*24 for role in l.rules.work(b,date.fromisoformat(e.world.date))[0]}
    buckets['accounting'][8]=240
    office.deliver(l.rules,b,buckets)
    tasks=e.world.systems['service_tasks']
    assert sum(t['worked'] for t in tasks)<=240
    assert tasks[1]['worked']==tasks[2]['worked']==0
    assert sum(buckets['accounting'])==0
    e.validate()


def test_outside_services_are_prepaid_then_expensed_and_saved(game):
    bid=acquire(game)
    before=game.world.cash(bid)
    act(game,'service_request',recipient=bid,provider='outside',department='accounting',mode='outside')
    assert before-game.world.cash(bid)==480*150
    assert game.world.accounts[bid]['asset:prepaid_services']==480*150
    step(game,2)
    task=game.world.systems['service_tasks'][-1]
    assert task['status']=='complete' and task['outside_cost']==72000
    assert game.world.accounts[bid]['asset:prepaid_services']==0
    assert game.world.systems['management_reports'][-1]['business_id']==bid
    assert game.store.load().systems['service_tasks']==game.world.systems['service_tasks']
    game.store.audit(game.world)


def test_legal_review_uses_existing_facts_and_can_fail(game):
    e=Engine(copy.deepcopy(game.world));p=e.world.properties[0]
    facts=copy.deepcopy(systems_for(e.world,p));original=p.asking
    office=ServiceOffice(e)
    office.action('service_request',dict(provider='outside',recipient='personal',department='legal',mode='outside',matter='negotiation',target_id=p.id),'review')
    task=e.world.systems['service_tasks'][-1]
    office.legal_result(task,0)
    assert p.asking==original and task['improvement']==task['recovered']==0
    assert systems_for(e.world,p)==facts and 'refused' in task['outcome']
    with pytest.raises(RuleError,match='already'):
        office.action('service_request',dict(provider='outside',recipient='personal',department='legal',mode='outside',matter='negotiation',target_id=p.id),'reroll')


def test_repairs_consume_resources_change_existing_system_and_keep_basis_reconciled(game):
    p=game.world.properties[0];act(game,'buy',property_id=p.id)
    before=game.world.cash('personal')
    act(game,'property_work',property_id=p.id,system='roof',kind='replacement',provider='outside')
    p=game.world.properties[0]
    condition=systems_for(game.world,p)['roof']['condition']
    assert game.world.cash('personal')<before
    step(game,8)
    job=game.world.systems['property_work'][-1]
    assert job['status']=='complete' and job['actual_cost']>0 and job['remaining']==0
    p=next(p for p in game.world.properties if p.id==job['property_id'])
    assert systems_for(game.world,p)['roof']['condition']>condition
    assert game.world.accounts['personal']['asset:prepaid_works']==0
    game.store.audit(game.world)


def test_property_proposals_and_deposit_liabilities(game):
    pid=game.world.properties[0].id;act(game,'buy',property_id=pid)
    act(game,'advertise_space',property_id=pid,rent=100000)
    step(game,5)
    offers=game.world.systems['tenant_offers'];assert len(offers)==3
    offer=next(o for o in offers if o['area']<=game.world.properties[0].spaces[0]['area'])
    act(game,'accept_tenant',property_id=pid,offer_id=offer['id'],rent=offer['rent'])
    lease=game.world.systems['leases'][-1]
    assert lease['reliability']==offer['reliability']
    assert game.world.accounts['personal']['liability:deposit:'+lease['id']]==-offer['rent']
    assert len(game.world.businesses)==len(game.store.load().businesses)
    game.store.audit(game.world)


@pytest.mark.parametrize('high_cost',[False,True])
def test_completed_flips_can_gain_or_lose_money(game,high_cost):
    pid=game.world.properties[0].id;act(game,'buy',property_id=pid)
    e=Engine(copy.deepcopy(game.world));p=e.get_property(pid)
    if high_cost:
        cost=15000000;e.post('personal','costly-work','Over-budget renovation',{'asset:cash':-cost,'asset:property':cost});p.basis+=cost
    ops=PropertyOperations(e)
    ops.action('market_property',dict(property_id=pid,asking=p.value),'list')
    listing=e.world.systems['property_listings'][pid]
    # Concrete accepted cash offer fixture eliminates financing randomness for the profit assertion.
    listing.update(status='closing',accepted='test-sale',due=e.world.date)
    listing['offers']=[dict(id='test-sale',price=p.value,concession=0,finance_risk=0,status='accepted')]
    ops.sales_tick()
    assert listing['status']=='sold'
    assert (listing['project_profit']<0)==high_cost
    assert listing['cash_returned']==listing['proceeds']
    e.validate()


def test_bank_deposits_do_not_create_capital_or_unlimited_lending(game):
    from test_new_industries import purchase
    bid=purchase(game,'bank');b=next(b for b in game.world.businesses if b.id==bid)
    e=Engine(copy.deepcopy(game.world));b=next(b for b in e.world.businesses if b.id==bid)
    before=bank_view(e.world,b)
    e.post(bid,'deposits','Customer funds',{'asset:cash':100000000,'liability:customer_deposits':-100000000})
    after=bank_view(e.world,b)
    assert after['capital']==before['capital']
    assert after['lendable']<=after['capital_headroom']
    e.validate()


def test_all_new_screens_render_without_mutating_world(game):
    acquire(game)
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        for page in ('operations_center','home_office','property_workbench'):
            response=client.get('/',params={'page':page})
            assert response.status_code==200 and 'data-action=' in response.text
    assert game.world.to_dict()==before


def test_new_workflows_daily_batch_and_reload_equivalence(game,tmp_path):
    from economic_simulation.persistence import Store
    pid=game.world.properties[0].id
    act(game,'buy',property_id=pid)
    act(game,'property_work',property_id=pid,kind='repair',system='roof',provider='outside')
    act(game,'service_request',recipient='personal',provider='outside',department='finance',mode='outside')
    original=copy.deepcopy(game.world)
    left=copy.deepcopy(original)
    for _ in range(12):
        e=Engine(left);e.advance_day();e.validate();left=e.world
    import sqlite3
    with game.store.connection() as source, sqlite3.connect(tmp_path/'replay.sqlite3') as destination:source.backup(destination)
    store=Store(tmp_path/'replay.sqlite3')
    right=store.load()
    for _ in range(12):
        e=Engine(right);e.advance_day();store.commit(e,right.revision);right=store.load()
    # Revisions are transaction metadata; all simulated state and RNG must match.
    left.revision=right.revision
    assert left.to_dict()==right.to_dict()
    store.audit(right)


def test_internal_construction_consumes_capacity_without_group_service_profit(game):
    from economic_simulation.business_views import group_profit,entity_names
    e,l,b,_,_=setup(game)
    emp,person=add_specialist(e,b.id,'maintenance');person.skills['maintenance']=90
    pid=e.world.properties[0].id;e.action('buy',dict(property_id=pid),'buy')
    p=e.get_property(pid);p.region=b.region
    ops=PropertyOperations(e);ops.action('property_work',dict(property_id=pid,system='roof',kind='replacement',provider=b.id),'work')
    buckets={role:[0]*24 for role in l.rules.work(b,date.fromisoformat(e.world.date))[0]};buckets['maintenance'][8]=240
    before=group_profit(e.world,list(entity_names(e.world)))
    ops.deliver(l.rules,b,buckets)
    job=e.world.systems['property_work'][-1]
    labor=job['actual_cost']-job['materials']
    assert job['remaining']==job['effort']-240 and sum(buckets['maintenance'])==0 and labor>0
    # The existing payroll cost is capitalized, never marked up as group income.
    assert group_profit(e.world,list(entity_names(e.world)))-before==labor
    assert not any(k.startswith('income:internal') and v for k,v in e.world.accounts[b.id].items())
    assert e.world.accounts['personal']['liability:intercompany:'+b.id]==-labor
    e.validate()


def test_delegated_lease_requires_template_and_stops_before_execution(game):
    from test_authority import contract
    from economic_simulation.authority import Authority
    e,l,b,_,_=setup(game);contract(e,b)
    refusal=Authority(e).check(b,None,'accept_tenant',dict(property_id=e.world.properties[0].id),0)
    assert 'template' in refusal
    e.world.systems['legal_templates']={b.id:{'routine_lease':dict(expires='2027-01-01')}}
    assert Authority(e).check(b,None,'accept_tenant',dict(region='Outside scope'),0)
    assert Authority(e).check(b,None,'accept_tenant',{},0) is None
    assert Authority(e).check(b,None,'fund_flip',{},0)=='Policy requires player approval.'


def test_flip_funding_ringfences_future_cash_and_refuses_overrun(game):
    pid=game.world.properties[0].id
    act(game,'inspect_property',property_id=pid)
    act(game,'flip_budget',property_id=pid,renovation=100,days=7)
    act(game,'fund_flip',property_id=pid)
    before=copy.deepcopy(game.world.accounts)
    with pytest.raises(RuleError,match='reserve'):
        Engine(copy.deepcopy(game.world)).action('flip_work',dict(property_id=pid),'too-big')
    assert game.world.accounts==before
    reserve=game.world.systems['flip_progress'][pid]['reserve']
    step(game,1)
    assert game.world.systems['flip_progress'][pid]['reserve']<reserve
    assert game.world.accounts['personal']['asset:flip_reserve']==sum(r['reserve'] for r in game.world.systems['flip_progress'].values())
    act(game,'add_flip_reserve',property_id=pid,amount=500000)
    act(game,'flip_work',property_id=pid)
    step(game,5)
    assert game.world.systems['property_work'][-1]['status']=='complete'
    game.store.audit(game.world)


def test_mixed_service_refunds_unused_outside_and_counts_actual_internal_time(game):
    e,l,b,_,_=setup(game);emp,p=add_specialist(e,b.id,'accounting');p.skills['finance']=100
    office=ServiceOffice(e);office.action('department_configure',dict(provider=b.id,department='accounting',regions=b.region,industries=b.industry,tools=3),'dept')
    office.action('service_request',dict(provider=b.id,recipient=b.id,department='accounting',mode='mixed'),'work')
    task=e.world.systems['service_tasks'][-1];before=e.world.cash(b.id)
    buckets={'accounting':[0]*24};buckets['accounting'][8]=480
    office.deliver(l.rules,b,buckets);office.tick()
    assert task['status']=='complete' and task['outside_cost']==0
    assert e.world.cash(b.id)==before+72000 and e.world.accounts[b.id]['asset:prepaid_services']==0
    assert sum(buckets['accounting'])<480
    e.validate()


def test_legal_collects_existing_business_receivable_and_not_hypothetical_income(game):
    e,l,b,_,_=setup(game);l.rules.invoice(b,100000,'customer','existing-invoice',14)
    invoice=b.receivables[-1];invoice['overdue_since']=e.world.date
    office=ServiceOffice(e);office.action('service_request',dict(provider='outside',recipient=b.id,department='legal',mode='outside',matter='collection',target_id=invoice['id']),'legal')
    task=e.world.systems['service_tasks'][-1];before=e.world.cash(b.id);income=e.world.accounts[b.id]['income:customer']
    office.legal_result(task,100)
    assert task['recovered']==100000 and e.world.cash(b.id)==before+100000
    assert e.world.accounts[b.id]['income:customer']==income and not b.receivables
    e.validate()


def test_inventory_batches_expire_and_dealership_age_changes_real_price(game):
    e,l,b,_,_=setup(game);industry=IndustryOperations(e)
    b.industry='grocery';lots=industry.lots(b);lots[0]['received']='2026-01-01'
    original=b.inventory_units;industry.add_stock(b,10);b.inventory_units+=10
    e.post(b.id,'stock-fixture','New delivery',{'asset:cash':-10*b.unit_cost,'asset:inventory':10*b.unit_cost})
    industry.before(b,{})
    assert b.inventory_units==10 and e.world.accounts[b.id]['expense:spoilage']==original*b.unit_cost
    b.industry='car_dealership';industry.lots(b)[0]['received']='2025-01-01'
    assert industry.sale_factor(b,5)==75
    e.validate()


def test_vp_remains_single_employee_and_cannot_duplicate_director_time(game):
    from economic_simulation.executives import Executives
    e,l,b,emp,_=setup(game);salary=emp.salary;count=len(e.world.employments)
    Executives(e).action(dict(employment_id=emp.id,business_ids=b.id,role='division_vp'))
    assert emp.salary==salary*125//100 and len(e.world.employments)==count
    assert l.reserved_minutes(emp)==30
    with pytest.raises(RuleError,match='executive'):
        l.action('director_assign',dict(employment_id=emp.id,business_id=b.id),'duplicate')
    e.validate()


@pytest.mark.parametrize('tenant_kind',['external','owned'])
def test_occupied_sale_transfers_lease_deposit_and_receivable_without_tenant_ownership(game,tenant_kind):
    from economic_simulation.real_estate import RealEstate
    e,l,b,_,_=setup(game);p=e.world.properties[0];p.region=b.region;p.category='commercial'
    e.action('buy',dict(property_id=p.id),'buy');estate=RealEstate(e)
    estate.action('configure_spaces',dict(property_id=p.id,units=1),'spaces')
    tenant='external' if tenant_kind=='external' else b.id
    estate.action('lease_space',dict(property_id=p.id,space_id=p.spaces[0]['id'],tenant=tenant,rent=100000),'lease')
    estate.tick(date.fromisoformat(e.world.date));lease=e.world.systems['leases'][-1]
    old_owner=b.owner;ops=PropertyOperations(e)
    ops.action('market_property',dict(property_id=p.id,asking=p.value),'list')
    listing=e.world.systems['property_listings'][p.id]
    listing.update(status='closing',accepted='occupied-sale',due=e.world.date)
    listing['offers']=[dict(id='occupied-sale',price=p.value,concession=0,finance_risk=0,status='accepted')]
    ops.sales_tick()
    assert listing['status']=='sold' and b.owner==old_owner
    assert lease['owner']==p.owner and lease['owner'].startswith('external-property-buyer:')
    assert lease['status']=='active' and e.world.accounts['personal']['liability:deposit:'+lease['id']]==0
    assert e.world.accounts[p.owner]['liability:deposit:'+lease['id']]==-lease['deposit_remaining']
    e.validate();e.world.date='2026-01-13';estate.tick(date.fromisoformat(e.world.date));e.validate()


def test_missed_loans_and_guarantees_do_not_duplicate_past_interest(game):
    from economic_simulation.finance_rules import Finance
    e,l,b,_,_=setup(game);finance=Finance(e)
    finance.action('borrow',dict(entity=b.id,amount=1200000,months=12,guarantor=b.owner),'loan')
    for entity in (b.id,b.owner):
        cash=e.world.cash(entity);e.post(entity,'cash-loss:'+entity,'Cash loss fixture',{'asset:cash':-cash,'expense:loss':cash})
    loan=e.world.systems['loans'][-1]
    for _ in range(2):
        e.world.date=loan['next_due'];finance.end_day(date.fromisoformat(e.world.date))
        assert loan['arrears']==loan['overdue_principal']+loan['interest_due']
        assert loan['guarantee_claim']==loan['arrears']
        assert -e.world.accounts[b.owner]['liability:intercompany:'+b.id]==loan['arrears']
        e.validate()
    e.post(b.id,'recovery','Outside capital fixture',{'asset:cash':loan['arrears'],'equity:recovery':-loan['arrears']})
    finance.action('repay_loan',dict(entity=b.id,loan_id=loan['id'],amount=loan['arrears']),'pay')
    assert loan['arrears']==loan['guarantee_claim']==0
    assert e.world.accounts[b.owner]['liability:intercompany:'+b.id]==0
    e.validate()


def test_overloaded_service_can_be_reassigned_without_forgiving_costs(game):
    e,l,b,_,_=setup(game);office=ServiceOffice(e)
    office.action('department_configure',dict(provider=b.id,department='finance'),'empty')
    office.action('service_request',dict(provider=b.id,recipient=b.id,department='finance',mode='internal'),'queue')
    task=e.world.systems['service_tasks'][-1];cash=e.world.cash(b.id)
    office.action('outsource_service',dict(task_id=task['id']),'outsource')
    assert e.world.cash(b.id)==cash-600*150
    for _ in range(3):office.tick()
    assert task['status']=='complete' and task['outside_cost']==90000
    e.validate()


def test_single_company_locations_share_obligations_but_not_unrelated_subsidiaries(game):
    from economic_simulation.operating_locations import OperatingLocations
    from economic_simulation.authority import cash_forecast
    e,l,b,_,_=setup(game)
    e.post(b.id,'capital','Growth capital fixture',{'asset:cash':20000000,'equity:test':-20000000})
    locations=OperatingLocations(e)
    locations.action(dict(entity=b.id,name='Second retail location',region=b.region),'location')
    unit=e.world.businesses[-1]
    assert unit.industry==b.industry and e.world.systems['operating_locations'][unit.id]['company']==b.id
    for entity in (b.id,unit.id):
        cash=e.world.cash(entity);e.post(entity,'drain:'+entity,'Distress fixture',{'asset:cash':-cash,'expense:loss':cash})
    e.post(unit.id,'earned','Location payroll obligation',{'expense:wages':100000,'liability:payroll':-100000})
    locations.settle()
    assert e.world.accounts[b.id]['liability:intercompany:'+unit.id]==-100000
    assert cash_forecast(e.world,b.id)['available']<cash_forecast(e.world,unit.id)['available']
    locations.settle();assert e.world.accounts[b.id]['liability:intercompany:'+unit.id]==-100000
    e.validate()


def test_location_profit_and_loss_are_taxed_once_in_the_legal_company(game):
    from economic_simulation.operating_locations import OperatingLocations
    from economic_simulation.finance_rules import Finance
    e,l,b,_,_=setup(game)
    e.post(b.id,'capital','Growth capital fixture',{'asset:cash':20000000,'equity:test':-20000000})
    OperatingLocations(e).action(dict(entity=b.id,name='Branch',region=b.region),'location')
    unit=e.world.businesses[-1];e.post(unit.id,'sale','Branch sale fixture',{'asset:cash':10000000,'income:sales':-10000000})
    e.world.date='2026-01-31';Finance(e).monthly_taxes(date.fromisoformat(e.world.date))
    assert e.world.accounts[unit.id].get('liability:income_tax',0)==0
    assert 'liability:income_tax' in e.world.accounts[b.id]
    e.validate()


def test_operations_upgrade_backups_preserves_balances_people_and_date(tmp_path):
    import json,sqlite3
    from economic_simulation.domain import new_game
    from economic_simulation.persistence import Store
    path=tmp_path/'older.sqlite3';e=new_game();e.world.systems['version']=1;e.world.systems.pop('operations_version')
    before=copy.deepcopy(e.world.to_dict());Store(path,initial=e)
    upgraded=Store(path);after=upgraded.load()
    assert after.accounts==before['accounts'] and after.date==before['date']
    assert [vars(p) for p in after.people]==before['people']
    assert after.systems['version']==5 and after.systems['operations_version']==11
    assert len(list(tmp_path.glob('older.before-operations-*.sqlite3')))==1
    upgraded.audit(after)
    assert Store(path).load().to_dict()==after.to_dict()


def test_shared_service_future_spending_counts_toward_delegated_monthly_limit(game):
    from test_authority import contract
    from economic_simulation.authority import Authority
    e,l,b,_,other=setup(game,two=True)
    office=ServiceOffice(e);office.action('department_configure',dict(provider=other,department='accounting',regions=b.region),'dept')
    prior=Authority(e).spent('manager:'+b.id)
    key=contract(e,b,period_limit=prior+100000)
    args=dict(recipient=b.id,provider=other,department='accounting',mode='internal')
    assert l.perform(b,'report-1','service_request',args,0,True,'Internal accounting report')
    assert Authority(e).spent(key)-prior==72000
    assert not l.perform(b,'report-2','service_request',args,0,True,'Another report')
    assert len(e.world.systems['service_tasks'])==1
    e.validate()


def test_foreign_operation_cannot_be_hidden_in_delegated_action_args(game):
    from test_authority import contract
    e,l,b,_,other=setup(game,two=True);contract(e,b)
    before=copy.deepcopy(e.world.accounts[other])
    assert not l.perform(b,'outside-scope','restock',dict(business_id=other,units=10),10000,True,'Wrong operation')
    assert e.world.accounts[other]==before
    assert 'scope' in e.world.systems['management_requests'][-1]['detail']


def test_closed_operation_asset_sale_is_delayed_and_records_real_loss(game):
    from economic_simulation.simulation_support import stable_roll
    e,l,b,_,_=setup(game);recovery=Distress(e);recovery.close(b,'Test closure')
    recovery.action('liquidate_assets',dict(entity=b.id),'market-assets')
    plan=e.world.systems['asset_liquidations'][-1]
    plan['id']=next('buyer-'+str(n) for n in range(100) if stable_roll(e.world,'buyer-'+str(n)+':buyer')>=20)
    cash=e.world.cash(b.id);recovery.liquidations();assert e.world.cash(b.id)==cash
    e.world.date=plan['due'];recovery.liquidations()
    assert plan['status']=='sold' and 0<plan['proceeds']<plan['book_value']
    assert e.world.cash(b.id)==cash+plan['proceeds'] and b.inventory_units==b.equipment==0
    assert e.world.accounts[b.id]['expense:liquidation_loss']==plan['loss']
    with pytest.raises(RuleError,match='closed'):l.rules.action('restock',dict(business_id=b.id,units=1),'restock-closed')
    e.validate()


def test_internal_repair_without_staff_can_be_completed_by_outside_contractor(game):
    e,l,b,_,_=setup(game);p=e.world.properties[0]
    e.action('buy',dict(property_id=p.id),'buy')
    ops=PropertyOperations(e);ops.action('property_work',dict(property_id=p.id,kind='repair',system='roof',provider=b.id),'internal')
    job=e.world.systems['property_work'][-1];cash=e.world.cash('personal')
    ops.action('outsource_property_work',dict(property_id=p.id,work_id=job['id']),'outsource')
    assert e.world.cash('personal')==cash-job['remaining']*100
    for _ in range(3):ops.tick()
    assert job['status']=='complete' and job['prepaid']==0
    e.validate()
