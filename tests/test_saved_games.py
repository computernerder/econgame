import copy,json,sqlite3
from pathlib import Path
import pytest
from test_game import game,act,step
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import RuleError
from economic_simulation.persistence import Store
from economic_simulation.saved_games import library,preview
from economic_simulation.desktop import SaveLock

def test_independent_games_switch_and_resume_exact_state(game):
    first=game.store.path
    act(game,'rename_campaign',campaign_name='One store')
    step(game,2);before=game.world.to_dict()
    act(game,'new_campaign',campaign_name='Property portfolio',name='Robin',seed=129)
    second=game.store.path;assert first!=second
    assert game.world.seed==129 and game.world.date!=before['date']
    step(game,1);second_state=game.world.to_dict()
    act(game,'open_campaign',file=first.name)
    assert game.world.to_dict()==before
    assert (first.parent/'last-campaign.txt').read_text()==first.name
    act(game,'open_campaign',file=second.name)
    assert game.world.to_dict()==second_state
    assert len(library(game)['rows'])==2
    game.store.audit(game.world)

def test_copy_journal_and_progress_are_independent_and_retry_safe(game):
    act(game,'rename_campaign',campaign_name='Original');step(game,2)
    initial=game.world.to_dict();path=game.store.path
    revision=game.world.revision
    result=game.execute('copy_campaign',{'campaign_name':'Experiment'},revision,'copy-retry-test')
    assert game.execute('copy_campaign',{'campaign_name':'Experiment'},revision,'copy-retry-test')==result
    assert game.store.path==path and game.world.to_dict()==initial
    copies=[r for r in library(game)['rows'] if not r['active']];assert len(copies)==1
    act(game,'open_campaign',file=copies[0]['file'])
    assert game.world.accounts==initial['accounts'] and game.world.seed==initial['seed']
    game.store.audit(game.world);step(game,3)
    assert Store(path).load().to_dict()==initial

def test_library_read_does_not_migrate_or_list_backups(game):
    game.store.backup('checkpoint');game.store.backup('manual-backup')
    old=game.store.path.parent/'old.sqlite3'
    with game.store.connection() as source,sqlite3.connect(old) as dest:source.backup(dest)
    with sqlite3.connect(old) as db:
        data=json.loads(db.execute('SELECT data FROM world').fetchone()[0]);data['systems'].pop('land_market_version',None)
        db.execute('UPDATE world SET data=?',(json.dumps(data),))
    before=old.read_bytes();rows=library(game)['rows']
    assert {r['file'] for r in rows}=={game.store.path.name,'old.sqlite3'}
    assert before==old.read_bytes()

@pytest.mark.parametrize('name',['../outside.sqlite3','C:/outside.sqlite3','missing.sqlite3','test.checkpoint.sqlite3'])
def test_open_rejects_unlisted_paths_without_creating_files(game,name):
    snapshot=game.world.to_dict();files=set(game.store.path.parent.iterdir())
    with pytest.raises(RuleError):act(game,'open_campaign',file=name)
    assert snapshot==game.world.to_dict() and files==set(game.store.path.parent.iterdir())

def test_locked_or_corrupt_destination_preserves_current_game(game):
    act(game,'copy_campaign',campaign_name='Other');other=next(r for r in library(game)['rows'] if not r['active'])
    target=game.store.path.parent/other['file'];lock=SaveLock(target.with_suffix('.lock'))
    before=game.world.to_dict();old=game.store.path
    try:
        with pytest.raises(RuleError,match='already open'):act(game,'open_campaign',file=target.name)
        assert game.world.to_dict()==before and game.store.path==old
    finally:lock.close()
    broken=old.parent/'broken.sqlite3';broken.write_text('not a database')
    assert next(r for r in library(game)['rows'] if r['file']==broken.name)['error']
    with pytest.raises(RuleError,match='could not be read'):act(game,'open_campaign',file=broken.name)
    assert game.store.path==old

def test_desktop_lock_is_released_when_switching_and_reacquired_on_return(tmp_path):
    path=tmp_path/'original.sqlite3';lock=SaveLock(path.with_suffix('.lock'));g=Game(path,save_lock=lock)
    try:
        act(g,'new_campaign',campaign_name='Second')
        available=SaveLock(path.with_suffix('.lock'));available.close()
        act(g,'open_campaign',file=path.name)
        with pytest.raises(RuleError):SaveLock(path.with_suffix('.lock'))
    finally:g.close()
    available=SaveLock(path.with_suffix('.lock'));available.close()

def test_switch_requires_paused_time_and_preview_is_read_only(game):
    before=game.world.to_dict();files=set(game.store.path.parent.iterdir())
    preview(game,'new_campaign',dict(campaign_name='Preview',seed=17))
    preview(game,'copy_campaign',dict(campaign_name='Preview copy'))
    assert before==game.world.to_dict() and files==set(game.store.path.parent.iterdir())
    game.progress['running']=True
    try:
        with pytest.raises(RuleError,match='Pause'):act(game,'new_campaign',campaign_name='Not yet')
    finally:game.progress['running']=False

def test_library_ui_and_stale_tab_cannot_edit_another_game(game):
    with client_for(game) as client:
        page=client.get('/?page=games');assert page.status_code==200
        assert 'Save a copy' in page.text and 'My games' in page.text and 'campaign-session' in page.text
        old_session=game.session_id
        response=client.post('/api/command',json=dict(action='new_campaign',args=dict(campaign_name='Second'),revision=game.world.revision,campaign_session=old_session,command_id='web-new-game'))
        assert response.status_code==200
        before=game.world.to_dict()
        for endpoint in ('/api/command','/api/preview','/api/forecast'):
            r=client.post(endpoint,json=dict(action='profile',args=dict(name='Wrong campaign'),revision=game.world.revision,campaign_session=old_session,command_id='stale-web-game'))
            assert r.status_code==409 and 'different game' in r.text
        assert game.world.to_dict()==before
        assert client.post('/api/cancel',headers={'x-game-session':old_session}).status_code==409
        assert client.get('/api/progress').json()['campaign_session']==game.session_id

def test_game_labels_are_escaped_and_rename_preserves_identity(game):
    path=game.store.path;before=copy.deepcopy(game.world.accounts)
    act(game,'rename_campaign',campaign_name='<script>alert(1)</script>')
    assert path==game.store.path and before==game.world.accounts
    with client_for(game) as client:
        text=client.get('/?page=games').text
        assert '&lt;script&gt;' in text and '<script>alert(1)</script>' not in text
    with pytest.raises(RuleError):act(game,'rename_campaign',campaign_name=' ')

def test_custom_dotted_save_names_remain_selectable(tmp_path):
    g=Game(tmp_path/'my.original.sqlite3')
    try:
        act(g,'new_campaign',campaign_name='New')
        assert any(r['file']=='my.original.sqlite3' for r in library(g)['rows'])
        act(g,'open_campaign',file='my.original.sqlite3')
        assert g.store.path.name=='my.original.sqlite3'
    finally:g.close()
