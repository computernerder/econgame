import copy
import json

import pytest

from test_game import game, act, step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine, RuleError
from economic_simulation.application import Game


def enable(game):
    act(game, 'developer_toggle', enabled=True)


def profit(game, entity):
    return -sum(v for k,v in game.world.accounts[entity].items() if k.startswith(('income:', 'expense:')))


def test_disabled_guard_enable_and_read_only_page(game):
    before = copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError, match='Enable developer'):
        act(game,'developer_cash',amount=10000)
    with client_for(game) as client:
        page = client.get('/?page=developer')
        assert page.status_code == 200 and 'Enable developer tools' in page.text
        assert 'data-action="developer_cash"' not in page.text
    assert game.world.to_dict() == before
    enable(game)
    assert not game.world.systems['settings']['modified']


def test_cash_balances_idempotence_backup_and_disable(game):
    enable(game)
    before = game.world.cash('personal'); prior_profit = profit(game,'personal')
    revision = game.world.revision
    result = game.execute('developer_cash', {'amount':123456}, revision, 'debug-cash-once')
    assert game.execute('developer_cash', {'amount':123456}, revision, 'debug-cash-once') == result
    assert game.world.cash('personal') == before + 123456
    assert profit(game,'personal') == prior_profit
    assert len(game.world.systems['developer_history']) == 1
    assert list(game.store.path.parent.glob('*before-developer-edit*'))
    act(game,'developer_cash',mode='remove',amount=123456)
    assert game.world.cash('personal') == before
    act(game,'developer_cash',mode='set',amount=0)
    assert game.world.cash('personal') == 0
    act(game,'developer_toggle',enabled=False)
    assert game.world.systems['settings']['modified']
    game.store.audit(game.world)
    assert game.store.load().to_dict() == json.loads(json.dumps(game.world.to_dict()))


@pytest.mark.parametrize('args', [dict(amount=-1),dict(amount=True),dict(amount='1.5'),dict(amount=10**12),dict(amount=1,mode='garbage'),dict(amount=10**11,mode='remove'),dict(amount=1,entity='not-owned')])
def test_cash_rejects_invalid_edits_atomically(game,args):
    enable(game); before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError):act(game,'developer_cash',**args)
    assert game.world.to_dict() == before
    assert not list(game.store.path.parent.glob('*before-developer-edit*'))


def test_business_stock_and_employee_keep_accounts_and_identities(game):
    bid = acquire(game);enable(game)
    before_profit = profit(game,bid)
    act(game,'developer_cash',entity=bid,amount=10000)
    assert profit(game,bid) == before_profit
    for field,value in [('daily_demand',0),('equipment_condition',20),('customer_relationships',5),('capacity_percent',0)]:
        act(game,'developer_business',business_id=bid,field=field,value=value)
    for units in (10000,7,0):
        act(game,'developer_stock',business_id=bid,value=units)
        b=next(b for b in game.world.businesses if b.id==bid)
        lots=game.world.systems['industry_state'][bid]['inventory_lots']
        assert sum(x['units'] for x in lots) == b.inventory_units == units
        assert game.world.accounts[bid]['asset:inventory'] == units*b.unit_cost
        assert profit(game,bid) == before_profit
    emp=next(e for e in game.world.employments if e.employer==bid and e.status=='active')
    original=copy.deepcopy(emp)
    person=next(p for p in game.world.people if p.id==emp.person_id)
    qualification=copy.deepcopy(person.qualifications)
    skill=next(iter(person.skills))
    act(game,'developer_employee',employment_id=emp.id,field='morale',value=1)
    act(game,'developer_employee',employment_id=emp.id,field='skill:'+skill,value=100)
    assert next(e for e in game.world.employments if e.id==emp.id) == original
    person=next(p for p in game.world.people if p.id==emp.person_id)
    assert person.morale==1 and person.skills[skill]==100 and person.qualifications==qualification
    Engine(game.world).validate();game.store.audit(game.world)
    step(game)
    assert next(b for b in game.world.businesses if b.id==bid).last_day.get('output',0)==0


def test_property_condition_persists_and_changes_repair_quote(game):
    from economic_simulation.property_operations import PropertyOperations, systems_for
    p=game.world.properties[0];act(game,'buy',property_id=p.id);enable(game)
    cash=game.world.cash('personal');basis=game.world.accounts['personal'].copy()
    act(game,'developer_property',property_id=p.id,field='roof',value=3)
    p=game.world.properties[0]
    assert systems_for(game.world,p)['roof']['condition']==3
    assert PropertyOperations(Engine(game.world)).quote(p,'roof','replacement')['gain']==92
    assert game.world.cash('personal')==cash and game.world.accounts['personal']==basis
    step(game)
    assert systems_for(game.world,game.world.properties[0])['roof']['condition']<=3
    act(game,'developer_property',property_id=p.id,field='all_systems',value=95)
    assert game.world.properties[0].condition==95
    reopened=Game(game.store.path)
    try:
        assert all(x['condition']==95 for x in systems_for(reopened.world,reopened.world.properties[0]).values())
        reopened.store.audit(reopened.world)
    finally:reopened.close()


def test_preview_is_read_only_dollars_are_exact_and_label_visible(game):
    enable(game);before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        payload=dict(action='developer_cash',args={'amount_dollars':'100.01'},revision=game.world.revision,command_id='web-debug-money')
        response=client.post('/api/preview',json=payload)
        assert response.status_code==200,response.text
        assert game.world.to_dict()==before
        assert not list(game.store.path.parent.glob('*before-developer-edit*'))
        response=client.post('/api/command',json=payload)
        assert response.status_code==200,response.text
        assert game.world.cash('personal')==before['accounts']['personal']['asset:cash']+10001
        page=client.get('/?page=developer')
        assert 'Campaign · modified' in page.text and 'cash (cents)' in page.text
    game.store.audit(game.world)


def test_scope_field_bounds_and_unknown_actions_do_not_mutate(game):
    bid=acquire(game);enable(game)
    cases=[('developer_business',dict(business_id=bid,field='owner',value=1)),
           ('developer_business',dict(business_id=bid,field='reputation',value=101)),
           ('developer_business',dict(business_id=game.world.businesses[-1].id,field='daily_demand',value=5)),
           ('developer_property',dict(property_id=game.world.properties[-1].id,field='roof',value=1)),
           ('developer_employee',dict(employment_id='missing',field='morale',value=1))]
    before=copy.deepcopy(game.world.to_dict())
    for action,args in cases:
        with pytest.raises(RuleError):act(game,action,**args)
        assert game.world.to_dict()==before


def test_controls_do_not_mutate_when_rendering_owned_entities(game):
    bid=acquire(game);act(game,'buy',property_id=game.world.properties[0].id);enable(game)
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        page=client.get('/?page=developer').text
        for action in ('business','stock','employee','property'):
            assert 'data-action="developer_'+action+'"' in page
        assert '?page=developer&amp;scope='+bid in client.get('/?page=developer&scope='+bid).text
    assert game.world.to_dict()==before
