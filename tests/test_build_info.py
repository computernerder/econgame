from fastapi.testclient import TestClient

from economic_simulation.build_info import build_info
from economic_simulation.server import Settings, create_server


def test_build_identity_defaults_and_rejects_invalid_header_values(monkeypatch):
    monkeypatch.delenv('EMPIRE_BUILD_NUMBER', raising=False)
    monkeypatch.delenv('EMPIRE_GIT_SHA', raising=False)
    assert build_info()['label'] == 'Build local'
    monkeypatch.setenv('EMPIRE_BUILD_NUMBER', 'bad\r\nHeader: injected')
    monkeypatch.setenv('EMPIRE_GIT_SHA', '<script>')
    assert build_info()['header'] == 'local'
    assert build_info()['revision'] == ''


def test_image_identity_appears_above_chapter_and_on_login(tmp_path, monkeypatch):
    monkeypatch.setenv('EMPIRE_BUILD_NUMBER', '42.2')
    monkeypatch.setenv('EMPIRE_GIT_SHA', 'abcdef0' + '1' * 33)
    monkeypatch.setenv('EMPIRE_ACCESS_KEY', 'build-test-only-access-key')
    monkeypatch.delenv('EMPIRE_ACCESS_KEY_FILE', raising=False)
    app = create_server(Settings(tmp_path, 'http://game.lan'))
    # Metadata belongs to this running process, not a changing environment/save.
    monkeypatch.setenv('EMPIRE_BUILD_NUMBER', '43.1')
    with TestClient(app, base_url='http://game.lan') as client:
        login = client.get('/login')
        assert 'Build 42.2' in login.text and 'abcdef0' in login.text
        assert login.headers['x-empire-build'] == '42.2-abcdef0'
        response = client.post('/login', data={'access_key': 'build-test-only-access-key'},
                               headers={'Origin': 'http://game.lan'})
        assert response.status_code == 200
        assert response.text.index('class="brand"') < response.text.index('Build 42.2') < response.text.index('CHAPTER 01')
        assert response.headers['x-empire-build'] == '42.2-abcdef0'
        assert client.get('/healthz').headers['x-empire-build'] == '42.2-abcdef0'
