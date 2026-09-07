import copy
import pytest
from test_game import game,act,step
from test_leadership import setup
from test_authority import contract
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.leadership import Leadership
from economic_simulation.director_scope import assigned,workload,reconcile
from economic_simulation.authority import Authority
from economic_simulation.leadership_history import duties
from economic_simulation.decision_inbox import items
from economic_simulation.organization import employee_tree
from economic_simulation.skip_controls import should_pause


def move(e,child,parent):
    e.action('transfer_business',dict(business_id=child,new_owner=parent),'move-'+child+'-'+parent)


def appoint(e,emp,bid,limit=1000000):
    e.action('director_assign',dict(employment_id=emp.id,business_id=bid,limit=limit),'appoint-'+bid+emp.id)


def branch(game):
    e,l,b,emp,child_id=setup(game,True)
    move(e,child_id,b.id)
    child=l.rules.company(child_id)
    manager=next(p for p in l.rules.staff(child_id) if l.rules.position(p.position_id).role=='manager')
    return e,l,b,emp,child,manager


def additional(e,l,parent):
    # Real acquisition with explicitly journaled test capital; no fabricated ownership.
    e.post('personal','test-capital-'+str(len(e.world.events)),
           'Test capital',{'asset:cash':100000000,'equity:capital':-100000000})
    b=next(b for b in e.world.businesses if b.owner is None)
    e.action('acquire_business',dict(business_id=b.id,entity='personal'),'acquire-'+b.id)
    for _ in range(3):e.advance_day()
    if b.owner!=parent:move(e,b.id,parent)
    return b


def test_parent_default_shares_identity_budget_time_and_keeps_local_manager(game):
    e,l,parent,emp,child,manager=branch(game)
    identities=[(p.id,p.employer,p.position_id) for p in e.world.employments]
    salary=emp.salary
    appoint(e,emp,parent.id)
    record=l.director(parent.id)[0]
    assert record is l.director(child.id)[0] and record['business_ids']==[parent.id]
    assert set(assigned(e.world,record))=={parent.id,child.id}
    assert l.actor(child,'restock')==(None,manager)
    assert l.actor(child,'upgrade_business')==(record,emp)
    assert workload(e.world,emp)['minutes']==120
    assert emp.salary==salary*120//100
    assert identities==[(p.id,p.employer,p.position_id) for p in e.world.employments]
    assert child.id in {b['id'] for b in duties(e.world,emp)[0]['businesses']}
    e.validate()


def test_nearest_explicit_director_overrides_branch_without_ancestor_absence_bypass(game):
    e,l,parent,emp,child,manager=branch(game)
    grandchild=additional(e,l,child.id)
    appoint(e,emp,parent.id)
    assert l.director(grandchild.id)[1] is emp
    appoint(e,manager,child.id)
    assert l.director(grandchild.id)[1] is manager
    assert assigned(e.world,l.director(parent.id)[0])==[parent.id]
    manager.leave_until=e.world.date
    assert l.director(grandchild.id)==(None,None)
    assert l.director(grandchild.id,False)[1] is manager
    manager.leave_until=None
    e.action('director_remove',dict(business_id=child.id),'remove-override')
    assert l.director(child.id)[1] is emp and l.director(grandchild.id)[1] is emp
    assert manager.employer==child.id
    e.validate()


def test_opt_out_stops_branch_but_explicit_appointment_still_covers_descendants(game):
    e,l,parent,emp,child,manager=branch(game)
    grandchild=additional(e,l,child.id)
    appoint(e,emp,parent.id)
    e.action('director_inheritance',dict(business_id=child.id,enabled=False),'stop-inheritance')
    assert l.director(child.id)==l.director(grandchild.id)==(None,None)
    assert l.director(parent.id)[1] is emp
    appoint(e,manager,child.id)
    assert l.director(grandchild.id)[1] is manager
    e.action('director_remove',dict(business_id=child.id),'remove-local')
    e.action('director_inheritance',dict(business_id=child.id,enabled=True),'restore-inheritance')
    assert l.director(grandchild.id)[1] is emp


def test_inherited_spending_uses_one_daily_and_monthly_budget(game):
    e,l,parent,emp,child,manager=branch(game)
    appoint(e,emp,parent.id,20000)
    manager.leave_until=e.world.date
    record=l.director(parent.id)[0]
    key=contract(e,parent,target='director:'+emp.id,period_limit=20000)
    amount=12000;units=amount//parent.unit_cost;amount=units*parent.unit_cost
    assert amount>10000
    assert l.perform(parent,'parent-stock','restock',dict(business_id=parent.id,units=units),amount,True,'Parent purchase')
    units=12000//child.unit_cost;child_amount=units*child.unit_cost
    assert child_amount>10000
    assert not l.perform(child,'child-stock','restock',dict(business_id=child.id,units=units),child_amount,True,'Child purchase')
    assert record['spent']==amount and Authority(e).spent(key)==amount
    e.world.date='2026-01-13';manager.leave_until=e.world.date
    assert not l.perform(child,'next-day','restock',dict(business_id=child.id,units=units),child_amount,True,'Cumulative child purchase')
    assert 'Cumulative' in e.world.systems['management_requests'][-1]['detail']
    assert Authority(e).spent(key)==amount
    e.validate()


def test_saved_contract_scope_requires_explicit_expansion_and_old_director_loses_control(game):
    e,l,parent,emp,child_id=setup(game,True)
    child=l.rules.company(child_id)
    appoint(e,emp,parent.id)
    record=l.director(parent.id)[0]
    key=contract(e,parent,target='director:'+emp.id)
    old=copy.deepcopy(e.world.systems['authority_contracts'][key])
    move(e,child.id,parent.id)
    assert e.world.systems['authority_contracts'][key]==old
    assert 'scope' in Authority(e).check(child,record,'restock',{},100)
    contract(e,parent,target=key,transaction_limit=9000000)
    assert e.world.systems['authority_contracts'][key]['businesses']==[parent.id]
    contract(e,parent,target=key,businesses=[parent.id,child.id],regions=[parent.region,child.region])
    assert Authority(e).check(child,record,'restock',{},100) is None
    move(e,child.id,'personal')
    assert l.director(child.id)==(None,None)
    assert 'no longer oversees' in Authority(e).check(child,record,'restock',{},100)


def test_inherited_director_restrictions_not_bypassed_by_uncontracted_local_manager(game):
    e,l,parent,emp,child,manager=branch(game)
    appoint(e,emp,parent.id)
    contract(e,parent,target='director:'+emp.id,purchasing='prohibit')
    child.authority.update(enabled=True,purchasing_limit=1000000)
    assert l.actor(child,'restock')[1] is manager
    assert 'Policy prohibits' in Authority(e).check(child,None,'restock',{},100)
    with pytest.raises(RuleError,match='Subordinate permissions'):
        contract(e,child,parent='director:'+emp.id,purchasing='allow')


def test_ownership_changes_history_and_pay_review_without_duplicating_employment(game):
    e,l,parent,emp,child_id=setup(game,True)
    appoint(e,emp,parent.id)
    salary=emp.salary;count=len(e.world.employments)
    move(e,child_id,parent.id)
    history=l.rules.person(emp.person_id).history
    assert child_id in {b['id'] for b in duties(e.world,emp)[0]['businesses']}
    assert 'Subsidiary ownership changed' in history[-1]['event']
    assert emp.salary==salary and emp.employer==parent.id
    l.start_day()
    request=next(r for r in e.world.systems['management_requests'] if r['key']=='leadership-pay:'+emp.id)
    assert request['status']=='open' and request['cost']>0
    assert len(e.world.employments)==count and emp.salary==salary
    first=copy.deepcopy(history);reconcile(e)
    assert history==first
    move(e,child_id,'personal')
    l.start_day()
    assert request['status']=='resolved'


def test_duplicate_explicit_root_does_not_double_count_inherited_scope_or_pay(game):
    e,l,parent,emp,child,_=branch(game)
    appoint(e,emp,parent.id)
    salary=emp.salary
    appoint(e,emp,child.id)
    assert emp.salary==salary and workload(e.world,emp)['count']==2
    assert l.reserved_minutes(emp)==120


def test_overloaded_inheritance_stops_long_skip_and_links_to_resolution(game):
    e,l,parent,emp,child,_=branch(game)
    appoint(e,emp,parent.id)
    emp.weekly_hours=20
    assert workload(e.world,emp)['overloaded']
    assert l.director(child.id)==(None,None) and l.director(child.id,False)[1] is emp
    inbox=next(i for i in items(e.world) if i['kind']=='director_capacity')
    assert '#business-policies' in inbox['url']
    e.world.systems['settings'].update(financial_pause_threshold=1000000000,pause_routine=False)
    e.pause_reasons=[];Authority(e).guardrails()
    assert should_pause(e) and e.pause_reason_text=='Director workload exceeded'
    game.store.commit(e,game.world.revision);game.world=e.world
    act(game,'advance',period='week');game.worker.join(timeout=10)
    assert not game.worker.is_alive() and game.progress['completed']==0
    assert 'Director workload exceeded' in game.progress['message']
    game.store.audit(game.world)


def test_appointment_rejects_insufficient_hours_for_inherited_businesses_atomically(game):
    e,l,parent,emp,child,_=branch(game)
    emp.weekly_hours=20
    before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError,match='including inherited'):
        appoint(e,emp,parent.id)
    assert e.world.to_dict()==before


def test_inherited_ui_is_read_only_and_policy_persists(game):
    e,l,parent,emp,child,_=branch(game)
    appoint(e,emp,parent.id)
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        page=client.get('/?page=business&business_id='+child.id)
        assert page.status_code==200 and 'Inherited from' in page.text
        assert 'data-action="director_inheritance"' in page.text
        assert 'data-action="director_remove"' not in page.text
        assert 'Director workload: 2 businesses' in page.text
        management=client.get('/?page=management')
        assert management.status_code==200 and 'inherited from '+parent.name in management.text
        org=employee_tree(game.world,child.id)
        assert 'Director inherited from '+parent.name in org['root']['meta']
        assert game.world.to_dict()==before
        payload=dict(action='director_inheritance',args=dict(business_id=child.id,enabled=False),revision=game.world.revision,command_id='inherit-ui')
        assert client.post('/api/preview',json=payload).status_code==200
        assert game.world.to_dict()==before
        assert client.post('/api/command',json=payload).status_code==200
    restored=game.store.load()
    assert Leadership(Engine(restored)).director(child.id,False)==(None,None)
    game.store.audit(game.world)


def test_inheritance_replay_save_load_and_financial_reconciliation(game):
    e,l,parent,emp,child,_=branch(game)
    appoint(e,emp,parent.id)
    game.store.commit(e,game.world.revision);game.world=e.world
    direct=copy.deepcopy(game.world)
    for _ in range(4):
        next_day=Engine(copy.deepcopy(direct));next_day.advance_day();next_day.validate()
        next_day.world.revision+=1;direct=next_day.world
    step(game,2);game.world=game.store.load();step(game,2)
    assert direct.to_dict()==game.world.to_dict()
    game.store.audit(game.world)


def test_reorganization_switches_to_new_parent_director_immediately(game):
    e,l,parent,emp,child,_=branch(game)
    other=additional(e,l,'personal')
    other_emp=next(p for p in l.rules.staff(other.id) if l.rules.position(p.position_id).role=='manager')
    appoint(e,emp,parent.id);appoint(e,other_emp,other.id)
    old_record=l.director(child.id,False)[0]
    cash={bid:e.world.cash(bid) for bid in e.world.accounts}
    move(e,child.id,other.id)
    assert l.director(child.id,False)[1] is other_emp
    assert assigned(e.world,old_record)==[parent.id]
    assert cash=={bid:e.world.cash(bid) for bid in e.world.accounts}
    assert emp.employer==parent.id and other_emp.employer==other.id
    assert child.name in l.rules.person(other_emp.person_id).history[-1]['event']
    e.validate()


def test_legacy_roots_inherit_without_read_migration_and_log_once_on_day_step(game):
    e,l,parent,emp,child,_=branch(game)
    e.world.systems['directors']=[dict(employment_id=emp.id,business_ids=[parent.id],active=True,limit=100000,day=e.world.date,spent=0)]
    before=copy.deepcopy(e.world.to_dict())
    assert l.view(child)['inherited_from']==parent.name
    assert e.world.to_dict()==before
    history=l.rules.person(emp.person_id).history
    count=len(history);reconcile(e)
    assert len(history)==count+1 and child.name in history[-1]['event']
    reconcile(e);assert len(history)==count+1
    emp.status='resigned'
    assert l.director(child.id,False)==(None,None)
