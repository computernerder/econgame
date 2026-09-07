import copy,json
from dataclasses import asdict
import pytest
from test_game import game,act,step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.business_views import entity_names,own_equity,group_profit,descendants
from economic_simulation.business_models import investment_account
from economic_simulation.domain import RuleError
from economic_simulation.organization import ownership_tree


def test_remove_subsidiary_preserves_operations_and_transfers_investment(game):
    act(game,'create_holding_company',name='Your property company')
    bid=acquire(game)
    cash={k:game.world.cash(k) for k in game.world.accounts}
    profit=group_profit(game.world,list(entity_names(game.world)))
    wealth=sum(own_equity(game.world,k) for k in entity_names(game.world))
    before=copy.deepcopy(game.world.to_dict())
    value=game.world.accounts['personal'][investment_account(bid)]
    goodwill=game.world.accounts['personal'].get('asset:goodwill:'+bid,0)
    act(game,'transfer_business',business_id=bid,new_owner='company')
    assert next(b for b in game.world.businesses if b.id==bid).owner=='company'
    assert game.world.accounts['company'][investment_account(bid)]==value
    assert game.world.accounts['company'].get('asset:goodwill:'+bid,0)==goodwill
    assert game.world.accounts['personal'][investment_account(bid)]==0
    assert cash=={k:game.world.cash(k) for k in game.world.accounts}
    assert group_profit(game.world,list(entity_names(game.world)))==profit
    assert sum(own_equity(game.world,k) for k in entity_names(game.world))==wealth
    for key in ('people','positions','employments','properties'):
        assert game.world.to_dict()[key]==before[key]
    assert game.world.accounts[bid]==before['accounts'][bid]
    act(game,'transfer_business',business_id=bid,new_owner='personal')
    act(game,'fund_business',business_id=bid,amount=100000)
    step(game,3)
    game.store.audit(game.world)
    restored=Game(game.store.path)
    assert json.dumps(restored.world.to_dict(),sort_keys=True)==json.dumps(game.world.to_dict(),sort_keys=True)
    restored.close()


def test_subtree_moves_and_cycles_rejected(game):
    act(game,'create_holding_company',name='Your property company')
    first=acquire(game,0);second=acquire(game,1)
    act(game,'transfer_business',business_id=second,new_owner=first)
    before=copy.deepcopy(game.world.to_dict())
    for target in (first,second):
        with pytest.raises(RuleError,match='cannot own itself'):
            act(game,'transfer_business',business_id=first,new_owner=target)
    assert game.world.to_dict()==before
    act(game,'transfer_business',business_id=first,new_owner='company')
    assert set(descendants(game.world,'company'))=={'company',first,second}
    assert next(b for b in game.world.businesses if b.id==second).owner==first
    assert any(child['id']==first for child in ownership_tree(game.world,'company')['root']['children'])
    game.store.audit(game.world)


def test_transfer_preview_is_read_only_and_command_idempotent(game):
    act(game,'create_holding_company',name='Your property company')
    bid=acquire(game)
    payload=dict(action='transfer_business',args=dict(business_id=bid,new_owner='company'),revision=game.world.revision,command_id='test-transfer-command')
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as c:
        headers={'Origin':'http://testserver','X-Game-Token':'test-token'}
        preview=c.post('/api/preview',json=payload,headers=headers)
        assert preview.status_code==200 and 'No cash changed hands' in preview.json()['message']
        assert game.world.to_dict()==before
        first=c.post('/api/command',json=payload,headers=headers);assert first.status_code==200
        after=copy.deepcopy(game.world.to_dict())
        repeat=c.post('/api/command',json=payload,headers=headers)
        assert repeat.status_code==200 and game.world.to_dict()==after
        page=c.get('/?page=organization&chart=ownership&scope=company')
        assert 'Rearrange business ownership' in page.text
    game.store.audit(game.world)


def test_pending_sale_freezes_affected_branches(game):
    act(game,'create_holding_company',name='Your property company')
    first=acquire(game,0);second=acquire(game,1)
    act(game,'sell_business',business_id=first)
    for bid,target in ((first,'company'),(second,first)):
        with pytest.raises(RuleError,match='sale is pending'):
            act(game,'transfer_business',business_id=bid,new_owner=target)
    with pytest.raises(RuleError,match='ownership'):
        act(game,'transfer_business',business_id=second,new_owner='missing-company')

def test_loans_guarantees_and_rent_survive_owner_change(game):
    from test_premises import business_property
    bid,pid,_=business_property(game,'company')
    act(game,'lease_premises',business_id=bid,property_id=pid,rent=100000,deposit_months=0)
    act(game,'borrow',entity=bid,amount=100000,months=12,guarantor='personal')
    loans=copy.deepcopy(game.world.systems['loans']);leases=copy.deepcopy(game.world.systems['leases'])
    act(game,'transfer_business',business_id=bid,new_owner='company')
    assert game.world.systems['loans']==loans and game.world.systems['leases']==leases
    before=game.world.accounts['company'].get('income:internal_rent:'+bid,0)
    step(game,2)
    assert game.world.accounts['company']['income:internal_rent:'+bid]<before
    assert game.world.systems['loans'][-1]['guarantor']=='personal'
    game.store.audit(game.world)
