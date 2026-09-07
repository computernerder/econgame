import copy
import json
import random
from datetime import date, timedelta

import pytest

from economic_simulation.application import Game
from economic_simulation.banking import operate_bank, validate_bank, bank_view
from economic_simulation.business_models import OPENING_ROLES
from economic_simulation.business_rules import BusinessRules
from economic_simulation.domain import Engine, LEGACY_CONTENT_VERSION, CONTENT_VERSION, new_game
from economic_simulation.industries import SALES, PROJECTS, sales_capacity, project_capacity
from economic_simulation.persistence import Store
from economic_simulation.staffing import staffing_plan, hiring_view
from test_game import game, act, step
from test_campaign_product import client_for

NEW = ('trades', 'construction', 'gas_station', 'grocery', 'bank', 'car_dealership')


def purchase(game, industry):
    engine = Engine(copy.deepcopy(game.world))
    engine.post('personal', 'test-industry-capital', 'Test capital',
                {'asset:cash': 500000000, 'equity:capital': -500000000})
    game.store.commit(engine, game.world.revision)
    game.world = engine.world
    bid = next(b.id for b in game.world.businesses if b.industry == industry)
    act(game, 'acquire_business', business_id=bid, entity='personal')
    step(game, 3)
    return bid


@pytest.mark.parametrize('industry', NEW)
def test_new_industry_acquisition_operations_staffing_and_startup(game, industry):
    bid = purchase(game, industry)
    step(game, 8)
    b = next(b for b in game.world.businesses if b.id == bid)
    assert b.status == 'operating'
    assert sum(day['revenue'] for day in b.history) > 0
    plan = staffing_plan(game.world, bid)
    assert {r['role'] for r in plan['rows']} >= OPENING_ROLES[industry]
    for role in OPENING_ROLES[industry]:
        assert hiring_view(game.world, bid, role)['eligible']
    with client_for(game) as client:
        response = client.get('/', params={'page': 'business', 'business_id': bid})
        assert response.status_code == 200
        assert 'Restart Empire Manager' not in response.text
        assert 'Staffing' in response.text or 'staffing' in response.text
        if industry in PROJECTS:
            assert 'Next job quote' in response.text
            assert game.world.accounts[bid]['expense:project_materials'] > 0
        elif industry in SALES:
            assert 'data-action="restock"' in response.text
            assert game.world.accounts[bid]['expense:cost_of_sales'] > 0
        else:
            assert 'Customer deposits owed' in response.text
    act(game, 'start_business', industry=industry, name='New ' + industry, region='Rutland County')
    startup = game.world.businesses[-1]
    assert startup.status == 'developing'
    assert OPENING_ROLES[industry] <= {p.role for p in game.world.positions if p.business_id == startup.id}
    game.store.audit(game.world)
    restored = Game(game.store.path)
    assert json.dumps(restored.world.to_dict(), sort_keys=True) == json.dumps(game.world.to_dict(), sort_keys=True)
    restored.close()


def test_stock_operations_need_overlapping_roles_and_supervised_projects():
    for industry, (a, _, b, _, _, _) in SALES.items():
        buckets = {a: [0] * 24, b: [0] * 24}
        for h in range(8, 16):
            buckets[a][h] = 60
        for h in range(16, 24):
            buckets[b][h] = 60
        assert sales_capacity(industry, buckets) == 0
        buckets[b] = buckets[a][:]
        assert sales_capacity(industry, buckets) > 0
    assert project_capacity('trades', {'tradesperson': 0, 'apprentice': 480}) == 0
    assert project_capacity('construction', {'builder': 60, 'laborer': 480}) == 120


def test_bank_principal_deposits_interest_and_repayments_reconcile(game):
    bid = purchase(game, 'bank')
    engine = Engine(copy.deepcopy(game.world))
    b = next(b for b in engine.world.businesses if b.id == bid)
    rules = BusinessRules(engine)
    engine.world.date = '2025-02-03'
    operate_bank(rules, b, date(2025, 2, 3), {'teller': 480, 'loan_officer': 480}, 100, True)
    assert len(b.bank_loans) >= 2
    assert engine.world.accounts[bid]['asset:customer_loans'] == sum(l['principal'] for l in b.bank_loans)
    deposit_posts = [p for p in engine.postings if p['memo'] == 'Outside customers place deposits']
    assert deposit_posts and all(not any(a.startswith('income:') for a in p['lines']) for p in deposit_posts)
    origin_posts = [p for p in engine.postings if p['memo'] == 'Customer loan principal advanced']
    assert origin_posts and all(not any(a.startswith('income:') for a in p['lines']) for p in origin_posts)
    b.auto_lending = False
    for n in range(1, 400):
        day = date(2025, 2, 3) + timedelta(days=n)
        engine.world.date = day.isoformat()
        operate_bank(rules, b, day, {'teller': 0, 'loan_officer': 0}, 100, False)
        validate_bank(b, engine.world.accounts[bid])
    assert not bank_view(engine.world, b)['loans']
    assert engine.world.accounts[bid]['asset:customer_loans'] == 0
    assert engine.world.accounts[bid]['asset:loan_interest'] == 0
    assert engine.world.accounts[bid]['expense:deposit_interest'] > 0
    payments = [p for p in engine.postings if p['memo'] == 'Customer loan installment collected']
    assert payments and all(not any(a.startswith('income:') for a in p['lines']) for p in payments)


def test_recognized_old_campaign_upgrade_preserves_records_and_runs_once(tmp_path):
    engine = new_game()
    removed = {b.id for b in engine.world.businesses if b.industry in NEW}
    engine.world.businesses = [b for b in engine.world.businesses if b.id not in removed]
    engine.world.positions = [p for p in engine.world.positions if p.business_id not in removed]
    engine.world.employments = [e for e in engine.world.employments if e.employer not in removed]
    engine.world.content_version = LEGACY_CONTENT_VERSION
    path = tmp_path / 'old.sqlite3'
    Store(path, initial=engine)
    before = copy.deepcopy(engine.world.to_dict())
    upgraded = Game(path)
    after = upgraded.world.to_dict()
    assert after['accounts'] == before['accounts']
    for key in ('businesses', 'positions', 'employments', 'people', 'properties'):
        old = {row['id']: row for row in before[key]}
        now = {row['id']: row for row in after[key]}
        assert all(now[k] == v for k, v in old.items())
    assert set(NEW) <= {b.industry for b in upgraded.world.businesses}
    assert upgraded.world.content_version == CONTENT_VERSION
    upgraded.store.audit(upgraded.world)
    upgraded.close()
    again = Game(path)
    assert again.world.to_dict() == after
    assert len(list(tmp_path.glob('old.before-industries-*.sqlite3'))) == 1
    again.close()


def test_bank_credit_loss_and_cash_reserve_are_real_constraints(game):
    bid = purchase(game, 'bank')
    engine = Engine(copy.deepcopy(game.world))
    rules = BusinessRules(engine)
    b = next(b for b in engine.world.businesses if b.id == bid)
    engine.world.date = '2026-02-03'
    before = len(b.bank_loans)
    cash = engine.world.cash(bid)
    engine.post(bid, 'test-use-cash', 'Test operating expense', {'asset:cash': -cash, 'expense:test': cash})
    b.bank_reserve_percent = 100
    operate_bank(rules, b, date(2026, 2, 3), {'teller': 480, 'loan_officer': 480}, 100, True)
    assert len(b.bank_loans) == before  # New deposits cannot fund loans at 100% reserve.
    engine.post(bid, 'test-credit-capital', 'Test capital', {'asset:cash': 5000000, 'equity:capital': -5000000})
    engine.world.date = '2026-02-04'
    operate_bank(rules, b, date(2026, 2, 4), {'teller': 480, 'loan_officer': 480}, 100, True)
    loan = b.bank_loans[-1]
    engine.world.seed = next(seed for seed in range(10000) if random.Random(f'credit:{seed}:{loan["id"]}').randrange(100) < 3)
    b.auto_lending = False
    engine.world.date = loan['due']
    operate_bank(rules, b, date.fromisoformat(loan['due']), {'teller': 0, 'loan_officer': 0}, 100, False)
    assert loan['status'] == 'defaulted' and loan['principal'] == 0
    assert engine.world.accounts[bid]['expense:credit_losses'] >= loan['original']
    validate_bank(b, engine.world.accounts[bid])


def test_bank_unfunded_withdrawals_pause_time_and_keep_customer_liability(game):
    bid = purchase(game, 'bank')
    engine = Engine(copy.deepcopy(game.world))
    b = next(b for b in engine.world.businesses if b.id == bid)
    engine.post(bid, 'test-deposits', 'Test deposits',
                {'asset:cash': 10000000, 'liability:customer_deposits': -10000000})
    cash = engine.world.cash(bid)
    engine.post(bid, 'test-illiquid', 'Test liquidity shortage', {'asset:cash': -cash, 'expense:test': cash})
    engine.world.date = '2026-02-03'
    assert BusinessRules(engine).operate(b, date(2026, 2, 3))
    assert b.last_day['withdrawals_unpaid'] > 0
    assert engine.world.accounts[bid]['liability:customer_deposits'] <= -10000000
    assert any(d['title'] == 'Bank needs withdrawal liquidity' for d in engine.world.systems['decisions'])
