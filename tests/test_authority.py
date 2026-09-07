import copy
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_leadership import setup
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.authority import Authority,cash_forecast
from economic_simulation.domain import Engine,RuleError
from economic_simulation.leadership import Leadership
from economic_simulation.skip_controls import should_pause


def contract(engine,b,**kwargs):
    args=dict(target='manager:'+b.id,transaction_limit=10000000,period_limit=10000000,
              horizon=1,headcount_limit=100,salary_limit=10000000)
    args.update(kwargs)
    Authority(engine).set_contract(args)
    b.authority.update(enabled=True,purchasing_limit=10000000)
    return args['target']


def purchase(leader,b,units=10,key='order'):
    return leader.perform(b,key,'restock',dict(business_id=b.id,units=units),units*b.unit_cost,True,'Test order')


def test_manager_monthly_limit_survives_days_and_contract_edits(game):
    e,l,b,_,_=setup(game)
    key=contract(e,b,period_limit=b.unit_cost*15)
    assert purchase(l,b)
    e.world.date='2026-01-13'
    assert not purchase(l,b,key='second')
    contract(e,b,period_limit=b.unit_cost*15)
    assert not purchase(l,b,key='renamed-order')
    assert Authority(e).spent(key)==10*b.unit_cost
    e.world.date='2026-02-02'
    assert purchase(l,b,key='next-month')
    e.validate()


def test_cash_forecast_does_not_spend_or_advance_rng_and_includes_incoming_staff(game):
    e,l,b,_,_=setup(game)
    before=copy.deepcopy(e.world.to_dict());base=cash_forecast(e.world,b.id)
    assert e.world.to_dict()==before
    staff=l.rules.staff(b.id)[-1]
    staff.status='joining';staff.start_date=(date.fromisoformat(e.world.date)+timedelta(days=10)).isoformat()
    later=cash_forecast(e.world,b.id)
    assert 0<later['obligations']<base['obligations']
    staff.start_date=(date.fromisoformat(e.world.date)+timedelta(days=40)).isoformat()
    assert cash_forecast(e.world,b.id)['obligations']<later['obligations']


def test_forecast_protects_deposits_and_bills_without_treating_receivables_as_cash(game):
    e,l,b,_,_=setup(game)
    base=cash_forecast(e.world,b.id)
    e.post(b.id,'bill','Test invoice',{'expense:test':50000,'liability:payable':-50000})
    e.post(b.id,'deposit','Refundable deposit',{'asset:cash':80000,'liability:deposit:test':-80000})
    e.post(b.id,'receivable','Earned unpaid sale',{'asset:receivable:test':90000,'income:test':-90000})
    result=cash_forecast(e.world,b.id)
    assert result['available']==base['available']-50000
    assert result['obligations']==base['obligations']+130000
    assert result['receivables']==base['receivables']+90000


def test_reserve_applies_to_full_preview_and_rejects_without_mutation(game):
    e,l,b,_,_=setup(game)
    available=cash_forecast(e.world,b.id,1)['available']
    contract(e,b,cash_reserve=available)
    balances=copy.deepcopy(e.world.accounts);stock=b.inventory_units
    assert not purchase(l,b)
    assert e.world.accounts==balances and b.inventory_units==stock
    assert not e.world.systems.get('authority_audit')
    assert 'Known obligations' in e.world.systems['management_requests'][-1]['detail']


def test_director_and_children_share_one_period_budget(game):
    e,l,b,manager,second=setup(game,True)
    for bid in (b.id,second):l.action('director_assign',dict(employment_id=manager.id,business_id=bid,limit=10000000),'appoint-'+bid)
    parent='director:'+manager.id
    contract(e,b,target=parent,period_limit=20000)
    child=contract(e,b,parent=parent,period_limit=20000)
    # A director being away lets the available local manager act under that grant.
    record=l.director(b.id)[0]
    authority=Authority(e)
    before_parent=authority.spent(parent);before_child=authority.spent(child)
    authority.record(b,None,manager,'restock',12000,12000,'Child purchase')
    assert authority.spent(parent)-before_parent==authority.spent(child)-before_child==12000
    other=l.rules.company(second)
    refusal=authority.check(other,record,'restock',{'units':1},9000)
    assert 'Cumulative' in refusal
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id


def test_parent_restrictions_cannot_be_overridden_and_tighten_live(game):
    e,l,b,manager,_=setup(game)
    l.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=10000000),'director')
    parent=contract(e,b,target='director:'+manager.id,period_limit=20000)
    with pytest.raises(RuleError,match='Subordinate limits'):
        contract(e,b,parent=parent,period_limit=20001)
    child=contract(e,b,parent=parent,period_limit=20000)
    contract(e,b,target=parent,period_limit=10000,purchasing='prohibit')
    assert 'prohibits' in Authority(e).check(b,None,'restock',{},100)
    with pytest.raises(RuleError,match='cycle'):
        contract(e,b,target=parent,parent=child,period_limit=10000,purchasing='prohibit')


@pytest.mark.parametrize('field,value,reason', [('regions','Elsewhere','geographic'),('purchasing','approval','approval'),('purchasing','prohibit','prohibits')])
def test_scope_and_action_rules(game,field,value,reason):
    e,l,b,_,_=setup(game)
    contract(e,b,**{field:value})
    assert not purchase(l,b)
    assert reason in e.world.systems['management_requests'][-1]['detail']


def test_stock_automation_uses_same_monthly_and_reserve_gate(game):
    e,l,b,_,_=setup(game)
    key=contract(e,b,period_limit=15*b.unit_cost)
    assert l.stock_limit(b,10)==10
    assert l.stock_limit(b,10)==0
    assert Authority(e).spent(key)==10*b.unit_cost


def test_understated_director_cost_cannot_bypass_limit(game):
    e,l,b,manager,_=setup(game)
    l.action('director_assign',dict(employment_id=manager.id,business_id=b.id,limit=1),'appoint')
    assert not l.perform(b,'underquote','restock',dict(business_id=b.id,units=10),1,True,'Incorrect estimate')
    assert not e.world.systems.get('authority_audit')


def test_objective_changes_decision_and_headcount_includes_new_hire(game):
    e,l,b,_,_=setup(game)
    contract(e,b,objective='preserve_cash')
    assert 'Cash-preservation' in Authority(e).check(b,None,'hire',{'amount':100},100)
    contract(e,b,objective='growth',headcount_limit=len(l.rules.staff(b.id))-1)
    assert 'headcount' in Authority(e).check(b,None,'hire',{'amount':100},100)
    contract(e,b,objective='growth',headcount_limit=100)
    assert Authority(e).check(b,None,'hire',{'amount':100},100) is None


def test_required_approval_ignores_threshold_and_repeated_request_stops(game):
    e,l,b,_,_=setup(game)
    e.world.systems['settings'].update(financial_pause_threshold=1000000000,pause_routine=False)
    for _ in range(2):
        e.pause_reasons=[]
        l.request(b,'approval','restock',dict(business_id=b.id,units=1),1,'Needs authorization')
        assert should_pause(e)
    assert len(e.world.systems['management_requests'])==1
    request=e.world.systems['management_requests'][0]
    assert request['risk'] and request['recommendation'] and request['due']


def test_ui_persistence_and_existing_request_stops_long_skip_before_next_day(game):
    bid=acquire(game)
    with client_for(game) as client:
        response=client.post('/api/command',headers={'Origin':'http://testserver','X-Game-Token':'test-token'},json=dict(action='authority_contract',args=dict(target='manager:'+bid,transaction_limit_dollars='1500',period_limit_dollars='3000'),revision=game.world.revision,command_id='contract-ui'))
        assert response.status_code==200
        page=client.get('/?page=management')
        assert page.status_code==200 and 'Cash after known commitments' in page.text and 'Contract active' in page.text
    assert game.store.load().systems['authority_contracts']==game.world.systems['authority_contracts']
    e=Engine(copy.deepcopy(game.world));b=next(b for b in e.world.businesses if b.id==bid)
    Leadership(e).request(b,'need-approval','restock',dict(business_id=bid,units=1),b.unit_cost,'Review spending')
    game.store.commit(e,game.world.revision);game.world=e.world
    before=game.world.date
    act(game,'advance',period='week');game.worker.join(timeout=10)
    assert game.world.date==before and game.progress['completed']==0
    assert 'Owner approval needed' in game.progress['message']
    game.store.audit(game.world)


def test_guardrail_cannot_be_suppressed(game):
    e,l,b,_,_=setup(game)
    contract(e,b,cash_reserve=e.world.cash(b.id))
    e.world.systems['settings']['financial_pause_threshold']=1000000000
    e.pause_reasons=[];Authority(e).guardrails()
    assert should_pause(e) and e.pause_reason_text=='Delegated cash reserve breached'


def test_project_acceptance_requires_authority_before_commitment(game):
    bid=acquire(game,2)
    e=Engine(copy.deepcopy(game.world));e.world.date='2026-01-12'
    l=Leadership(e);b=l.rules.company(bid)
    b.project_active=False;b.project_earned=0;b.project_progress=0
    contract(e,b,contracts='approval')
    before=(b.project_number,b.contract_minutes,b.contract_fee)
    assert not l.accept_project(b)
    assert not b.project_active and before==(b.project_number,b.contract_minutes,b.contract_fee)
    assert e.world.systems['management_requests'][-1]['action']=='new_project'
    contract(e,b,contracts='allow',project_limit=0)
    assert not l.accept_project(b) and not b.project_active
    assert 'project limit' in e.world.systems['management_requests'][-1]['detail']
    contract(e,b,contracts='allow',project_limit=10000000)
    assert l.accept_project(b) and b.project_active
    assert e.world.systems['authority_audit'][-1]['action']=='new_project'


def test_authority_replay_and_save_load_keep_state_and_journal_identical(game):
    e,l,b,_,_=setup(game)
    contract(e,b,period_limit=100000)
    game.store.commit(e,game.world.revision);game.world=e.world
    baseline=copy.deepcopy(game.world)
    direct=baseline
    for _ in range(4):
        next_day=Engine(copy.deepcopy(direct));next_day.advance_day();next_day.validate()
        # Store commits advance only the persistence revision, not game outcomes.
        next_day.world.revision+=1;direct=next_day.world
    step(game,2);game.world=game.store.load();step(game,2)
    assert game.world.to_dict()==direct.to_dict()
    game.store.audit(game.world)


def test_deferred_request_never_executes_or_reappears_during_cooldown(game):
    e,l,b,_,_=setup(game)
    contract(e,b,purchasing='approval')
    assert not purchase(l,b,key='stock')
    request=e.world.systems['management_requests'][-1]
    l.action('management_defer',{'request_id':request['id']},'defer')
    contract(e,b,purchasing='allow')
    before=copy.deepcopy(e.world.accounts)
    assert not purchase(l,b,key='stock') and l.stock_limit(b,10)==0
    assert e.world.accounts==before and request['status']=='deferred'
    e.world.date='2026-01-20'
    assert purchase(l,b,key='stock')


def test_debt_principal_is_a_cash_commitment_not_an_operating_expense(game):
    e,l,b,_,_=setup(game)
    baseline=cash_forecast(e.world,b.id,60)
    profit_before=-sum(v for k,v in e.world.accounts[b.id].items() if k.startswith(('income:','expense:')))
    e.action('borrow',dict(entity=b.id,amount=100000,months=12),'borrow-for-test')
    after=cash_forecast(e.world,b.id,60)
    payments=[r for r in after['rows'] if r['kind']=='debt']
    assert len(payments)==2 and sum(r['amount'] for r in payments)>100000//6
    assert after['cash']==baseline['cash']+100000
    assert profit_before==-sum(v for k,v in e.world.accounts[b.id].items() if k.startswith(('income:','expense:')))
    e.validate()


def test_shared_service_forecast_allocates_cash_without_duplicating_employees(game):
    from economic_simulation.shared_services import SharedServices
    e,l,b,manager,second=setup(game,True)
    before_source=cash_forecast(e.world,b.id,7)
    before_target=cash_forecast(e.world,second,7)
    count=len(e.world.employments)
    services=SharedServices(e)
    services.action('service_agreement',dict(source=b.id,target=second,markup=20),'agreement')
    services.action('assign_staff',dict(employment_id=manager.id,target=second,role='manager',start_minute=480,minutes=120),'assignment')
    after_source=cash_forecast(e.world,b.id,7)
    after_target=cash_forecast(e.world,second,7)
    charges=[r for r in after_target['rows'] if r['detail'].startswith('Assigned shared-service')]
    assert len(charges)==1 and charges[0]['amount']>0
    assert after_source==before_source
    assert after_target['obligations']==before_target['obligations']+charges[0]['amount']
    assert len(e.world.employments)==count and manager.employer==b.id
    e.validate()


def test_absent_director_does_not_allow_uncontracted_manager_to_bypass_controls(game):
    e,l,b,manager,_=setup(game)
    director=next(emp for emp in l.rules.staff(b.id) if emp.id!=manager.id)
    l.action('director_assign',dict(employment_id=director.id,business_id=b.id,limit=10000000),'appoint')
    contract(e,b,target='director:'+director.id,purchasing='approval')
    director.leave_until=e.world.date
    assert l.actor(b)[1].id==manager.id
    assert not purchase(l,b)
    assert 'approval' in e.world.systems['management_requests'][-1]['detail']
