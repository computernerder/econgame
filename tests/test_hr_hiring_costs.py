import copy
from datetime import date, timedelta

import pytest

from test_game import game, act
from test_leadership import setup
from test_specialists import add_specialist
from test_campaign_product import client_for
from economic_simulation.domain import Engine, RuleError
from economic_simulation.specialists import apply, available, recruitment_quote
from economic_simulation.staffing import hiring_view
from economic_simulation.shared_services import SharedServices


def commit(game, engine):
    engine.validate()
    game.store.commit(engine, game.world.revision)
    game.world = engine.world


def offer(world, bid):
    view = hiring_view(world, bid, 'cashier')
    return dict(business_id=bid, role='cashier', person_id=view['eligible'][0]['id'],
                amount=view['salary'], weekly_hours=view['hours'])


@pytest.mark.parametrize('minutes,fee,used', [(0,30000,0),(59,30000,0),(60,0,60),(120,0,60)])
def test_hiring_uses_exact_capacity_and_only_real_outside_expense(game, minutes, fee, used):
    e, leader, b, _, _ = setup(game)
    apply(leader.rules, b, {'hr':[minutes]})
    cash = e.world.cash(b.id)
    payroll = e.world.accounts[b.id].get('liability:payroll',0)
    start = len(e.postings)
    result = e.action('hire_for_role', offer(e.world,b.id), 'cost-boundary')
    assert e.world.cash(b.id) == cash-fee
    assert available(e.world,b.id,'hr') == minutes-used
    assert e.world.accounts[b.id].get('liability:payroll',0) == payroll
    postings = e.postings[start:]
    assert bool(postings) == bool(fee)
    assert ('No outside recruitment fee' in result) == bool(used)
    assert ('Outside hiring support costs $300' in result) == bool(fee)
    person=leader.rules.person(e.world.employments[-1].person_id)
    assert ('No outside recruitment fee' in person.history[-1]['event']) == bool(used)
    e.validate()


def test_hr_hire_needs_salary_reserve_but_no_extra_recruiter_cash(game):
    e, leader, b, _, _ = setup(game)
    apply(leader.rules,b,{'hr':[60]})
    args=offer(e.world,b.id)
    excess=e.world.cash(b.id)-args['amount']
    e.post(b.id,'fixture-expense','Testing exact salary reserve',{'asset:cash':-excess,'expense:testing':excess})
    e.action('hire_for_role',args,'salary-reserve')
    assert e.world.cash(b.id)==args['amount']
    assert available(e.world,b.id,'hr')==0
    # Without the completed HR work, the same cash cannot fund the outside fee.
    with pytest.raises(RuleError,match='month of this salary'):
        e.action('hire_for_role',offer(e.world,b.id),'outside-reserve')


def test_hr_employee_must_deliver_work_and_absence_creates_no_capacity(game):
    e, leader, b, _, _ = setup(game)
    emp, _=add_specialist(e,b.id,'hr')
    assert recruitment_quote(e.world,b.id)['fee']==30000
    emp.leave_until='2026-02-01'
    leader.rules.operate(b,date.fromisoformat(e.world.date))
    assert available(e.world,b.id,'hr')==0
    e.world.date='2026-01-13';emp.leave_until=None
    before=e.world.accounts[b.id].get('liability:payroll',0)
    leader.rules.operate(b,date.fromisoformat(e.world.date))
    assert recruitment_quote(e.world,b.id)['fee']==0
    assert e.world.accounts[b.id]['liability:payroll']<before
    e.validate()


def test_shared_hr_work_is_allocated_and_consumed_only_at_recipient(game):
    e, leader, b, _, other = setup(game,True)
    emp,_=add_specialist(e,b.id,'hr')
    services=SharedServices(e)
    services.action('service_agreement',dict(source=b.id,target=other,staff_access=True),'hr-agreement')
    services.action('assign_staff',dict(employment_id=emp.id,target=other,role='hr',start_minute=480,minutes=240),'hr-assignment')
    today=date.fromisoformat(e.world.date)
    leader.rules.operate(b,today);leader.rules.operate(leader.rules.company(other),today);services.settle(today)
    own=available(e.world,b.id,'hr');shared=available(e.world,other,'hr')
    assert 60<=shared and own+shared<=480*115//100
    assert e.world.systems['assignments'][-1]['last_cost']>0
    # The other business is a restaurant; use one of its valid roles.
    guide=hiring_view(e.world,other,'server')
    cash=e.world.cash(other)
    e.action('hire_for_role',dict(business_id=other,role='server',person_id=guide['eligible'][0]['id'],amount=guide['salary'],weekly_hours=guide['hours']),'shared-hr-hire')
    assert e.world.cash(other)==cash
    assert available(e.world,b.id,'hr')==own
    assert available(e.world,other,'hr')==shared-60
    e.validate()


def test_completed_hr_work_expires_and_other_company_cannot_use_it(game):
    e, leader, b, _, other = setup(game,True)
    apply(leader.rules,b,{'hr':[60]})
    assert recruitment_quote(e.world,other)['fee']==30000
    e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=30)).isoformat()
    assert recruitment_quote(e.world,b.id)['fee']==30000


def test_preview_save_reload_and_repeated_command_consume_hr_once(game):
    e, leader, b, _, _ = setup(game)
    apply(leader.rules,b,{'hr':[120]});commit(game,e)
    args=offer(game.world,b.id);before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        response=client.post('/api/preview',json=dict(action='hire_for_role',args={**args,'amount_dollars':str(args['amount']/100)},revision=game.world.revision,command_id='hr-preview'))
        assert response.status_code==200,response.text
        assert 'No outside recruitment fee' in response.json()['message']
        assert game.world.to_dict()==before
    rev=game.world.revision
    result=game.execute('hire_for_role',args,rev,'one-hr-hire')
    assert available(game.world,b.id,'hr')==60
    assert game.execute('hire_for_role',args,rev,'one-hr-hire')==result
    loaded=game.store.load()
    assert loaded.to_dict()==game.world.to_dict()
    assert available(loaded,b.id,'hr')==60
    assert loaded.cash(b.id)==before['accounts'][b.id]['asset:cash']
    game.store.audit(game.world)


def test_rejected_offer_keeps_hr_work_and_cash(game):
    e, leader, b, _, _ = setup(game)
    apply(leader.rules,b,{'hr':[60]});commit(game,e)
    args=offer(game.world,b.id);args['amount']=1
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError,match='declined'):
        act(game,'hire_for_role',**args)
    assert game.world.to_dict()==before


@pytest.mark.parametrize('minutes,fee', [(0,30000),(60,0)])
def test_both_hiring_screens_show_actual_fee_and_funding(game,minutes,fee):
    e, leader, b, _, _ = setup(game)
    apply(leader.rules,b,{'hr':[minutes]})
    e.action('create_position',dict(business_id=b.id,role='cashier'),'hr-ui-vacancy')
    commit(game,e)
    before=copy.deepcopy(game.world.to_dict())
    guide=hiring_view(game.world,b.id,'cashier')
    assert guide['upfront']==guide['salary']+fee
    with client_for(game) as client:
        page=client.get('/',params=dict(page='hiring',scope=b.id,business_id=b.id,role='cashier'))
        assert page.status_code==200,page.text
        assert f'data-recruitment-fee="{fee}"' in page.text
        assert guide['recruitment']['explanation'] in page.text
        assert 'plus $300 available' not in page.text
        business=client.get('/',params=dict(page='business',scope=b.id,business_id=b.id))
        assert business.status_code==200,business.text
        assert guide['recruitment']['explanation'] in business.text
        assert 'Accepted offers cost $300' not in business.text
    assert game.world.to_dict()==before
