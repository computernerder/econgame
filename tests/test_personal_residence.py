import copy
import json
import pytest

from test_game import game, act, step
from test_campaign_product import client_for
from economic_simulation.domain import Engine, World, RuleError, new_game
from economic_simulation.personal_residence import current, blocker, validate
from economic_simulation.property_operations import systems_for


def buy_home(game, index=0):
    p=[p for p in game.world.properties if p.owner is None and p.status=='market' and p.category=='residential' and p.condition>=40][index]
    act(game,'buy',property_id=p.id)
    return next(x for x in game.world.properties if x.id==p.id)


def test_residence_keeps_assets_and_upkeep_without_rent(game):
    p=buy_home(game);before=copy.deepcopy(game.world.accounts)
    act(game,'set_residence',property_id=p.id)
    assert game.world.accounts==before
    assert current(game.world).id==p.id
    step(game,7)
    home=current(game.world)
    assert home.status=='occupied' and home.occupant=='personal' and home.rent==0
    assert game.world.accounts['personal'].get('income:rent',0)==0
    assert game.world.accounts['personal']['expense:holding']>0
    assert game.world.cash('personal')<before['personal']['asset:cash']
    assert game.store.load().to_dict()==game.world.to_dict()
    game.store.audit(game.world)


def test_switch_and_move_out_restore_vacancy(game):
    first=buy_home(game);act(game,'set_residence',property_id=first.id)
    second=buy_home(game)
    act(game,'set_residence',property_id=second.id)
    assert current(game.world).id==second.id
    old=next(p for p in game.world.properties if p.id==first.id)
    assert old.status=='vacant' and old.occupant is None and old.occupancy_use=='rental'
    act(game,'clear_residence',property_id=second.id)
    assert current(game.world) is None
    act(game,'rent',property_id=second.id)
    assert next(p for p in game.world.properties if p.id==second.id).status=='seeking'
    game.store.audit(game.world)


@pytest.mark.parametrize('action,args',[
    ('rent',{}),('sell',{}),('configure_spaces',{'units':1}),
    ('release_premises',{}),('advertise_space',{}),('market_property',{}),
    ('property_work',{'kind':'conversion','system':'interior','use':'commercial'}),
])
def test_residence_cannot_be_leased_sold_or_converted(game,action,args):
    p=buy_home(game);act(game,'set_residence',property_id=p.id)
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError,match='Move out'):
        act(game,action,property_id=p.id,**args)
    assert game.world.to_dict()==before


def test_failed_move_keeps_old_home_and_existing_tenant(game):
    first=buy_home(game);act(game,'set_residence',property_id=first.id)
    other=buy_home(game);act(game,'rent',property_id=other.id);step(game,8)
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError,match='vacant'):act(game,'set_residence',property_id=other.id)
    assert game.world.to_dict()==before
    assert current(game.world).id==first.id
    assert next(p for p in game.world.properties if p.id==other.id).tenant


def test_eligibility_and_single_residence_validation(game):
    p=buy_home(game)
    for field,value,text in [('owner','company','personal portfolio'),('category','commercial','residential'),
                             ('condition',20,'40 condition'),('spaces',[{'id':'a'}],'undivided')]:
        test=copy.deepcopy(p);setattr(test,field,value)
        assert text in blocker(game.world,test)
    game.world.systems['property_listings']={p.id:{'status':'marketing'}}
    assert 'Withdraw' in blocker(game.world,p)
    game.world.systems['property_listings']={}
    act(game,'set_residence',property_id=p.id)
    other=copy.deepcopy(current(game.world));other.id='duplicate';game.world.properties.append(other)
    with pytest.raises(RuleError,match='only one'):validate(game.world)


def test_home_repairs_consume_cash_and_keep_occupancy(game):
    p=buy_home(game);act(game,'set_residence',property_id=p.id)
    cash=game.world.cash('personal');before=systems_for(game.world,p)['plumbing']['condition']
    act(game,'property_work',property_id=p.id,system='plumbing',kind='repair',provider='outside')
    assert game.world.cash('personal')<cash
    step(game,12)
    home=current(game.world)
    assert home.id==p.id and systems_for(game.world,home)['plumbing']['condition']>before
    assert game.world.systems['property_work'][-1]['status']=='complete'
    game.store.audit(game.world)


def test_property_owner_and_portfolio_render_residence_controls(game):
    p=buy_home(game);c=client_for(game)
    url='/?page=property&scope=personal&property_id='+p.id
    assert 'Make this my residence' in c.get(url).text
    act(game,'set_residence',property_id=p.id)
    for page in (url,'/?page=owner','/?page=portfolio'):
        response=c.get(page);assert response.status_code==200
        assert 'residence' in response.text and p.name in response.text
    assert 'Move out' in c.get(url).text
    assert 'No rental income' in c.get('/?page=portfolio').text
    assert 'Release premises · '+p.name not in c.get('/?page=spaces').text


def test_residence_seed_and_reload_equivalence():
    a=new_game(63);p=next(p for p in a.world.properties if p.category=='residential' and p.condition>=40)
    a.action('buy',{'property_id':p.id},'test-buy')
    a.action('set_residence',{'property_id':p.id},'test-home')
    b=Engine(World.from_dict(json.loads(json.dumps(a.world.to_dict()))))
    for _ in range(35):a.advance_day()
    for _ in range(35):
        b=Engine(World.from_dict(json.loads(json.dumps(b.world.to_dict()))));b.advance_day()
    assert json.loads(json.dumps(a.world.to_dict()))==json.loads(json.dumps(b.world.to_dict()))
