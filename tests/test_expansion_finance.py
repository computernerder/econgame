from test_game import game,act,step
from test_business import acquire
from economic_simulation.domain import Engine,RuleError
from economic_simulation.expansion import Expansion
import pytest


def test_startup_budget_and_staff_gate(game):
    q=Expansion(Engine(game.world)).opening_quote('retail')
    before=game.world.cash('personal');act(game,'start_business',industry='retail',name='Test Retail',region='Rutland County')
    b=game.world.businesses[-1];bid=b.id
    assert game.world.cash('personal')==before-q['total']
    assert game.world.accounts[bid]['asset:deposit']==q['deposit']
    assert game.world.accounts[bid]['expense:startup']==q['expense']
    assert not [e for e in game.world.employments if e.employer==bid]
    step(game,40);b=next(b for b in game.world.businesses if b.id==bid)
    assert b.status=='developing' and not game.world.accounts[bid].get('income:retail_sales',0)
    assert any('Opening needs staff'==d['title'] for d in game.world.systems['decisions'])
    game.store.audit(game.world)


def test_loan_is_not_revenue_and_repayment_reconciles(game):
    profit=game.view()['lifetime_profit'];act(game,'borrow',entity='personal',amount=1000000,months=12)
    assert game.view()['lifetime_profit']==profit
    loan=game.world.systems['loans'][-1];lid=loan['id']
    step(game,35);loan=game.world.systems['loans'][-1]
    assert loan['principal']<1000000 and game.world.accounts['personal']['expense:interest']>0
    total=loan['principal']+loan['interest_due'];act(game,'repay_loan',entity='personal',loan_id=lid,amount=total)
    assert game.world.systems['loans'][-1]['status']=='repaid'
    game.store.audit(game.world)


def test_collateral_cannot_be_reused_or_sold(game):
    p=game.world.properties[0];act(game,'buy',property_id=p.id)
    act(game,'borrow',entity='personal',property_id=p.id,amount=1000000,months=60)
    with pytest.raises(RuleError):act(game,'borrow',entity='personal',property_id=p.id,amount=1000000,months=60)
    with pytest.raises(RuleError):act(game,'sell',property_id=p.id)


def test_cancel_startup_recovers_cash_and_preserves_history(game):
    act(game,'start_business',industry='rental',name='Cancelled Rental',region='Rutland County')
    bid=game.world.businesses[-1].id
    act(game,'cancel_opening',business_id=bid)
    assert not any(b['id']==bid for b in game.view()['businesses'])
    assert next(b for b in game.world.businesses if b.id==bid).status=='closed'
    game.store.audit(game.world)


def test_divestment_preserves_staff_but_excludes_group(game):
    bid=acquire(game);ids=[e.person_id for e in game.world.employments if e.employer==bid]
    act(game,'sell_business',business_id=bid);step(game,14)
    assert not any(b['id']==bid for b in game.view()['businesses'])
    assert [e.person_id for e in game.world.employments if e.employer==bid]==ids
    assert not any(e['business_id']==bid for e in game.view()['employees'])
    with pytest.raises(RuleError):act(game,'restock',business_id=bid,units=10)
    step(game,3);game.store.audit(game.world)


def test_future_expansion_and_actual_tax_payments(game):
    bid=acquire(game);act(game,'fund_business',business_id=bid,amount=2000000)
    act(game,'upgrade_business',business_id=bid);assert next(b for b in game.world.businesses if b.id==bid).capacity_percent==100
    step(game,21);assert next(b for b in game.world.businesses if b.id==bid).capacity_percent==120
    step(game,10)
    assert game.world.accounts[bid]['expense:depreciation']>0
    assert game.world.accounts[bid]['expense:payroll_tax']>0
    assert 'liability:sales_tax' in game.world.accounts[bid]
    game.store.audit(game.world)
