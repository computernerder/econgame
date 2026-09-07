import copy
from datetime import date
import pytest
from test_game import game, act, step
from test_new_industries import purchase
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.finance_rules import Finance
from economic_simulation.business_views import group_profit,eliminated
from economic_simulation.banking import bank_view
from economic_simulation.application import Game


def setup_bank(game):
    bid=purchase(game,'bank')
    act(game,'create_holding_company',name='Your property company')
    act(game,'invest',amount=20000000)
    return bid


def test_owner_bank_approval_discount_and_real_funding(game):
    bid=setup_bank(game)
    with pytest.raises(RuleError,match='at most'):
        act(game,'borrow',entity='company',amount=12000000,months=60)
    bank_cash=game.world.cash(bid);borrower_cash=game.world.cash('company')
    act(game,'borrow',entity='company',lender=bid,amount=12000000,months=60)
    loan=game.world.systems['loans'][-1]
    assert loan['rate_bps']==max(100,game.world.systems['interest_bps'])
    assert game.world.cash(bid)==bank_cash-12000000
    assert game.world.cash('company')==borrower_cash+12000000
    assert game.world.accounts[bid]['asset:internal_loan:company']==12000000
    assert game.world.accounts['company']['liability:internal_loan:'+bid]==-12000000
    game.store.audit(game.world)
    with client_for(game) as client:
        response=client.get('/?page=financing&scope=company')
        assert response.status_code==200 and 'owner benefits' in response.text and '75%' in response.text
    restored=Game(game.store.path);restored.store.audit(restored.world);restored.close()


def test_interest_repayment_and_fees_reach_bank_and_cancel_in_group(game):
    bid=setup_bank(game)
    act(game,'borrow',entity='company',lender=bid,amount=1000000,months=12)
    lid=game.world.systems['loans'][-1]['id']
    e=Engine(copy.deepcopy(game.world));f=Finance(e);before=group_profit(e.world,['company',bid])
    e.world.date='2026-01-05';f.end_day(date(2026,1,5))
    loan=e.world.systems['loans'][-1];interest=loan['interest_due'];assert interest>0
    assert e.world.accounts[bid]['asset:internal_interest:company']==interest
    assert group_profit(e.world,['company',bid])==before
    cash=e.world.cash(bid)
    f.action('repay_loan',dict(entity='company',loan_id=lid,amount=1000000+interest),'test-pay')
    assert e.world.cash(bid)==cash+1000000+interest and loan['status']=='repaid'
    e.validate();game.store.commit(e,game.world.revision);game.world=e.world;game.store.audit(game.world)
    assert eliminated('asset:internal_loan:company',['company',bid])
    assert eliminated('liability:internal_loan:'+bid,['company',bid])


def test_bank_reserves_self_lending_and_unowned_bank_rejected(game):
    bid=setup_bank(game)
    with pytest.raises(RuleError,match='different from the borrower'):
        act(game,'borrow',entity=bid,lender=bid,amount=100000,months=12)
    with pytest.raises(RuleError,match='operating bank'):
        act(game,'borrow',entity='company',lender='missing-bank',amount=100000,months=12)
    e=Engine(copy.deepcopy(game.world));b=next(b for b in e.world.businesses if b.id==bid)
    cash=e.world.cash(bid);e.post(bid,'test-illiquid','Test expense',{'asset:cash':-cash,'expense:test':cash})
    assert bank_view(e.world,b)['lendable']==0
    with pytest.raises(RuleError,match='at most'):
        Finance(e).action('borrow',dict(entity='company',lender=bid,amount=100000,months=12),'test-loan')


def test_scheduled_payment_and_restructure_reconcile_multiple_loans(game):
    bid=setup_bank(game)
    for amount in (1000000,2000000):act(game,'borrow',entity='company',lender=bid,amount=amount,months=12)
    lid=game.world.systems['loans'][-1]['id'];cash=game.world.cash(bid)
    act(game,'restructure_loan',entity='company',loan_id=lid)
    assert game.world.cash(bid)==cash+20000
    step(game,40)
    loans=[l for l in game.world.systems['loans'] if l.get('lender')==bid]
    assert all(l['history'] and l['principal']<l['original'] for l in loans)
    assert game.world.accounts[bid]['asset:internal_loan:company']==sum(l['principal'] for l in loans)
    assert game.world.accounts[bid]['asset:internal_interest:company']==sum(l['interest_due'] for l in loans)
    game.store.audit(game.world)
