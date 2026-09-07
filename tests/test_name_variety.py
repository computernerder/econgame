"""Naming variety without identity changes or economic RNG side effects."""
import copy,re
from datetime import date
import pytest
from test_game import game,act
from test_campaign_product import client_for
from economic_simulation.domain import new_game,World,Engine
from economic_simulation.business_rules import BusinessRules
from economic_simulation.employee_names import unique_name,FIRST,LAST,migrate_names
from economic_simulation.world_names import business_name,property_name,tenant_name,supplier_name


def test_new_world_names_are_varied_unique_and_repeatable():
    a=new_game(42).world;b=new_game(42).world;c=new_game(8317).world
    assert a.to_dict()==b.to_dict()
    for key in ('people','businesses','properties'):
        names=[x.name for x in getattr(a,key)];other={x.name for x in getattr(c,key)}
        assert len(names)==len(set(n.casefold() for n in names))
        assert len(set(names)&other)<len(names)//5
    assert len({p.name.split()[0] for p in a.people})>len(a.people)*.7
    assert all(not re.search(r'\d',p.name) for p in a.people)
    assert all('Branch ' not in b.name for b in a.businesses)
    assert len(FIRST)*len(LAST)>75000


def test_many_names_have_no_numbers_or_duplicate_names():
    w=World(seed=378);used=set()
    for n in range(1500):
        name=unique_name(w,'extra-'+str(n),used)
        assert name.casefold() not in used and not re.search(r'\d',name)
        used.add(name.casefold())
    assert len({n.split()[0] for n in used})>230
    assert len({n.split()[-1] for n in used})>250


def test_existing_names_and_player_choices_survive_load_and_new_arrivals():
    w=new_game(83).world;w.people[0].name='Mara Custom';w.businesses[0].name='My Chosen Shop';w.properties[0].name='Our Family Home'
    before={key:[(x.id,x.name) for x in getattr(w,key)] for key in ('people','businesses','properties')}
    restored=World.from_dict(copy.deepcopy(w.to_dict()))
    assert migrate_names(restored)==0
    e=Engine(restored);BusinessRules(e).make_person('cashier',True);BusinessRules(e).add_business(0);e.populate_market(4)
    for key,rows in before.items():
        current={x.id:x.name for x in getattr(restored,key)}
        assert all(current[id]==name for id,name in rows)
    assert restored.people[0].name=='Mara Custom'
    e.validate()


def test_name_generation_never_consumes_simulation_randomness():
    e=new_game(589);before=copy.deepcopy(e.world.to_dict())
    for index in range(30):
        unique_name(e.world,'name-test-'+str(index))
        business_name(e.world,'business-test-'+str(index),'bank')
        property_name(e.world,'property-test-'+str(index),'land')
        tenant_name(e.world,'tenant-test-'+str(index))
        supplier_name(e.world,'supplier-test-'+str(index),'legal')
    assert e.world.to_dict()==before


def test_saved_generation_continues_identically():
    e=new_game(327);r=Engine(World.from_dict(copy.deepcopy(e.world.to_dict())))
    for engine in (e,r):
        BusinessRules(engine).make_person('engineer',True)
        BusinessRules(engine).add_business(2)
        engine.populate_market(5)
    assert e.world.to_dict()==r.world.to_dict()


def test_cosmetic_names_do_not_change_money_traits_or_daily_rng(monkeypatch):
    a=new_game(742)
    with monkeypatch.context() as m:
        m.setattr('economic_simulation.world_names.business_name',lambda w,id,*args,**kwargs:'Company '+id)
        m.setattr('economic_simulation.world_names.property_name',lambda w,id,*args,**kwargs:'Property '+id)
        m.setattr('economic_simulation.world_names.tenant_name',lambda w,id,*args,**kwargs:'Tenant '+id)
        b=new_game(742)
        for e in (a,b):
            e.action('buy',dict(property_id='p1'),'test-buy')
            e.get_property('p1').condition=100
            e.action('rent',dict(property_id='p1'),'test-rent')
        for _ in range(10):
            a=Engine(copy.deepcopy(a.world));b=Engine(copy.deepcopy(b.world))
            a.advance_day();b.advance_day()
            assert a.world.accounts==b.world.accounts
            assert a.world.rng_state==b.world.rng_state
            assert a.world.business_rng_state==b.world.business_rng_state
            assert a.world.systems['streams']==b.world.systems['streams']
    assert [(p.id,p.skills,p.qualifications) for p in a.world.people]==[(p.id,p.skills,p.qualifications) for p in b.world.people]


def test_tenant_supplier_and_competitor_names_are_recorded():
    from economic_simulation.economy import Economy
    from economic_simulation.supplier_contracts import SupplierContracts
    e=new_game(159);Economy(e).competitors(date.fromisoformat(e.world.date))
    names=[r['name'] for r in e.world.systems['competitors']]
    assert len(names)==len(set(names)) and all(' County Trading' not in n for n in names)
    task=dict(id='supplier-test',recipient='personal',service_department='legal')
    SupplierContracts(e).offers(task,90)
    offers=e.world.systems['supplier_offers']
    assert len({o['supplier'] for o in offers})==3
    assert all(any(term in o['supplier'] for term in ('Legal','Law','Counsel')) for o in offers)
    e.world.systems['tenant_offers']=[dict(name=tenant_name(e.world,'renter-1'))]
    assert tenant_name(e.world,'renter-2')!=e.world.systems['tenant_offers'][0]['name']


def test_counties_and_chosen_business_name_are_not_randomized(game):
    from economic_simulation.vermont import COUNTIES
    assert {p.region for p in game.world.properties}==set(COUNTIES)
    act(game,'start_business',name='My Favorite Store',industry='retail')
    assert game.world.businesses[-1].name=='My Favorite Store'


def test_new_campaign_seed_is_editable_and_suggested_in_both_forms(game):
    with client_for(game) as client:
        for route in ('/?page=games','/?page=settings'):
            html=client.get(route).text
            assert 'data-random-seed' in html
        assert 'crypto.getRandomValues' in client.get('/static/usability.js').text
