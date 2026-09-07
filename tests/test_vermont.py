import copy
import json
import sqlite3
from dataclasses import asdict

from test_game import game, act
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import new_game, Engine, World
from economic_simulation.persistence import Store
from economic_simulation.vermont import COUNTIES, LEGACY_COUNTIES, migrate


def test_every_county_has_property_and_business_opportunities(game):
    assert len(COUNTIES) == 14 and len(set(COUNTIES)) == 14
    assert game.world.systems['setting'] == 'Vermont'
    assert {r['id'] for r in game.world.systems['regions']} == set(COUNTIES)
    for name in COUNTIES:
        assert {p.category for p in game.world.properties if p.region == name and p.status == 'market'} == {
            'residential', 'commercial', 'industrial', 'office', 'mixed_use', 'land'}
    act(game, 'start_business', industry='engineering', name='Green Mountain Design', region='Grand Isle County')
    assert game.world.businesses[-1].region == 'Grand Isle County'
    game.store.audit(game.world)


def test_migration_preserves_records_authority_and_random_streams(game):
    # Build a legacy-shaped snapshot, including queued work and geography grants.
    w = game.world
    reverse = {v:k for k,v in LEGACY_COUNTIES.items()}
    w.systems.pop('geography_version');w.systems.pop('setting')
    w.properties = [p for p in w.properties if p.region in reverse]
    for p in w.properties:p.region=reverse[p.region]
    for b in w.businesses:b.region=reverse.get(b.region,b.region)
    for p in w.people:p.home_region='Willow Creek'
    w.systems['regions'] = [r for r in w.systems['regions'] if r['id'] in reverse]
    for r in w.systems['regions']:r['id']=reverse[r['id']]
    w.systems['authority_contracts']={'sample':{'regions':['Willow Creek'], 'transaction_limit':12345}}
    w.systems['departments']={'sample':{'regions':['Northbank','Parkside']}}
    w.systems['test_pending']={'args':{'region':'Northbank','regions':'Willow Creek, Parkside'}, 'name':'Northbank Custom Business'}
    before = copy.deepcopy(w.to_dict())
    migrate(Engine(w))
    assert w.accounts == before['accounts'] and w.rng_state == before['rng_state']
    assert w.systems['streams'] == before['systems']['streams']
    assert w.systems['authority_contracts']['sample'] == {'regions':['Rutland County'], 'transaction_limit':12345}
    assert w.systems['departments']['sample']['regions'] == ['Chittenden County','Washington County']
    assert w.systems['test_pending']['args'] == {'region':'Chittenden County','regions':'Rutland County,Washington County'}
    assert w.systems['test_pending']['name'] == 'Northbank Custom Business'
    for old in before['properties']:
        now=asdict(next(p for p in w.properties if p.id==old['id']))
        assert now == dict(old,region=LEGACY_COUNTIES[old['region']])
    assert [(p.id,p.name) for p in w.people] == [(p['id'],p['name']) for p in before['people']]
    snapshot=copy.deepcopy(w.to_dict());migrate(Engine(w));assert w.to_dict()==snapshot


def test_store_upgrade_backs_up_once_and_reconciles(game):
    path=game.store.path
    with game.store.connection() as db:
        data=json.loads(db.execute('SELECT data FROM world').fetchone()[0])
        data['systems'].pop('geography_version')
        data['systems'].pop('setting')
        db.execute('UPDATE world SET data=?',(json.dumps(data),))
    store=Store(path);restored=store.load();store.audit(restored)
    assert restored.systems['geography_version']==24
    backups=list(path.parent.glob('*.before-vermont-*.sqlite3'))
    assert len(backups)==1
    with sqlite3.connect(backups[0].as_uri()+'?mode=ro',uri=True) as db:
        original=json.loads(db.execute('SELECT data FROM world').fetchone()[0])
    assert 'geography_version' not in original['systems']
    assert restored.accounts==original['accounts']
    Store(path)
    assert len(list(path.parent.glob('*.before-vermont-*.sqlite3')))==1
    assert Store(path).load().to_dict()==restored.to_dict()


def test_county_filters_and_legacy_bookmarks(game):
    c=client_for(game)
    html=c.get('/?page=market&region=Grand%20Isle%20County').text
    assert 'Vermont county' in html and 'All counties' in html
    assert 'value="Grand Isle County" selected' in html
    assert all(p.name in html for p in game.world.properties if p.region=='Grand Isle County' and p.status=='market')
    assert all(p.name not in html for p in game.world.properties if p.region=='Rutland County' and p.status=='market')
    assert 'value="Chittenden County" selected' in c.get('/?page=market&region=Northbank').text
    assert 'Vermont counties and community' in c.get('/?page=regions').text


def test_seed_save_load_and_daily_steps_remain_equivalent():
    a=new_game(92);b=new_game(92)
    assert a.world.to_dict()==b.world.to_dict()
    for _ in range(35):a.advance_day()
    for _ in range(35):
        b=Engine(World.from_dict(json.loads(json.dumps(b.world.to_dict()))))
        b.advance_day()
    assert json.loads(json.dumps(a.world.to_dict()))==json.loads(json.dumps(b.world.to_dict()))
    a.validate();b.validate()
