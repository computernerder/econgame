import copy
from datetime import date

import pytest

from test_game import game, act, step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine, RuleError, daily_share
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_views import group_profit, entity_names, company_view
from economic_simulation.real_estate import RealEstate
from economic_simulation.premises import external_rent, arrangement


def business_property(game, landlord):
    bid=acquire(game)
    if landlord=='business':
        landlord=bid
        act(game,'fund_business',business_id=bid,amount=10000000)
    elif landlord=='company':
        act(game,'create_holding_company',name='Your property company')
        act(game,'invest',amount=10000000)
    pid=next(p.id for p in game.world.properties if p.category=='commercial' and p.region==next(b.region for b in game.world.businesses if b.id==bid) and p.status=='market')
    act(game,'buy',entity=landlord,property_id=pid)
    return bid,pid,landlord


def test_company_buys_and_occupies_its_property(game):
    bid,pid,_=business_property(game,'business')
    personal=game.world.cash('personal')
    before=game.world.accounts[bid].get('expense:premises_rent',0)
    act(game,'occupy_property',business_id=bid,property_id=pid)
    step(game,7)
    prop=next(p for p in game.world.properties if p.id==pid)
    assert prop.owner==prop.occupant==bid and prop.status=='occupied'
    assert game.world.accounts[bid].get('expense:premises_rent',0)==before
    assert game.world.accounts[bid]['expense:holding']>0
    assert game.world.cash('personal')==personal
    view=company_view(BusinessRules(Engine(game.world)),next(b for b in game.world.businesses if b.id==bid))
    assert view['premises_rent']==0
    assert view['premises'][0]['owner']==view['name']
    game.store.audit(game.world)


def test_holding_company_receives_business_rent_without_group_profit(game):
    bid,pid,landlord=business_property(game,'company')
    before_owner=game.world.cash(landlord);before_tenant=game.world.cash(bid)
    act(game,'lease_premises',business_id=bid,property_id=pid,rent=110000,deposit_months=1)
    assert game.world.cash(landlord)==before_owner+110000
    assert game.world.cash(bid)==before_tenant-110000
    engine=Engine(copy.deepcopy(game.world));before=group_profit(engine.world,list(entity_names(engine.world)))
    before_owner=engine.world.cash(landlord);before_tenant=engine.world.cash(bid)
    RealEstate(engine).tick(date.fromisoformat(engine.world.date))
    rent=daily_share(110000,date.fromisoformat(engine.world.date))
    assert engine.world.cash(landlord)==before_owner+rent
    assert engine.world.cash(bid)==before_tenant-rent
    assert group_profit(engine.world,[landlord])==group_profit(game.world,[landlord])+rent
    assert group_profit(engine.world,[bid])==group_profit(game.world,[bid])-rent
    assert group_profit(engine.world,list(entity_names(engine.world)))==before
    assert arrangement(engine.world,next(b for b in engine.world.businesses if b.id==bid))['external_rent']==0
    engine.validate()
    game.store.commit(engine,game.world.revision);game.world=engine.world
    game.store.audit(game.world)


def test_external_rent_has_real_recipient(game):
    bid=acquire(game)
    engine=Engine(copy.deepcopy(game.world));business=next(b for b in engine.world.businesses if b.id==bid)
    landlord='external-landlord-'+bid
    existing=engine.world.cash(landlord)
    before=engine.world.cash(bid)
    external_rent(engine,business,date.fromisoformat(engine.world.date))
    amount=daily_share(business.monthly_lease,date.fromisoformat(engine.world.date))
    assert engine.world.cash(bid)==before-amount
    assert engine.world.cash(landlord)==existing+amount
    assert landlord not in entity_names(engine.world)
    engine.validate()


def test_external_arrears_survive_relocation_and_pay_landlord(game):
    bid,pid,_=business_property(game,'business')
    engine=Engine(copy.deepcopy(game.world));business=next(b for b in engine.world.businesses if b.id==bid)
    cash=engine.world.cash(bid)
    engine.post(bid,'fixture-empty','Test shortfall',{'asset:cash':-cash,'expense:test':cash})
    landlord='external-landlord-'+bid
    before=engine.world.cash(landlord)
    external_rent(engine,business,date.fromisoformat(engine.world.date))
    due=-engine.world.accounts[bid]['liability:rent:'+landlord]
    assert due>0 and engine.world.cash(landlord)==before
    RealEstate(engine).action('occupy_property',{'business_id':bid,'property_id':pid},'fixture-occupy')
    engine.world.date='2026-01-20'
    engine.post(bid,'fixture-fund','Test funding',{'asset:cash':due,'income:test':-due})
    external_rent(engine,business,date.fromisoformat(engine.world.date))
    assert engine.world.accounts[bid]['liability:rent:'+landlord]==0
    assert engine.world.cash(landlord)==before+due
    assert engine.world.accounts[landlord]['asset:rent_receivable:'+bid]==0
    engine.validate()


def test_company_rent_arrears_are_paid_after_funding_even_after_end(game):
    bid,pid,owner=business_property(game,'company')
    act(game,'lease_premises',business_id=bid,property_id=pid,rent=100000,deposit_months=0)
    engine=Engine(copy.deepcopy(game.world));lease=engine.world.systems['leases'][-1]
    cash=engine.world.cash(bid)
    engine.post(bid,'fixture-spend','Test cash shortfall',{'asset:cash':-cash,'expense:test':cash})
    RealEstate(engine).settle_company_rent(lease,4000)
    assert lease['arrears']==4000
    assert engine.world.accounts[owner]['asset:intercompany:'+bid]==4000
    engine.world.date='2026-01-20'
    engine.post(bid,'fixture-income','Test cash replenishment',{'asset:cash':6000,'income:test':-6000})
    lease['status']='ended'
    before=engine.world.cash(owner)
    RealEstate(engine).tick(date.fromisoformat(engine.world.date))
    assert lease['arrears']==0
    assert engine.world.cash(owner)==before+4000
    assert engine.world.accounts[owner]['asset:intercompany:'+bid]==0
    assert engine.world.accounts[bid]['liability:intercompany:'+owner]==0
    engine.validate()


def test_duplicate_premises_and_external_property_purchase_rejected(game):
    bid,pid,_=business_property(game,'company')
    act(game,'lease_premises',business_id=bid,property_id=pid,rent=100000)
    with pytest.raises(RuleError):
        act(game,'lease_premises',business_id=bid,property_id=pid,rent=100000)
    landlord='external-landlord-'+bid
    with pytest.raises(RuleError,match='ownership'):
        act(game,'buy',property_id=game.world.properties[1].id,entity=landlord)


def test_company_page_shows_landlord_and_real_rent(game):
    bid,pid,_=business_property(game,'company')
    with client_for(game) as client:
        response=client.get('/',params={'page':'business','business_id':bid,'scope':bid})
        assert 'data-action="lease_premises"' in response.text
        act(game,'lease_premises',business_id=bid,property_id=pid,rent=123400)
        response=client.get('/',params={'page':'business','business_id':bid,'scope':bid})
        assert response.status_code==200
        assert 'Your property company' in response.text
        assert '<td>$1,234</td>' in response.text
        assert 'data-action="lease_premises"' not in response.text
