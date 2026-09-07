import copy
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_leadership import setup
from test_authority import contract
from test_manager_routines import invoice
from test_specialists import add_specialist
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.leadership import Leadership
from economic_simulation.authority import Authority
from economic_simulation.routine_management import RoutineManagement,policy as routine_policy,assigned_collection
from economic_simulation.manager_defaults import automation,limits
from economic_simulation.management import Management,policy,growth_status
from economic_simulation.decision_inbox import items


def profitable(e,b):
    # Seed recorded demand and paid sales, with matching ledger entries.
    e.world.date='2026-02-01';b.history=[]
    for _ in range(14):
        e.post(b.id,'sales-'+e.world.date,'Recorded customer sales',{'asset:cash':100000,'income:sales':-100000})
        b.history.append(dict(date=e.world.date,output=100,capacity=100,profit=100000))
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    e.world.date='2026-02-16'
    b.last_day=b.history[-1]


def test_collections_belong_to_manager_until_exception_without_setup(game):
    e,l,b,manager,_=setup(game);r=invoice(e,b)
    before=copy.deepcopy(e.world.to_dict())
    assert assigned_collection(e.world,b,r)
    assert not any(i['kind']=='invoice' for i in items(e.world))
    assert e.world.to_dict()==before
    RoutineManagement(e).tick()
    assert r['recovery']['method']=='reminder'
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    RoutineManagement(e).action(dict(business_id=b.id,collections=False))
    another=invoice(e,b,'manual-invoice')
    assert any(i['kind']=='invoice' and i['targets']['invoice_id']==another['id'] for i in items(e.world))


def test_large_contingency_fee_uses_collection_authority_and_only_recovered_cash(game):
    from economic_simulation.customer_collections import CustomerCollections
    e,l,b,manager,_=setup(game);r=invoice(e,b,amount=2000000)
    r['recovery_attempts']=['reminder','plan'];cash=e.world.cash(b.id)
    RoutineManagement(e).tick()
    assert r['recovery']['method']=='agency' and e.world.cash(b.id)==cash
    audit=e.world.systems['authority_audit'][-1]
    assert audit['commitment']==500000 and audit['cash_cost']==0 and audit['actor']==manager.id
    e.world.date=r['recovery']['next_date'];CustomerCollections(e).collect(b)
    if r['recovery']['status']=='complete':
        assert e.world.cash(b.id)==cash+1500000
        assert e.world.accounts[b.id]['expense:collection_fees']==500000
    else:assert e.world.cash(b.id)==cash
    e.validate()


def test_collection_override_really_blocks_and_creates_a_manager_question(game):
    e,l,b,manager,_=setup(game);r=invoice(e,b,amount=2000000);r['recovery_attempts']=['reminder','plan']
    RoutineManagement(e).action(dict(business_id=b.id,collection_limit=10000))
    RoutineManagement(e).tick()
    assert not r.get('recovery')
    question=next(i for i in items(e.world) if i['kind']=='management')
    assert question['source']['cost']==500000 and l.rules.person(manager.person_id).name in question['detail']
    from economic_simulation.recovery_navigation import delegation_link
    link=delegation_link(e.world,question['source']['id'])
    assert link['url'].endswith('#routine-policy-'+b.id)
    game.store.commit(e,game.world.revision);game.world=e.world
    with client_for(game) as client:
        html=client.get('/?page=operations_center&scope='+b.id).text
        assert 'Waiting for your decision in Decision inbox' in html
        assert 'Review the manager’s question' in html and 'Change collection limits' in html


def test_default_contingency_collection_can_help_cash_distress(game):
    e,l,b,manager,_=setup(game);r=invoice(e,b,amount=2000000)
    r['recovery_attempts']=['reminder','plan'];cash=e.world.cash(b.id)
    e.post(b.id,'overdue-cost','Missed operating obligation',{'expense:operations':cash+1000000,'liability:operating':-cash-1000000})
    RoutineManagement(e).tick()
    assert r['recovery']['method']=='agency' and e.world.cash(b.id)==cash
    assert e.world.systems['authority_audit'][-1]['commitment']==500000
    e.validate()


def test_manager_uses_staffed_legal_department_but_outsources_when_overloaded(game):
    from economic_simulation.service_office import ServiceOffice
    e,l,b,manager,_=setup(game);emp,_=add_specialist(e,b.id,'legal')
    office=ServiceOffice(e)
    office.action('department_configure',dict(provider=b.id,department='legal',staff=emp.id,regions=b.region,industries=b.industry),'department')
    r=invoice(e,b,amount=1000000);r['recovery_attempts']=['reminder','plan','agency']
    RoutineManagement(e).tick();task=e.world.systems['service_tasks'][-1]
    assert task['provider']==b.id and task['mode']=='internal' and task.get('prepaid',0)==0
    before=task['remaining'];l.rules.operate(b,date.fromisoformat(e.world.date))
    assert task['remaining']<before and task['status']!='complete'
    task['remaining']=10000
    proposal=RoutineManagement(e).collection_proposal(b,r,routine_policy(e.world,b))
    assert proposal[1]['provider']=='outside'


def test_manager_queues_real_legal_work_then_escalates_large_remaining_loss(game):
    from economic_simulation.service_office import ServiceOffice
    e,l,b,manager,_=setup(game);r=invoice(e,b,amount=1000000)
    r['recovery_attempts']=['reminder','plan','agency'];cash=e.world.cash(b.id)
    RoutineManagement(e).tick();task=e.world.systems['service_tasks'][-1]
    assert task['target_id']==r['id'] and task['matter']=='collection' and task['remaining']==1200
    assert task['prepaid']==180000 and e.world.cash(b.id)==cash-180000
    for _ in range(8):
        ServiceOffice(e).tick();e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    assert task['status']=='complete' and task['outside_cost']>0
    while date.fromisoformat(e.world.date).weekday()>4:e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    RoutineManagement(e).tick()
    assert any(q['action']=='write_off_invoice' and q['cost']==r['amount'] for q in e.world.systems['management_requests'])
    e.validate()


def test_exhausted_small_balance_is_written_off_once_by_manager(game):
    e,l,b,manager,_=setup(game);r=invoice(e,b,amount=50000);r['recovery_attempts']=['reminder','plan','agency']
    cash=e.world.cash(b.id);RoutineManagement(e).tick();RoutineManagement(e).tick()
    assert r not in b.receivables and e.world.cash(b.id)==cash
    assert e.world.accounts[b.id]['expense:bad_debt']==50000
    assert sum(row['action']=='write_off_invoice' for row in e.world.systems['authority_audit'])==1
    e.validate()


def test_director_appointment_enables_growth_with_real_cost_and_pay_history(game):
    e,l,b,manager,_=setup(game);profitable(e,b);before=manager.salary;count=len(e.world.employments)
    l.action('director_assign',dict(business_id=b.id,employment_id=manager.id),'promote')
    assert manager.salary>before and len(e.world.employments)==count
    assert policy(b,e.world)['growth']=='auto' and l.view(b)['managing_director']
    assert growth_status(e.world,b)['ready']
    cash=e.world.cash(b.id);l.grow(b)
    plan=next(p for p in e.world.systems['plans'] if p['kind']=='upgrade')
    assert e.world.cash(b.id)==cash-plan['cost'] and plan['status']=='active'
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    assert e.world.systems['authority_audit'][-1]['charged_to']==['director:'+manager.id]
    assert any('Appointed' in h['event'] for h in l.rules.person(manager.person_id).history)
    l.action('director_remove',dict(business_id=b.id),'remove')
    assert policy(b,e.world)['growth']=='off' and l.actor(b)==(None,manager)
    e.validate()


def test_default_director_growth_waits_for_evidence_and_respects_overrides(game):
    e,l,b,manager,_=setup(game)
    from economic_simulation.operating_automation import OperatingAutomation
    OperatingAutomation(e).action(dict(business_id=b.id,pricing=False))
    Management(e).action(dict(target=b.id,hiring='freeze'))
    l.action('director_assign',dict(business_id=b.id,employment_id=manager.id),'promote')
    assert policy(b,e.world)['growth']=='auto' and policy(b,e.world)['hiring']=='freeze'
    assert automation(e.world,b)['locations'] and automation(e.world,b)['location_limit']==2
    assert not automation(e.world,b)['pricing']
    assert not growth_status(e.world,b)['ready']
    profitable(e,b);Management(e).action(dict(target=b.id,growth='off'))
    l.grow(b);assert not any(p['kind']=='upgrade' for p in e.world.systems['plans'])
    assert not policy(b,e.world)['growth']=='auto'


def test_manager_automatically_inherits_parent_controls_and_cumulative_budget(game):
    e,l,b,manager,_=setup(game);director=next(emp for emp in l.rules.staff(b.id) if emp.id!=manager.id)
    l.action('director_assign',dict(business_id=b.id,employment_id=director.id,limit=10000000),'director')
    parent=contract(e,b,target='director:'+director.id,contracts='allow',purchasing='allow',period_limit=b.unit_cost*2,transaction_limit=b.unit_cost*2)
    assert 'manager:'+b.id not in e.world.systems['authority_contracts']
    assert l.perform(b,'stock-one','restock',dict(business_id=b.id,units=1),b.unit_cost,True,'Stock')
    row=e.world.systems['authority_audit'][-1]
    assert row['actor']==manager.id and parent in row['charged_to']
    assert Authority(e).spent(parent)==b.unit_cost
    contract(e,b,target=parent,contracts='prohibit')
    r=invoice(e,b);RoutineManagement(e).tick()
    assert not r.get('recovery') and 'prohibits' in e.world.systems['management_requests'][-1]['detail']


def test_director_daily_and_monthly_limits_and_scope_restrict_default_grant(game):
    e,l,b,manager,second=setup(game,True)
    l.action('director_assign',dict(business_id=b.id,employment_id=manager.id,limit=100000),'director')
    record=l.director(b.id)[0];a=Authority(e)
    assert 'scope' in a.check(b,record,'restock',dict(business_id=second),0)
    assert 'approval' in a.check(b,record,'borrow',dict(entity=b.id),0)
    a.record(b,record,manager,'restock',400000,0,'Prior cumulative commitments')
    assert 'Cumulative' in a.check(b,record,'restock',dict(business_id=b.id),1)
    assert not l.perform(b,'over-limit','restock',dict(business_id=b.id,units=100000//b.unit_cost+1),100001,True,'Complete order')


def test_default_director_can_fund_one_additional_same_industry_location(game):
    e,l,b,manager,_=setup(game);profitable(e,b)
    e.post('personal','test-capital','Owner capital for test',{'asset:cash':100000000,'equity:capital':-100000000})
    e.action('fund_business',dict(business_id=b.id,amount=100000000),'growth-capital')
    l.action('director_assign',dict(business_id=b.id,employment_id=manager.id),'director')
    b.capacity_percent=160
    from economic_simulation.operating_automation import OperatingAutomation
    OperatingAutomation(e).tick();OperatingAutomation(e).tick()
    units=[unit for unit in e.world.businesses if unit.owner==b.id]
    assert len(units)==1 and units[0].industry==b.industry and units[0].status=='developing',[q['detail'] for q in e.world.systems.get('management_requests',[])]
    assert e.world.systems['operating_locations'][units[0].id]['company']==b.id
    assert l.director(units[0].id,False)[0] is l.director(b.id)[0]
    e.validate()


def test_managing_director_keeps_daily_collection_and_writeoff_limits(game):
    e,l,b,manager,_=setup(game)
    l.action('director_assign',dict(business_id=b.id,employment_id=manager.id),'promote')
    RoutineManagement(e).action(dict(business_id=b.id,collection_limit=10000,write_off_limit=10000))
    r=invoice(e,b,amount=2000000);r['recovery_attempts']=['reminder','plan']
    RoutineManagement(e).tick()
    assert not r.get('recovery')
    assert 'collection limit' in e.world.systems['management_requests'][-1]['detail']
    assert not l.perform(b,'loss','write_off_invoice',dict(entity=b.id,invoice_id=r['id']),r['amount'],True,'Unrecovered balance')
    assert r in b.receivables and 'write-off limit' in e.world.systems['management_requests'][-1]['detail']


def test_default_director_respects_business_cash_reserve_for_location_funding(game):
    e,l,b,manager,_=setup(game);profitable(e,b)
    e.post('personal','test-capital','Owner test capital',{'asset:cash':100000000,'equity:capital':-100000000})
    e.action('fund_business',dict(business_id=b.id,amount=100000000),'growth-capital')
    l.action('director_assign',dict(business_id=b.id,employment_id=manager.id),'promote')
    Management(e).action(dict(target=b.id,cash_reserve=e.world.cash(b.id)-10000))
    b.capacity_percent=160
    from economic_simulation.operating_automation import OperatingAutomation
    OperatingAutomation(e).tick()
    assert not any(unit.owner==b.id for unit in e.world.businesses)
    assert 'reserve requires' in e.world.systems['management_requests'][-1]['detail']
    e.validate()


def test_restore_defaults_preserves_custom_authority_and_existing_commitments(game):
    e,l,b,manager,_=setup(game);key=contract(e,b,contracts='prohibit')
    b.authority.update(enabled=False,purchasing_limit=0,routine_management={'collections':False},spent=50000)
    Management(e).action(dict(target=b.id,growth='off',cash_reserve=123400))
    before=copy.deepcopy(e.world.accounts);saved=copy.deepcopy(e.world.systems['authority_contracts'][key])
    e.action('leadership_defaults',dict(business_id=b.id),'reset')
    assert limits(b)['enabled'] and routine_policy(e.world,b)['collections']
    assert b.authority['spent']==50000 and policy(b,e.world)['cash_reserve']==123400 and policy(b,e.world)['growth']=='off'
    assert e.world.accounts==before and e.world.systems['authority_contracts'][key]==saved


def test_role_and_collection_ui_are_read_only_and_promotion_preview_has_no_effect(game):
    e,l,b,manager,_=setup(game);invoice(e,b);game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html=client.get('/?page=business&business_id='+b.id).text
        assert 'Promote manager to managing director' in html and 'Use default manager policies' in html
        html=client.get('/?page=operations_center&scope='+b.id).text
        assert 'Assigned to the manager' in html
        preview=client.post('/api/preview',json=dict(action='director_assign',args=dict(business_id=b.id,employment_id=manager.id),revision=game.world.revision,command_id='preview-managing-director'))
        assert preview.status_code==200 and 'growth authority' in preview.text and 'raise' in preview.text
    assert game.world.to_dict()==before


def test_director_growth_and_collection_replay_and_save_load_reconcile(game):
    e,l,b,manager,_=setup(game);profitable(e,b)
    l.action('director_assign',dict(business_id=b.id,employment_id=manager.id),'director');invoice(e,b)
    game.store.commit(e,game.world.revision);game.world=e.world
    batch=Engine(copy.deepcopy(game.world))
    for _ in range(12):batch.advance_day()
    step(game,6);game.world=game.store.load();step(game,6)
    batch.world.revision=game.world.revision
    assert batch.world.to_dict()==game.world.to_dict()
    game.store.audit(game.world)
