import copy
import pytest
from test_game import game,act
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import Engine,RuleError
from economic_simulation.holding_company import exists
from economic_simulation.business_views import entity_names,descendants
from economic_simulation.organization import ownership_tree
from economic_simulation.navigation import navigation_view


def test_new_campaign_has_only_personal_owner_and_no_default_company(game):
    before=copy.deepcopy(game.world.to_dict())
    assert not exists(game.world)
    assert entity_names(game.world)=={'personal':'Personal portfolio'}
    assert descendants(game.world,'personal')==['personal']
    assert ownership_tree(game.world)['companies']==0
    assert [c['id'] for c in navigation_view(game.world,'overview','personal')['choices']]==['personal']
    with client_for(game) as client:
        for page in ['overview','organization','owner','expansion','financing','spaces','policies']:
            response=client.get('/',params={'page':page,'scope':'company'})
            assert response.status_code==200
            assert 'Your property company' not in response.text
            assert '<option value="company"' not in response.text
        assert 'Create a holding company' in client.get('/?page=owner').text
        assert 'data-action="invest"' not in client.get('/?page=owner').text
    assert game.world.to_dict()==before


def test_explicit_formation_is_named_empty_persistent_and_can_be_funded(game):
    before=game.world.cash('personal')
    act(game,'create_holding_company',name='Willow Holdings')
    assert exists(game.world) and game.world.cash('personal')==before
    assert game.world.cash('company')==0
    assert entity_names(game.world)['company']=='Willow Holdings'
    assert ownership_tree(game.world)['companies']==1
    restored=Game(game.store.path)
    assert entity_names(restored.world)['company']=='Willow Holdings'
    restored.close()
    act(game,'invest',amount=10000000)
    act(game,'buy',entity='company',property_id=game.world.properties[0].id)
    assert game.world.properties[0].owner=='company'
    game.store.audit(game.world)
    with client_for(game) as client:
        assert 'Willow Holdings' in client.get('/?page=owner').text
        assert 'data-action="create_holding_company"' not in client.get('/?page=owner').text


def test_cannot_use_uncreated_company_or_create_duplicate(game):
    before=game.world.to_dict()
    for action,args in [('invest',dict(amount=100)),('buy',dict(entity='company',property_id=game.world.properties[0].id)),('fund_business',dict(business_id='company',amount=100)),('create_holding_company',dict(name=' '))]:
        with pytest.raises(RuleError):act(game,action,**args)
    assert game.world.to_dict()==before
    act(game,'create_holding_company',name='My Holdings')
    with pytest.raises(RuleError):act(game,'create_holding_company',name='Duplicate')


def test_legacy_used_company_is_preserved_without_formation_record(game):
    engine=Engine(copy.deepcopy(game.world))
    engine.post('personal','legacy-owner','Legacy investment',{'asset:cash':-100000,'asset:investment':100000})
    engine.post('company','legacy-company','Legacy capital',{'asset:cash':100000,'equity:capital':-100000})
    game.store.commit(engine,game.world.revision);game.world=engine.world
    assert 'holding_company' not in game.world.systems
    assert entity_names(game.world)['company']=='Your property company'
    act(game,'withdraw',amount=100000)
    assert exists(game.world)  # Preserve historical accounts even at zero cash.
    game.store.audit(game.world)


def test_calendar_and_tax_bookkeeping_do_not_create_a_company():
    from economic_simulation.domain import new_game
    engine=new_game()
    for _ in range(370):engine.advance_day()
    assert not exists(engine.world)
    assert 'company' not in entity_names(engine.world)
    engine.validate()
