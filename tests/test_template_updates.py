import shutil

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader, select_autoescape

from economic_simulation import web
from economic_simulation.application import money
from test_game import game
from test_business import acquire


@pytest.mark.parametrize('version', [None, '0.4.3'])
def test_old_runtime_gets_restart_page_without_new_business_fields(version):
    env = Environment(loader=FileSystemLoader(web.ROOT / 'templates'),
                      autoescape=select_autoescape())
    env.filters['money'] = money
    context = {'page': 'business', 'business': {'industry': 'engineering'}}
    if version is not None:
        context['runtime_version'] = version
    html = env.get_template('game.html').render(**context)
    assert 'Restart Empire Manager' in html
    assert 'Play Empire Manager.cmd' in html
    assert '/static/game.js' not in html
    assert 'data-action=' not in html


def test_running_app_keeps_all_templates_from_startup(game, tmp_path, monkeypatch):
    bid = acquire(game, 2)
    root = tmp_path / 'presentation'
    shutil.copytree(web.ROOT / 'templates', root / 'templates')
    (root / 'static').mkdir()
    monkeypatch.setattr(web, 'ROOT', root)
    app = web.create_app(game, 'test-token', 'testserver')
    # Simulate an installation before either the root or its include is cached.
    (root / 'templates' / 'game.html').write_text('INCOMPATIBLE ROOT', encoding='utf-8')
    (root / 'templates' / 'engineering.html').write_text(
        '{{ missing_field / 60 }}', encoding='utf-8')
    with TestClient(app) as client:
        client.get('/?key=test-token')
        response = client.get('/', params={'page': 'business', 'business_id': bid})
    assert response.status_code == 200
    assert 'Contract value per work hour' in response.text
    assert 'Restart Empire Manager' not in response.text
    assert 'INCOMPATIBLE ROOT' not in response.text
