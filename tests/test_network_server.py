import copy
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from economic_simulation.domain import RuleError
from economic_simulation.persistence import Store
from economic_simulation.server import Settings, access_key, active_save, create_server, public_origin

ORIGIN = 'http://192.168.1.3:8892'
KEY = 'test-only-network-access-key-0340'


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv('EMPIRE_ACCESS_KEY', KEY)
    monkeypatch.delenv('EMPIRE_ACCESS_KEY_FILE', raising=False)
    settings = Settings(tmp_path, ORIGIN)
    app = create_server(settings)
    with TestClient(app, base_url=ORIGIN) as client:
        yield app, client, settings


def sign_in(client, key=KEY):
    response = client.post('/login', data={'access_key': key}, headers={'Origin': str(client.base_url).rstrip('/')})
    assert response.status_code == 200
    return re.search(r'name="game-token" content="([^"]+)"', response.text).group(1)


def command(client, game, token, action, args=None, **overrides):
    payload = dict(action=action, args=args or {}, revision=game.world.revision,
                   campaign_session=game.session_id, command_id=f'network-{game.world.revision}-{action}')
    payload.update(overrides)
    return client.post('/api/command', json=payload, headers={'Origin': str(client.base_url).rstrip('/'), 'X-Game-Token': token})


@pytest.mark.parametrize('url', ['', 'ftp://game', 'http://game/path', 'http://user:pass@game', 'http://game?key=x', 'http://game#x', 'http://game:bad', 'http://*'])
def test_rejects_ambiguous_public_addresses(url):
    with pytest.raises(ValueError):
        public_origin(url)


def test_normalizes_browser_origin_and_requires_configuration(monkeypatch):
    assert public_origin('HTTP://GAME:80/') == 'http://game'
    assert public_origin('https://game:443') == 'https://game'
    assert public_origin('http://[::1]:8892') == 'http://[::1]:8892'
    monkeypatch.delenv('EMPIRE_PUBLIC_URL', raising=False)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_unauthenticated_clients_cannot_read_or_change_campaign(server):
    app, client, _ = server
    before = copy.deepcopy(app.state.game.world.to_dict())
    assert 'Server access key' in client.get('/').text
    assert client.get('/healthz').json() == {'status': 'ok'}
    assert client.get('/api/progress').status_code == 401
    assert client.get('/?key='+KEY).url.path == '/login'
    assert client.get('/static/login.css').status_code == 200
    assert client.get('/static/game.js', follow_redirects=False).status_code == 303
    assert client.post('/api/command', json={}).status_code == 401
    assert client.get('/', headers={'Host': 'evil.example'}).status_code == 403
    assert app.state.game.world.to_dict() == before


def test_login_separates_credentials_from_csrf_and_enforces_origin(server):
    app, client, _ = server
    assert client.post('/login', data={'access_key': KEY}).status_code == 403
    token = sign_in(client)
    assert token != KEY
    page = client.get('/')
    assert KEY not in page.text
    assert 'Sign out' in page.text and 'Shared server' in page.text
    assert page.headers['cache-control'] == 'no-store'
    payload = dict(action='profile', args={'name': 'LAN player'}, revision=0, command_id='network-profile-test')
    assert client.post('/api/command', json=payload).status_code == 403
    assert client.post('/api/command', json=payload, headers={'Origin': 'http://evil.example', 'X-Game-Token': token}).status_code == 403
    assert client.post('/api/command', json=payload, headers={'Origin': ORIGIN, 'X-Game-Token': KEY}).status_code == 403
    assert command(client, app.state.game, token, 'profile', {'name': 'LAN player'}).status_code == 200
    app.state.game.store.audit(app.state.game.world)


def test_failed_login_is_bounded_and_throttled(server):
    _, client, _ = server
    for _ in range(10):
        response = client.post('/login', data={'access_key': 'wrong—key'}, headers={'Origin': ORIGIN})
        assert response.status_code == 401
        assert KEY not in response.text
    response = client.post('/login', data={'access_key': KEY}, headers={'Origin': ORIGIN})
    assert response.status_code == 429 and response.headers['Retry-After'] == '60'


def test_logout_requires_same_origin_and_csrf(server):
    _, client, _ = server
    token = sign_in(client)
    assert client.get('/logout').status_code == 403
    assert client.post('/logout', data={'csrf': token}).status_code == 403
    assert client.post('/logout', data={'csrf': 'bad'}, headers={'Origin': ORIGIN}).status_code == 403
    assert client.post('/logout', data={'csrf': token}, headers={'Origin': ORIGIN}).url.path == '/login'
    assert client.get('/api/progress').status_code == 401


def test_https_proxy_address_sets_secure_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv('EMPIRE_ACCESS_KEY', KEY)
    monkeypatch.delenv('EMPIRE_ACCESS_KEY_FILE', raising=False)
    app = create_server(Settings(tmp_path, 'https://game.example'))
    with TestClient(app, base_url='https://game.example') as client:
        response = client.post('/login', data={'access_key': KEY}, headers={'Origin': 'https://game.example'}, follow_redirects=False)
        cookie = response.headers['set-cookie'].lower()
        assert all(flag in cookie for flag in ('secure', 'httponly', 'samesite=strict', 'max-age=43200'))
        assert client.get('/').status_code == 200


def test_two_browsers_keep_revision_and_campaign_switch_guards(server):
    app, first, _ = server
    game = app.state.game
    token = sign_in(first)
    # This client shares the running app, not ownership of its lifespan.
    second = TestClient(app, base_url=ORIGIN)
    other_token = sign_in(second)
    revision, session = game.world.revision, game.session_id
    assert command(first, game, token, 'profile', {'name': 'First player'}).status_code == 200
    stale = command(second, game, other_token, 'profile', {'name': 'Stale'}, revision=revision, command_id='stale-browser-command')
    assert stale.status_code == 409
    assert command(first, game, token, 'new_campaign', {'campaign_name': 'Server second game', 'name': 'New player', 'seed': 17}).status_code == 200
    assert command(second, game, other_token, 'profile', {'name': 'Wrong game'}, campaign_session=session, command_id='stale-campaign-command').status_code == 409
    second.close()


def test_library_lock_stays_held_across_campaign_switches(server):
    app, client, settings = server
    token = sign_in(client)
    assert command(client, app.state.game, token, 'new_campaign', {'campaign_name': 'Different save', 'name': 'Player', 'seed': 17}).status_code == 200
    with pytest.raises(RuleError, match='already open'):
        create_server(settings)


def test_restart_keeps_campaign_key_and_financial_state(tmp_path, monkeypatch):
    monkeypatch.delenv('EMPIRE_ACCESS_KEY', raising=False)
    monkeypatch.delenv('EMPIRE_ACCESS_KEY_FILE', raising=False)
    settings = Settings(tmp_path, ORIGIN)
    app = create_server(settings)
    key = (tmp_path/'access-key').read_text().strip()
    with TestClient(app, base_url=ORIGIN) as client:
        token = sign_in(client, key)
        assert command(client, app.state.game, token, 'new_campaign', {'campaign_name': 'Persistent game', 'name': 'Pat', 'seed': 27}).status_code == 200
        old_cookie = client.cookies.get('game_session')
        before = app.state.game.world.to_dict()
        path = app.state.game.store.path
    restarted = create_server(settings)
    with TestClient(restarted, base_url=ORIGIN) as client:
        assert (tmp_path/'access-key').read_text().strip() == key
        client.cookies.set('game_session', old_cookie)
        assert client.get('/api/progress').status_code == 401
        client.cookies.clear()
        sign_in(client, key)
        assert restarted.state.game.store.path == path
        assert restarted.state.game.world.to_dict() == before
        restarted.state.game.store.audit(restarted.state.game.world)


def test_failed_start_releases_library_lock(tmp_path, monkeypatch):
    monkeypatch.setenv('EMPIRE_ACCESS_KEY', 'short')
    monkeypatch.delenv('EMPIRE_ACCESS_KEY_FILE', raising=False)
    settings = Settings(tmp_path, ORIGIN)
    with pytest.raises(ValueError, match='16 to 512'):
        create_server(settings)
    monkeypatch.setenv('EMPIRE_ACCESS_KEY', KEY)
    with TestClient(create_server(settings), base_url=ORIGIN) as client:
        assert client.get('/healthz').status_code == 200


def test_external_secret_and_safe_campaign_pointer(tmp_path, monkeypatch):
    monkeypatch.delenv('EMPIRE_ACCESS_KEY', raising=False)
    secret = tmp_path/'secret.txt'
    secret.write_text(KEY)
    monkeypatch.setenv('EMPIRE_ACCESS_KEY_FILE', str(secret))
    assert access_key(tmp_path) == KEY
    (tmp_path/'last-campaign.txt').write_text('../outside.sqlite3')
    assert active_save(tmp_path) == tmp_path/'campaign.sqlite3'


def test_shutdown_waits_for_saved_day_and_releases_locks(tmp_path, monkeypatch):
    monkeypatch.setenv('EMPIRE_ACCESS_KEY', KEY)
    monkeypatch.delenv('EMPIRE_ACCESS_KEY_FILE', raising=False)
    app = create_server(Settings(tmp_path, ORIGIN))
    with TestClient(app, base_url=ORIGIN) as client:
        token = sign_in(client)
        game = app.state.game
        assert command(client, game, token, 'advance', {'period': 'month'}).status_code == 200
    assert not game.worker.is_alive()
    assert Store(game.store.path).load().to_dict() == game.world.to_dict()
    game.store.audit(game.world)


@pytest.mark.parametrize('origin', [ORIGIN, 'http://game.lan', 'https://game.example'])
def test_native_login_and_logout_preserve_origin(tmp_path, monkeypatch, origin):
    monkeypatch.setenv('EMPIRE_ACCESS_KEY', KEY)
    monkeypatch.delenv('EMPIRE_ACCESS_KEY_FILE', raising=False)
    app = create_server(Settings(tmp_path, origin))
    with TestClient(app, base_url=origin) as client:
        # A browser form POST under no-referrer sends Origin: null.
        # Preserve the real same-origin value without permitting null origins.
        page = client.get('/login')
        assert page.headers['referrer-policy'] == 'same-origin'
        assert '<form method="post" action="/login">' in page.text
        for rejected in (None, 'null', 'http://untrusted.example'):
            headers = {} if rejected is None else {'Origin': rejected}
            assert client.post('/login', data={'access_key': KEY}, headers=headers).status_code == 403
        token = sign_in(client)
        assert client.get('/').headers['referrer-policy'] == 'same-origin'
        for rejected in (None, 'null', 'http://untrusted.example'):
            headers = {} if rejected is None else {'Origin': rejected}
            assert client.post('/logout', data={'csrf': token}, headers=headers).status_code == 403
        result = client.post('/logout', data={'csrf': token}, headers={'Origin': origin})
        assert result.url.path == '/login'
        assert result.headers['referrer-policy'] == 'same-origin'
        assert client.get('/api/progress').status_code == 401


def test_local_launcher_keeps_key_out_of_referrers(server):
    from economic_simulation.web import create_app
    app, _, _ = server
    local = create_app(app.state.game, 'local-launch-key', 'testserver')
    with TestClient(local) as client:
        redirect = client.get('/?key=local-launch-key', follow_redirects=False)
        assert redirect.status_code == 303
        assert redirect.headers['referrer-policy'] == 'no-referrer'
        assert client.get('/').headers['referrer-policy'] == 'no-referrer'
