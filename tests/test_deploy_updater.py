"""Exercise the real Bash controller with disposable files and a fake Docker daemon."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.name == 'nt' or not shutil.which('jq'), reason='Unraid updater requires Linux Bash/jq')
SCRIPT = Path(__file__).resolve().parents[1] / 'deploy/update-unraid.sh'
OLD = 'sha256:' + 'a' * 64
NEW = 'sha256:' + 'b' * 64
DIGEST = 'ghcr.io/computernerder/econgame@sha256:' + 'c' * 64

FAKE_DOCKER = r'''
import json, os, pathlib, sys
p = pathlib.Path(os.environ['FAKE_DOCKER_STATE'])
s = json.loads(p.read_text()); args = sys.argv[1:]
s['calls'].append(args)
root = pathlib.Path(s['root'])
old = 'sha256:' + 'a'*64; new = 'sha256:' + 'b'*64
digest = 'ghcr.io/computernerder/econgame@sha256:' + 'c'*64
labels = {'org.opencontainers.image.source':'https://github.com/computernerder/econgame',
          'org.opencontainers.image.revision':'d'*40, 'io.econgame.build-number':s.get('build','42.1')}
def done(value=None, code=0):
    p.write_text(json.dumps(s))
    if value is not None: print(value if isinstance(value,str) else json.dumps(value))
    sys.exit(code)
if args[:4] == ['compose','-p','econgame','config']:
    done({'services':{'econgame':{'container_name':'econgame','user':'99:100',
          'environment':{'EMPIRE_PUBLIC_URL':'http://game.lan'},
          'volumes':[{'target':'/data','source':str(root/'data')}]}}})
if args[:3] == ['compose','-p','econgame']:
    operation=args[3]
    if operation == 'stop': s['running']=False; done()
    if operation == 'rm': done()
    if operation == 'up':
        setting=(root/'source/.env').read_text()
        if digest in setting:
            s['image']=new
            (root/'data/save.txt').write_text('candidate migrated save')
        else: s['image']=old
        s['running']=True; done()
if args[0] == 'pull': done(code=1 if s.get('failure')=='pull' else 0)
if args[:2] == ['image','inspect']:
    done([{'Id':old if s.get('same') else new,'RepoDigests':[digest],'Config':{'Labels':labels}}])
if args[0]=='inspect':
    if '--format' in args: done('true')
    running_labels=dict(labels); running_labels['io.econgame.build-number']=s.get('old_build','local')
    done([{'Image':s['image'],'State':{'Running':s['running']},'Config':{'Labels':running_labels}}])
if args[0]=='exec':
    bad=(args[1]=='econgame-update-check' and s.get('failure')=='preflight') or (args[1]=='econgame' and s['image']==new and s.get('failure')=='live')
    done(code=1 if bad else 0)
if args[0]=='run':
    mount=args[args.index('--mount')+1]
    directory=pathlib.Path(mount.split('src=',1)[1].split(',dst=',1)[0])
    assert (directory/'save.txt').read_text()=='original save'
    (directory/'save.txt').write_text('preflight migrated copy')
    done('qa-container')
if args[0]=='start': s['running']=True; done()
if args[0] in ('stop','rm'): done()
done('Unexpected fake Docker call: '+repr(args), code=3)
'''


@pytest.fixture
def deployment(tmp_path):
    root = tmp_path / 'econgame'
    for folder in ('source', 'data', 'deploy'):
        (root / folder).mkdir(parents=True)
    (root / 'source/compose.yaml').write_text('services: {}\n')
    (root / 'source/.env').write_text('EMPIRE_PUBLIC_URL=http://game.lan\nEMPIRE_IMAGE=econgame:previous\n')
    (root / 'data/save.txt').write_text('original save')
    (root / 'deploy/enabled').touch()
    bin_dir = tmp_path / 'bin'; bin_dir.mkdir()
    executable = bin_dir / 'docker'
    executable.write_text('#!' + sys.executable + '\n' + FAKE_DOCKER)
    executable.chmod(0o755)
    tar = bin_dir / 'tar'
    tar.write_text('#!' + sys.executable + '\n' +
                   'import json, os, subprocess, sys\n' +
                   's=json.load(open(os.environ["FAKE_DOCKER_STATE"]))\n' +
                   'if s.get("failure")=="backup" and "-czf" in sys.argv: sys.exit(1)\n' +
                   'sys.exit(subprocess.call(["/usr/bin/tar", *sys.argv[1:]]))\n')
    tar.chmod(0o755)
    state = tmp_path / 'docker.json'
    state.write_text(json.dumps({'root': str(root), 'calls': [], 'image': OLD, 'running': True}))
    env = dict(os.environ, EMPIRE_APP_ROOT=str(root), FAKE_DOCKER_STATE=str(state),
               EMPIRE_HEALTH_ATTEMPTS='1', EMPIRE_HEALTH_INTERVAL='0',
               PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
    def run(**settings):
        data = json.loads(state.read_text()); data.update(settings); state.write_text(json.dumps(data))
        result = subprocess.run(['bash', str(SCRIPT)], env=env, text=True, capture_output=True, timeout=20)
        return result, json.loads(state.read_text())
    return root, run


def test_success_keeps_backup_and_pins_exact_digest(deployment):
    root, run = deployment
    result, state = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert state['image'] == NEW and state['running']
    assert DIGEST in (root / 'source/.env').read_text()
    assert 'EMPIRE_PUBLIC_URL=http://game.lan' in (root / 'source/.env').read_text()
    assert (root / 'data/save.txt').read_text() == 'candidate migrated save'
    record = json.loads((root / 'deploy/deployed.json').read_text())
    assert record['build'] == '42.1' and record['image'] == DIGEST
    assert (Path(record['backup']) / 'data-before.tar.gz').is_file()
    assert any('--network' in call and 'none' in call for call in state['calls'])


@pytest.mark.parametrize('settings', [{'same': True}, {'old_build': '43.1'}, {'old_build': '42.2'}, {'running': False}])
def test_unchanged_older_or_stopped_game_has_no_downtime(deployment, settings):
    root, run = deployment
    result, state = run(**settings)
    assert result.returncode == 0, result.stderr
    assert not any(call[:4] == ['compose', '-p', 'econgame', 'stop'] for call in state['calls'])
    assert (root / 'data/save.txt').read_text() == 'original save'


@pytest.mark.parametrize('settings', [{'failure': 'pull'}, {'build': 'local'}])
def test_unavailable_or_unidentified_image_does_not_stop_game(deployment, settings):
    root, run = deployment
    result, state = run(**settings)
    assert result.returncode != 0
    assert state['running'] and state['image'] == OLD
    assert not any(call[:4] == ['compose', '-p', 'econgame', 'stop'] for call in state['calls'])


def test_preflight_failure_restarts_untouched_old_game(deployment):
    root, run = deployment
    result, state = run(failure='preflight')
    assert result.returncode != 0
    assert state['running'] and state['image'] == OLD
    assert (root / 'data/save.txt').read_text() == 'original save'
    assert (root / 'deploy/failed-digest').read_text().strip() == DIGEST


def test_failed_live_start_restores_snapshot_and_preserves_failed_saves(deployment):
    root, run = deployment
    result, state = run(failure='live')
    assert result.returncode != 0, result.stdout
    assert state['running'] and state['image'] == OLD
    assert (root / 'data/save.txt').read_text() == 'original save'
    assert next((root / 'backups').glob('*/failed-data/save.txt')).read_text() == 'candidate migrated save'
    assert OLD in (root / 'source/.env').read_text()
    result, state = run()
    assert result.returncode == 0
    assert state['image'] == OLD  # Failed digest is not retried every five minutes.


def test_pause_stops_all_registry_and_docker_work(deployment):
    root, run = deployment
    (root / 'deploy/paused').touch()
    result, state = run()
    assert result.returncode == 0 and state['calls'] == []


def test_backup_failure_restarts_original_without_replacing_data(deployment):
    root, run = deployment
    result, state = run(failure='backup')
    assert result.returncode != 0
    assert state['running'] and state['image'] == OLD
    assert (root / 'data/save.txt').read_text() == 'original save'


def test_concurrent_check_does_not_start_another_deployment(deployment):
    import fcntl
    root, run = deployment
    with (root / 'deploy/update.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result, state = run()
    assert result.returncode == 0 and state['calls'] == []
