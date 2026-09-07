"""Separate campaign files, read-only discovery, and safe active-save switching."""
import copy
import json
import os
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from .domain import Engine, RuleError
from .persistence import Store

ACTIONS={'new_campaign','open_campaign','rename_campaign','copy_campaign'}

def recovery_backup(path):
    return any(part in path.stem for part in ('.before-','.checkpoint','.manual-backup'))

def label(world,path):
    return world.systems.get('campaign_label') or world.owner_name+' — '+Path(path).stem

def checked_label(value):
    value=str(value or '').strip()
    if not 1<=len(value)<=80:raise RuleError('Use a game name of 1–80 characters.')
    return value

def campaign_path(game,name):
    root=game.store.path.resolve().parent
    if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name or not name.endswith('.sqlite3'):
        raise RuleError('Choose a saved game from My games.')
    target=root/name
    if target.resolve().parent!=root or target.is_symlink() or not target.is_file():
        raise RuleError('This saved game is unavailable. Refresh My games.')
    if recovery_backup(target) and target.resolve()!=game.store.path.resolve():
        raise RuleError('Recovery backups are not separate games. Choose a saved game from My games.')
    return target

def read_summary(path):
    # Never instantiate Store during browsing: it creates/migrates saves.
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1) as db:
        row=db.execute('SELECT data FROM world WHERE id=1').fetchone()
    if not row:raise ValueError('Missing campaign')
    data=json.loads(row[0]);settings=data.get('systems',{}).get('settings',{})
    owned={'personal','company'}
    businesses=data.get('businesses',[])
    for _ in businesses:
        added={b['id'] for b in businesses if b.get('owner') in owned}-owned
        if not added:break
        owned.update(added)
    return dict(file=path.name,name=data.get('systems',{}).get('campaign_label') or data['owner_name']+' — '+path.stem,
        owner=data['owner_name'],date=data['date'],mode=settings.get('mode','entrepreneur'),
        cash=data['accounts']['personal'].get('asset:cash',0),seed=data['seed'],
        businesses=sum(b['id'] in owned for b in businesses),
        modified=settings.get('modified',False),saved=datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),error='')

def library(game):
    rows=[];current=game.store.path.resolve()
    for path in current.parent.glob('*.sqlite3'):
        if path.is_symlink() or recovery_backup(path) and path.resolve()!=current:continue
        try:row=read_summary(path)
        except (sqlite3.Error,ValueError,KeyError,TypeError,OSError):
            row=dict(file=path.name,name=path.stem,error='Unable to read this saved game. Its file has been retained.',saved='')
        row['active']=path.resolve()==current;rows.append(row)
    rows.sort(key=lambda r:(not r['active'],r['name'].casefold(),r['file']))
    return dict(current=label(game.world,game.store.path),file=game.store.path.name,rows=rows)

def pointer(path):
    target=path.parent/'last-campaign.txt';temp=target.with_name('last-campaign-'+uuid.uuid4().hex+'.tmp')
    try:temp.write_text(path.name,encoding='utf-8');os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)

def preview(game,action,args):
    if action=='open_campaign':
        path=campaign_path(game,args.get('file'))
        try:row=read_summary(path)
        except (sqlite3.Error,ValueError,KeyError,TypeError,OSError) as exc:
            raise RuleError('This saved game could not be read. Your current game remains open.') from exc
        return 'Open '+row['name']+' at '+row['date']+'. Your current game is already saved; inactive games do not advance.'
    if action in ('rename_campaign','copy_campaign'):
        name=checked_label(args.get('campaign_name'))
        return ('Rename the current game to ' if action=='rename_campaign' else 'Create an independent saved copy named ')+name+'.'
    from .campaign_options import prepare_campaign
    prepare_campaign(args)
    if args.get('campaign_name') is not None:checked_label(args['campaign_name'])
    return 'Create and open a separate game. Existing games and progress remain saved.'

def execute(game,action,args,command_id,fingerprint):
    from .desktop import SaveLock
    # Game.execute owns the mutex and has checked running state and revision.
    preview(game,action,args)
    if action=='rename_campaign':
        engine=Engine(copy.deepcopy(game.world));name=checked_label(args.get('campaign_name'))
        engine.world.systems['campaign_label']=name;result='Game renamed to '+name+'.'
        game.store.commit(engine,game.world.revision,(command_id,fingerprint,result));game.world=engine.world
        return result
    if action=='open_campaign':
        path=campaign_path(game,args.get('file'))
        if path.resolve()==game.store.path.resolve():return 'This game is already open.'
    else:path=game.store.path.parent/('campaign-'+uuid.uuid4().hex[:12]+'.sqlite3')
    lock=SaveLock(path.with_suffix('.lock'))
    try:
        if action=='new_campaign':
            from .campaign_options import prepare_campaign
            initial=prepare_campaign(args)
            initial.world.systems['campaign_label']=checked_label(args.get('campaign_name',initial.world.owner_name+'’s game'))
            store=Store(path,initial=initial)
        elif action=='copy_campaign':
            with game.store.connection() as source,sqlite3.connect(path) as dest:source.backup(dest)
            store=Store(path)
        else:store=Store(path)
        world=store.load();store.audit(world)
        if action in ('new_campaign','copy_campaign'):
            engine=Engine(world)
            if action=='copy_campaign':engine.world.systems['campaign_label']=checked_label(args['campaign_name'])
            result=('Saved an independent copy: ' if action=='copy_campaign' else 'New campaign opened: ')+label(engine.world,path)+'. Your previous campaign remains saved.'
            store.commit(engine,world.revision,(command_id,fingerprint,result));world=engine.world
        else:result='Opened '+label(world,path)+'.'
        if action=='copy_campaign':
            # Cache the response in the source without touching its economic state or revision.
            with game.store.connection() as db:db.execute('INSERT INTO commands VALUES(?,?,?)',(command_id,fingerprint,result))
            return result
        pointer(path)
        previous=game.extra_save_lock
        game.store=store;game.world=world;game.extra_save_lock=lock;lock=None
        game.session_id=uuid.uuid4().hex
        game.progress=dict(running=False,completed=0,total=0,message=result)
        if previous:previous.close()
        return result
    finally:
        if lock:lock.close()
