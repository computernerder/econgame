import copy
from datetime import date,timedelta
import pytest
from test_game import game,act
from test_business import acquire
from test_campaign_product import client_for
from test_leadership import setup
from economic_simulation.domain import Engine,RuleError
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_models import ROLE_PAY
from economic_simulation.specialists import Specialists,apply,available,consume,recruitment_fee
from economic_simulation.shared_services import SharedServices


def add_specialist(engine,bid,role):
    rules=BusinessRules(engine);rules.make_person(role,candidate=True);person=engine.world.people[-1]
    rules.action('create_position',dict(business_id=bid,role=role),'position-'+role)
    rules.action('hire',dict(position_id=engine.world.positions[-1].id,person_id=person.id,amount=ROLE_PAY[role],weekly_hours=40),'hire-'+role)
    emp=engine.world.employments[-1];emp.status='active';emp.start_date=engine.world.date
    return emp,person


def test_specialist_work_changes_real_costs_and_capacity(game):
    engine,leader,b,_,_=setup(game)
    for role in ('it','purchasing','marketing','hr','logistics'):add_specialist(engine,b.id,role)
    leader.rules.operate(b,date.fromisoformat(engine.world.date))
    result=b.last_day['specialists']
    assert result['it_percent']>0 and result['marketing_percent']>0
    assert result['overhead_savings']>0 and result['hr_percent']>0
    assert result['supplier_savings']>0
    assert any(p['memo']=='Supplier volume rebate on goods sold' for p in engine.postings)
    assert available(engine.world,b.id,'hr')>0
    assert result['logistics_percent']>0
    engine.validate()


def test_banked_capacity_is_finite_expires_and_cannot_duplicate_same_day(game):
    engine,leader,b,_,_=setup(game)
    apply(leader.rules,b,{'accounting':[12000],'legal':[1200],'hr':[60]})
    assert available(engine.world,b.id,'accounting')==4800
    apply(leader.rules,b,{'accounting':[12000]})
    assert available(engine.world,b.id,'accounting')==4800
    consume(engine.world,b.id,'legal',1200)
    with pytest.raises(RuleError):consume(engine.world,b.id,'legal',1)
    engine.world.date=(date.fromisoformat(engine.world.date)+timedelta(days=30)).isoformat()
    assert available(engine.world,b.id,'accounting')==0


def test_accounting_report_consumes_work_and_keeps_balances_unchanged(game):
    engine,leader,b,_,_=setup(game)
    before=copy.deepcopy(engine.world.accounts)
    with pytest.raises(RuleError):Specialists(engine).action('specialist_report',dict(business_id=b.id))
    apply(leader.rules,b,{'accounting':[180]})
    Specialists(engine).action('specialist_report',dict(business_id=b.id))
    report=engine.world.systems['management_reports'][-1]
    assert report['cash']==engine.world.cash(b.id) and report['profit']==report['revenue']-report['expenses']
    assert available(engine.world,b.id,'accounting')==60 and engine.world.accounts==before
    engine.validate()


def test_legal_negotiation_reduces_purchase_price_once_without_negative_goodwill(game):
    engine,leader,b,_,_=setup(game)
    target=next(x for x in engine.world.businesses if x.status=='market' and not x.market_parent)
    original=target.asking
    apply(leader.rules,b,{'legal':[2400]})
    Specialists(engine).action('negotiate_acquisition',dict(business_id=b.id,target_id=target.id))
    assert target.asking<original and leader.rules.quote(target.id)['goodwill']>=0
    assert available(engine.world,b.id,'legal')==1200 and target.owner is None
    with pytest.raises(RuleError):Specialists(engine).action('negotiate_acquisition',dict(business_id=b.id,target_id=target.id))
    assert available(engine.world,b.id,'legal')==1200
    engine.validate()


def test_hr_recruitment_fee_uses_one_hour_of_hr_work(game):
    engine,leader,b,_,_=setup(game)
    apply(leader.rules,b,{'hr':[60]})
    assert recruitment_fee(engine.world,b.id)==0
    before=engine.world.cash(b.id)
    add_specialist(engine,b.id,'it')
    assert before==engine.world.cash(b.id)
    assert available(engine.world,b.id,'hr')==0 and recruitment_fee(engine.world,b.id)==30000
    engine.validate()


def test_shared_accountant_time_benefits_recipient_without_duplication(game):
    engine,leader,b,_,second=setup(game,True)
    emp,person=add_specialist(engine,b.id,'accounting');services=SharedServices(engine)
    services.action('service_agreement',dict(source=b.id,target=second,staff_access=True),'accounting-agreement')
    services.action('assign_staff',dict(employment_id=emp.id,target=second,role='accounting',start_minute=480,minutes=240),'accounting-assignment')
    today=date.fromisoformat(engine.world.date)
    leader.rules.operate(b,today);leader.rules.operate(leader.rules.company(second),today);services.settle(today)
    own=available(engine.world,b.id,'accounting');shared=available(engine.world,second,'accounting')
    assert own>0 and shared>0 and own+shared<=480*115//100
    assert engine.world.systems['assignments'][-1]['last_cost']>0
    engine.validate()


def test_expired_license_and_absence_do_not_create_service_hours(game):
    engine,leader,b,_,_=setup(game)
    emp,person=add_specialist(engine,b.id,'legal');person.licenses['legal_practice']='2025-01-01'
    leader.rules.operate(b,date.fromisoformat(engine.world.date))
    assert available(engine.world,b.id,'legal')==0
    engine.world.date='2026-01-13';person.licenses['legal_practice']='2030-01-01';emp.leave_until='2026-02-01'
    leader.rules.operate(b,date.fromisoformat(engine.world.date))
    assert available(engine.world,b.id,'legal')==0


def test_shared_services_ui_shows_concrete_specialist_value(game):
    bid=acquire(game)
    with client_for(game) as c:
        response=c.get('/?page=services')
        assert response.status_code==200
        assert 'Make specialists earn their place' in response.text
        assert 'Prepare accounting report' in response.text and 'Review legal negotiation' in response.text
        page=c.get('/',params=dict(page='business',business_id=bid))
        assert 'Bank 20 qualified hours' in page.text

def test_logistics_coordinator_reduces_actual_outside_carrier_bill(game):
    from economic_simulation.logistics import settle_transport
    engine,leader,b,_,_=setup(game)
    today=date.fromisoformat(engine.world.date)
    leader.rules.operate(b,today)
    normal=Engine(copy.deepcopy(engine.world));supported=Engine(copy.deepcopy(engine.world))
    client=next(x for x in supported.world.businesses if x.id==b.id)
    client.last_day['specialists']['logistics_percent']=20
    settle_transport(BusinessRules(normal),today);settle_transport(BusinessRules(supported),today)
    original=next(x for x in normal.world.businesses if x.id==b.id)
    assert original.last_day['transport_cost']>0
    assert client.last_day['transport_cost']==original.last_day['transport_cost']*80//100
    assert client.last_day['specialists']['freight_savings']==original.last_day['transport_cost']-client.last_day['transport_cost']
    normal.validate();supported.validate()

def test_hr_does_not_cancel_unpaid_payroll_consequences(game):
    engine,leader,b,manager,_=setup(game)
    b.payroll_overdue=True
    person=leader.rules.person(manager.person_id);morale=person.morale;loyalty=person.loyalty
    apply(leader.rules,b,{'hr':[480]})
    assert person.morale==morale and person.loyalty==loyalty
