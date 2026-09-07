import copy
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from test_game import game, act, step
from test_business import acquire
from economic_simulation.campaign_options import forecast, prepare_campaign
from economic_simulation.campaign_views import PAGES
from economic_simulation.domain import RuleError
from economic_simulation.persistence import Store
from economic_simulation.web import create_app


def client_for(game):
    client = TestClient(create_app(game, 'test-token', 'testserver'))
    client.get('/?key=test-token')
    client.headers.update({'origin': 'http://testserver', 'x-game-token': 'test-token'})
    return client


def test_every_campaign_screen_renders_controls_and_saved_records(game):
    bid = acquire(game)
    prop = game.world.properties[0]
    act(game, 'buy', property_id=prop.id)
    act(game, 'configure_spaces', property_id=prop.id, units=2)
    act(game, 'borrow', amount=1000000, months=12)
    step(game, 32)
    before = copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        for page in sorted(PAGES):
            for scope in ('personal', bid):
                response = client.get('/', params={'page': page, 'scope': scope})
                assert response.status_code == 200, (page, response.text)
                assert '<h1>' in response.text
                assert 'No records yet.' in response.text or '<form' in response.text or 'panel' in response.text
        assert 'data-action="start_business"' in client.get('/?page=expansion').text
        assert 'data-action="lease_space"' in client.get('/?page=spaces').text
        assert 'data-action="repay_loan"' in client.get('/?page=financing').text
        assert 'id="forecast-form"' in client.get('/?page=forecast').text
    assert game.world.to_dict() == before


def test_forecast_is_repeatable_and_never_changes_live_save(game):
    acquire(game)
    before = copy.deepcopy(game.world.to_dict())
    first = forecast(game.world, 3)
    assert first == forecast(game.world, 3)
    assert len(first['results']) == 3
    assert game.world.to_dict() == before
    assert game.store.load().to_dict() == json.loads(json.dumps(before))
    with pytest.raises(RuleError):
        forecast(game.world, 91)
    with client_for(game) as client:
        game.progress['running'] = True
        response = client.post('/api/forecast', json=dict(action='forecast', args={'days': 1}, revision=game.world.revision, command_id='forecast-test'))
        game.progress['running'] = False
        assert response.status_code == 409


@pytest.mark.parametrize('mode', ['entrepreneur', 'guided', 'sandbox'])
def test_scenarios_balance_and_preserve_options(tmp_path, mode):
    engine = prepare_campaign(dict(mode=mode, name='Test Owner'))
    store = Store(tmp_path / (mode + '.sqlite3'), initial=engine)
    world = store.load()
    store.audit(world)
    assert world.owner_name == 'Test Owner'
    assert world.systems['settings']['modified'] == (mode == 'sandbox')
    if mode == 'guided':
        assert any(b.owner == 'personal' for b in world.businesses)
        assert any(e.status == 'ended' for e in world.employments)


def test_campaign_switch_keeps_old_save_and_retries_same_command(game):
    old_path = game.store.path
    before = old_path.read_bytes()
    command_id = 'new-campaign-retry'
    args = dict(mode='sandbox', capital=50000000, name='New Owner')
    revision = game.world.revision
    result = game.execute('new_campaign', args, revision, command_id)
    new_path = game.store.path
    assert new_path != old_path
    assert old_path.read_bytes() == before
    assert game.execute('new_campaign', args, revision, command_id) == result
    assert game.store.path == new_path
    assert game.world.cash('personal') == 50000000
    assert (old_path.parent / 'last-campaign.txt').read_text() == new_path.name
    game.store.audit(game.world)


def test_preview_dollar_conversion_and_new_campaign_is_read_only(game):
    before = copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        response = client.post('/api/preview', json=dict(action='new_campaign', args=dict(mode='sandbox', name='Preview Owner', capital_dollars='500000.25'), revision=game.world.revision, command_id='preview-campaign'))
        assert response.status_code == 200, response.text
        assert game.world.to_dict() == before
        assert not list(game.store.path.parent.glob('campaign-*.sqlite3'))
        response = client.post('/api/command', json=dict(action='settings', args={'stop_cash_dollars': '1234.56'}, revision=game.world.revision, command_id='cash-alert-settings'))
        assert response.status_code == 200, response.text
        assert game.world.systems['settings']['stop_cash'] == 123456


def test_split_lease_deposit_and_termination_reconcile(game):
    pid = game.world.properties[0].id
    act(game, 'buy', property_id=pid)
    act(game, 'configure_spaces', property_id=pid, units=2)
    prop = next(p for p in game.world.properties if p.id == pid)
    act(game, 'lease_space', property_id=pid, space_id=prop.spaces[0]['id'], rent=100000, months=12)
    lease = game.world.systems['leases'][-1]
    assert game.world.accounts['personal']['liability:deposit:' + lease['id']] == -100000
    step(game, 32)
    act(game, 'end_lease', lease_id=lease['id'])
    step(game)
    lease = game.world.systems['leases'][-1]
    assert lease['status'] == 'ended'
    assert lease['deposit_remaining'] == 0
    game.store.audit(game.world)


def test_new_franchise_renders_before_first_day_and_royalties_reconcile(game):
    bid = acquire(game)
    act(game, 'fund_business', business_id=bid, amount=3000000)
    act(game, 'join_franchise', business_id=bid)
    with client_for(game) as client:
        response = client.get('/?page=franchises')
        assert response.status_code == 200
        assert 'data-action="renew_franchise"' in response.text
    step(game, 7)
    assert game.world.accounts[bid].get('expense:royalties', 0) > 0
    contract = game.world.systems['franchises'][-1]
    act(game, 'end_franchise', franchise_id=contract['id'])
    assert game.world.systems['franchises'][-1]['status'] == 'terminated'
    game.store.audit(game.world)
