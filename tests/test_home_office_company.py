import copy
from datetime import date
import pytest
from test_game import game,act,step
from test_business import acquire
from test_specialists import add_specialist
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.expansion import Expansion
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_views import group_profit,descendants
from economic_simulation.service_office import ServiceOffice
from economic_simulation.shared_services import SharedServices
from economic_simulation.home_office_company import companies
from economic_simulation.campaign_views import campaign_view


def create_office(game):
    act(game,'start_business',industry='office',name='Group Services',region='Rutland County')
    return game.world.businesses[-1].id


def test_company_is_optional_and_creation_has_separate_funded_books(game):
    assert not companies(game.world)
    before=copy.deepcopy(game.world.to_dict())
    view=campaign_view(game.world,'home_office','personal')
    assert view['office_creation']['action']=='start_business'
    assert game.world.to_dict()==before
    quote=Expansion(Engine(game.world)).opening_quote('office')
    bid=create_office(game)
    assert game.world.cash('personal')==before['accounts']['personal']['asset:cash']-quote['total']
    assert game.world.cash(bid)==quote['reserve']
    assert game.world.accounts[bid]['expense:startup']==quote['expense']
    assert companies(game.world)[0]['profit']==-quote['expense']
    assert companies(game.world)[0]['internal_earned']==0
    assert game.world.accounts['personal']['asset:investment:'+bid]==quote['total']
    assert companies(game.store.load())==companies(game.world)
    game.store.audit(game.world)


def test_company_formation_rejects_unfunded_setup_without_partial_company(game):
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError,match='cash'):
        act(game,'start_business',industry='office',name='Unfunded Office',region='Rutland County',reserve=1000000000)
    assert game.world.to_dict()==before


def test_existing_departments_stay_put_and_new_office_is_default_provider(game):
    recipient=acquire(game)
    act(game,'department_configure',provider=recipient,department='accounting')
    original=copy.deepcopy(game.world.systems['departments'])
    bid=create_office(game)
    assert game.world.systems['departments']==original
    view=campaign_view(game.world,'home_office',recipient)
    form=next(f for f in view['forms'] if f['action']=='department_configure')
    assert next(f for f in form['fields'] if f['name']=='provider')['value']==bid
    assert form['anchor']=='department-setup'
    client=client_for(game);before=copy.deepcopy(game.world.to_dict())
    page=client.get('/?page=home_office&scope='+bid)
    assert page.status_code==200 and 'Separate financial report' in page.text and 'Group Services' in page.text
    assert 'id="department-setup"' in page.text and 'id="department-setup" open' not in page.text
    focused=client.get('/?page=home_office&scope='+bid+'&action_focus=department_configure')
    assert 'id="department-setup" open' in focused.text
    for key in ('business_url','finance_url','people_url','capital_url','services_url'):
        assert client.get(companies(game.world)[0][key]).status_code==200
    assert game.world.to_dict()==before


def test_office_uses_actual_labor_and_separate_receivable_without_group_profit(game):
    recipient=acquire(game);bid=create_office(game)
    e=Engine(copy.deepcopy(game.world));rules=BusinessRules(e);b=rules.company(bid)
    e.world.date='2026-01-12';b.status='operating'
    emp,_=add_specialist(e,bid,'accounting')
    office=ServiceOffice(e)
    office.action('department_configure',dict(provider=bid,department='accounting',staff=emp.id,regions='Rutland County',industries='retail'),'department')
    for i in range(3):office.action('service_request',dict(provider=bid,recipient=recipient,department='accounting',mode='internal'),'queue-'+str(i))
    buckets,_=rules.work(b,date.fromisoformat(e.world.date))
    wages=e.world.accounts[bid]['expense:wages']
    before_profit=group_profit(e.world,descendants(e.world,'personal'))
    parent=copy.deepcopy(e.world.accounts['personal']);cash=e.world.cash(bid)
    capacity=sum(buckets['accounting']);office.deliver(rules,b,buckets)
    tasks=e.world.systems['service_tasks'];charge=sum(t['internal_cost'] for t in tasks)
    assert charge>0 and e.world.cash(bid)==cash
    assert e.world.accounts[bid]['asset:intercompany:'+recipient]==charge
    assert e.world.accounts[recipient]['liability:intercompany:'+bid]==-charge
    assert e.world.accounts[bid]['expense:wages']==wages
    assert group_profit(e.world,descendants(e.world,'personal'))==before_profit
    dept=e.world.systems['departments'][bid+':accounting']
    assert 0<dept['last_used']<=capacity and sum(buckets['accounting'])==capacity-dept['last_used']
    assert tasks[-1]['status']=='queued'
    row=companies(e.world)[0]
    assert row['internal_earned']==charge and row['receivable']==charge and row['payroll']>=wages
    SharedServices(e).settle(date.fromisoformat(e.world.date))
    assert e.world.cash(bid)==cash+charge and e.world.accounts[bid]['asset:intercompany:'+recipient]==0
    assert group_profit(e.world,descendants(e.world,'personal'))==before_profit
    assert e.world.accounts['personal']==parent
    e.validate();game.store.commit(e,game.world.revision);game.world=e.world
    assert companies(game.store.load())==companies(game.world)
    game.store.audit(game.world)


def test_office_opening_gate_and_no_free_department_revenue(game):
    bid=create_office(game);e=Engine(copy.deepcopy(game.world));rules=BusinessRules(e);b=rules.company(bid)
    e.world.date='2026-01-12';emp,_=add_specialist(e,bid,'accounting')
    office=ServiceOffice(e);office.action('department_configure',dict(provider=bid,department='accounting',staff=emp.id),'department')
    office.action('service_request',dict(provider=bid,recipient='personal',department='accounting',mode='internal'),'queue')
    before=copy.deepcopy(e.world.accounts)
    office.deliver(rules,b,{'accounting':[480]*24})
    assert e.world.systems['service_tasks'][-1]['worked']==0 and e.world.accounts==before
    b.status='operating';e.world.systems['service_tasks'][-1]['status']='cancelled'
    rules.operate(b,date.fromisoformat(e.world.date))
    row=companies(e.world)[0]
    assert row['internal_earned']==0 and row['payroll']>0 and row['unused_minutes']>0
    assert b.last_day['output']==0 and b.last_day['unit']=='shared-service staff minutes'
