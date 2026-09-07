import copy,json
from datetime import date
import pytest
from test_game import game
from test_leadership import setup
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.application import Game
from economic_simulation.leadership import Leadership,review
from economic_simulation.leadership_pay import quote
from economic_simulation.authority import cash_forecast
from economic_simulation.executives import Executives


def appoint(engine,emp,bid,limit=100000):
    return engine.action('director_assign',dict(employment_id=emp.id,business_id=bid,limit=limit),'appoint-'+bid+str(limit))


def test_director_raise_changes_future_payroll_not_existing_cash_or_wages(game):
    e,l,b,emp,_=setup(game)
    before=copy.deepcopy(e.world.accounts);due=review(e.world,emp)['due'];old=emp.salary
    forecast=cash_forecast(e.world,b.id,30)['obligations']
    message=appoint(e,emp,b.id)
    assert emp.salary==391000 and old==340000
    assert e.world.accounts==before and review(e.world,emp)['due']==due
    assert cash_forecast(e.world,b.id,30)['obligations']>forecast
    assert '+$510/month' in message and '+$6,120/year' in message
    e.validate()


def test_scope_increase_repeat_limit_edit_and_reappointment(game):
    e,l,b,emp,other=setup(game,True)
    appoint(e,emp,b.id);first=emp.salary
    appoint(e,emp,b.id,200000);assert emp.salary==first
    appoint(e,emp,other);assert emp.salary==410550
    e.action('director_remove',dict(business_id=other),'remove-one')
    appoint(e,emp,other,300000);assert emp.salary==410550
    for bid in (b.id,other):e.action('director_remove',dict(business_id=bid),'remove-'+bid)
    appoint(e,emp,b.id,400000);assert emp.salary==410550
    e.validate()


def test_cross_company_director_uses_original_employer_and_one_employee(game):
    e,l,b,emp,other=setup(game,True)
    original_ids=[x.id for x in e.world.employments];balances=copy.deepcopy(e.world.accounts)
    appoint(e,emp,other)
    assert emp.employer==b.id and emp.salary==391000
    assert e.world.accounts==balances and [x.id for x in e.world.employments]==original_ids
    control=Engine(copy.deepcopy(e.world));control_emp=next(x for x in control.world.employments if x.id==emp.id);control_emp.salary=340000
    e.advance_day();control.advance_day()
    assert e.world.accounts[b.id]['liability:payroll']<control.world.accounts[b.id]['liability:payroll']
    assert e.world.accounts[other]['liability:payroll']==control.world.accounts[other]['liability:payroll']


def test_hourly_appointment_updates_rate_and_monthly_equivalent(game):
    e,l,b,emp,_=setup(game)
    emp.compensation=dict(pay_basis='hourly',hourly_rate=2000,shift_premium=1234)
    emp.salary=2000*emp.weekly_hours*52//12
    appoint(e,emp,b.id)
    assert emp.compensation['hourly_rate']==2300
    assert emp.salary==2300*emp.weekly_hours*52//12
    assert emp.compensation['shift_premium']==1234


def test_rejected_appointment_does_not_change_pay(game):
    e,l,b,emp,_=setup(game);emp.weekly_hours=10
    before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError,match='scheduled hour'):appoint(e,emp,b.id)
    assert e.world.to_dict()==before


def test_existing_director_gets_one_inbox_request_and_owner_approval(game):
    e,l,b,emp,_=setup(game)
    e.world.systems['directors']=[dict(employment_id=emp.id,business_ids=[b.id],limit=100000,active=True,day=e.world.date,spent=0)]
    before=emp.salary
    l.start_day();l.start_day()
    requests=[r for r in e.world.systems['management_requests'] if r['action']=='leadership_raise' and r['status']=='open']
    assert len(requests)==1 and emp.salary==before and e.pause_reasons
    e.action('management_approve',dict(request_id=requests[0]['id']),'approve-pay')
    assert emp.salary==391000 and requests[0]['status']=='resolved'
    l.start_day();assert not any(r['action']=='leadership_raise' and r['status']=='open' for r in e.world.systems['management_requests'])
    e.validate()


def test_removed_legacy_duties_resolve_unneeded_pay_request(game):
    e,l,b,emp,_=setup(game)
    e.world.systems['directors']=[dict(employment_id=emp.id,business_ids=[b.id],limit=100000,active=True,day=e.world.date,spent=0)]
    l.start_day();old=emp.salary
    e.action('director_remove',dict(business_id=b.id),'remove-legacy-director')
    assert emp.salary==old
    assert all(r['status']=='resolved' for r in e.world.systems['management_requests'] if r['action']=='leadership_raise')


def test_home_office_director_and_vp_credit_prior_responsibility(game):
    e,l,b,emp,_=setup(game)
    executives=Executives(e)
    args=dict(employment_id=emp.id,business_ids=b.id,role='home_office_director')
    executives.action(args);assert emp.salary==391000
    executives.action(args);assert emp.salary==391000
    executives.action(dict(args,role='division_vp'));assert emp.salary==430100
    e.validate()


def test_preview_shows_pay_before_commit_and_state_roundtrips(game):
    e,l,b,emp,_=setup(game);game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        payload=dict(action='director_assign',args=dict(employment_id=emp.id,business_id=b.id,limit_dollars='1000'),revision=game.world.revision,command_id='review-director-pay')
        result=client.post('/api/preview',json=payload)
        assert result.status_code==200 and '$3,910/month' in result.json()['message']
        assert 'monthly employer payroll' in result.json()['description']
        assert game.world.to_dict()==before
        html=client.get('/?page=business&business_id='+b.id).text
        assert '$3,400 → $3,910/month' in html and '15% on first director appointment' in html
        assert client.post('/api/command',json=payload).status_code==200
    loaded=Game(game.store.path)
    try:assert loaded.world.to_dict()==json.loads(json.dumps(game.world.to_dict()))
    finally:loaded.close()
    game.store.audit(game.world)
