import copy
import json
import sqlite3
from dataclasses import asdict
from datetime import date

import pytest
from test_game import game, act, step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import new_game, Engine, RuleError, INDUSTRIES_CONTENT_VERSION, CONTENT_VERSION
from economic_simulation.application import Game
from economic_simulation.persistence import Store
from economic_simulation.real_estate import RealEstate


def test_five_categories_available_in_every_district(game):
    for region in ('Rutland County','Chittenden County','Washington County'):
        assert {p.category for p in game.world.properties if p.region==region and p.status=='market'} == {'residential','commercial','industrial','office','mixed_use','land'}
    client=client_for(game)
    for category in ('residential','commercial','industrial','office','mixed_use'):
        response=client.get('/?page=market&category='+category+'&region=Chittenden%20County')
        assert response.status_code==200
        for p in game.world.properties:
            if p.status=='market':
                assert (p.name in response.text)==(p.category==category and p.region=='Chittenden County')
        assert 'Property category' in response.text


def test_business_can_own_home_but_requires_suitable_operating_premises(game):
    bid=acquire(game)
    act(game,'fund_business',business_id=bid,amount=15000000)
    pid=game.world.properties[0].id
    act(game,'buy',entity=bid,property_id=pid)
    with pytest.raises(RuleError,match='commercial'):
        act(game,'occupy_property',business_id=bid,property_id=pid)
    assert next(p for p in game.world.properties if p.id==pid).owner==bid
    act(game,'rent',entity=bid,property_id=pid)
    step(game,10)
    assert next(p for p in game.world.properties if p.id==pid).tenant.startswith('Household')
    game.store.audit(game.world)


def test_industrial_space_supports_trades_and_conversion(game):
    from test_new_industries import purchase
    bid=purchase(game,'trades')
    act(game,'fund_business',business_id=bid,amount=20000000)
    p=next(p for p in game.world.properties if p.category=='industrial' and p.region=='Rutland County')
    act(game,'buy',entity='personal',property_id=p.id)
    act(game,'configure_spaces',property_id=p.id,units=1)
    p=next(x for x in game.world.properties if x.id==p.id)
    assert p.spaces[0]['use']=='industrial'
    act(game,'lease_space',property_id=p.id,space_id=p.spaces[0]['id'],tenant=bid,rent=100000,deposit_months=0)
    step(game,1)
    assert game.world.accounts['personal']['income:internal_rent:'+bid]<0
    game.store.audit(game.world)


def test_conversion_changes_permitted_tenant_use_after_work(game):
    p=game.world.properties[0]
    act(game,'buy',entity='personal',property_id=p.id)
    act(game,'configure_spaces',property_id=p.id,units=1)
    p=next(x for x in game.world.properties if x.id==p.id)
    act(game,'convert_space',property_id=p.id,space_id=p.spaces[0]['id'],use='industrial')
    engine=Engine(copy.deepcopy(game.world))
    plan=engine.world.systems['plans'][-1]
    with pytest.raises(RuleError,match='Finish the conversion'):
        RealEstate(engine).action('lease_space',{'property_id':p.id,'space_id':p.spaces[0]['id']},'test-early')
    engine.world.date=plan['due']
    RealEstate(engine).tick(date.fromisoformat(plan['due']))
    assert next(x for x in engine.world.properties if x.id==p.id).spaces[0]['use']=='industrial'
    engine.validate()


def test_existing_save_upgrade_preserves_assets_accounts_and_runs_once(tmp_path):
    engine=new_game()
    engine.world.properties=[p for p in engine.world.properties if p.category=='residential']
    engine.world.content_version=INDUSTRIES_CONTENT_VERSION
    path=tmp_path/'old.sqlite3'
    Store(path,initial=engine)
    before=engine.world.to_dict()
    # Old snapshots did not have the category field.
    with sqlite3.connect(path) as db:
        data=json.loads(db.execute('SELECT data FROM world').fetchone()[0])
        for p in data['properties']:p.pop('category')
        db.execute('UPDATE world SET data=?',(json.dumps(data),))
    upgraded=Game(path)
    after=upgraded.world.to_dict()
    assert after['accounts']==before['accounts']
    assert all(asdict(p)==old for p,old in zip(upgraded.world.properties,before['properties']))
    assert {p.category for p in upgraded.world.properties}=={'residential','commercial','industrial'}
    assert after['content_version']==CONTENT_VERSION
    upgraded.store.audit(upgraded.world)
    upgraded.close()
    again=Game(path)
    assert again.world.to_dict()==after
    again.close()
    assert len(list(tmp_path.glob('old.before-property-types-*.sqlite3')))==1
