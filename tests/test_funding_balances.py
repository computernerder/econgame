import copy
import json
from html import unescape
import re

from test_game import game, act
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.application import money
from economic_simulation.funding_balances import account_balances


def test_account_cash_is_separate_and_read_only(game):
    bid = acquire(game)
    game.world.accounts[bid]['asset:development_reserve'] = 999999
    game.world.accounts[bid]['asset:cash'] = -1234
    before = copy.deepcopy(game.world.to_dict())
    balances = account_balances(game.world)
    assert balances[bid]['cash'] == -1234
    assert balances[bid]['label'] == money(-1234)
    assert balances['personal']['cash'] == game.world.cash('personal')
    assert all(b.id not in balances for b in game.world.businesses if b.owner == 'market')
    assert game.world.to_dict() == before


def test_funding_forms_show_account_cash_and_escape_names(game):
    bid = acquire(game)
    game.world.businesses[0].name = '<Cash & Company>'
    client = client_for(game)
    before = copy.deepcopy(game.world.to_dict())
    for page in ('home_office', 'expansion', 'financing', 'property_workbench', 'owner'):
        response = client.get('/?page=' + page)
        assert response.status_code == 200
        html = response.text
        data = re.search(r'id="funding-accounts" hidden data-accounts="([^"]+)"', html)
        balances = json.loads(unescape(data.group(1)))
        assert balances[bid]['cash'] == game.world.cash(bid)
        assert '<Cash & Company>' not in html
        if page == 'home_office':
            assert 'data-account-label="Personal portfolio"' in html
            assert money(game.world.cash('personal')) + ' cash</option>' in html
    html = client.get('/?page=business&business_id=' + bid).text
    assert 'data-account-cash="personal"' in html
    assert 'data-account-cash="' + bid + '"' in html
    assert game.world.to_dict() == before


def test_progress_refreshes_all_accounts_after_funding(game):
    bid = acquire(game)
    client = client_for(game)
    before = client.get('/api/progress?scope=personal').json()['account_balances']
    act(game, 'fund_business', business_id=bid, amount=10000)
    after = client.get('/api/progress?scope=' + bid).json()['account_balances']
    assert after[bid]['cash'] == before[bid]['cash'] + 10000
    assert after['personal']['cash'] == before['personal']['cash'] - 10000
    assert after == account_balances(game.store.load())
    game.store.audit(game.world)
