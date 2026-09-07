import copy
import json
import sqlite3
from datetime import date

import pytest
from test_game import game, act, step
from test_new_industries import purchase
from test_campaign_product import client_for
from test_authority import contract
from economic_simulation.domain import Engine,RuleError
from economic_simulation.application import Game
from economic_simulation.business_rules import BusinessRules
from economic_simulation.engineering import accept,next_offer
from economic_simulation.project_portfolio import jobs,remaining,deliver,planning_capacity
from economic_simulation.authority import Authority,cash_forecast
from economic_simulation.leadership import Leadership


def fixture_engine(game,industry):
    bid=purchase(game,industry)
    e=Engine(copy.deepcopy(game.world));b=next(b for b in e.world.businesses if b.id==bid)
    unbilled=e.world.accounts[bid].get('asset:unbilled',0)
    if unbilled:e.post(bid,'reset-test-order','Reset test fixture order',{'asset:unbilled':-unbilled,'income:fixture':unbilled})
    b.parallel_projects=[];b.project_active=True;b.project_progress=b.project_earned=0
    b.contract_minutes=b.contract_base_minutes=600;b.contract_fee=b.contract_base_fee=100000
    b.auto_projects=False;b.authority.setdefault('operating_policy',{})['jobs']=False
    e.world.date='2026-01-12'
    return e,b


@pytest.mark.parametrize('industry',['engineering','construction','trades','factory'])
def test_two_projects_share_real_daily_capacity_and_reload(game,industry):
    e,b=fixture_engine(game,industry);r=BusinessRules(e)
    accept(r,b)
    assert len(jobs(b))==2 and planning_capacity(e.world,b)>0
    before=remaining(b)
    r.operate(b,date.fromisoformat(e.world.date));e.validate()
    allocations=b.last_day['project_allocations']
    assert len(allocations)==2 and all(j['minutes']>0 for j in allocations)
    assert sum(j['minutes'] for j in allocations)==b.last_day['project_minutes']==before-remaining(b)
    if industry=='factory':assert b.last_day['project_minutes']<=b.last_day['output']*60
    else:assert b.last_day['project_minutes']+b.last_day['consulting_minutes']+b.last_day['retainer_minutes']<=b.last_day['qualified_capacity']
    assert e.world.accounts[b.id]['asset:unbilled']==sum(j['earned'] for j in jobs(b))
    game.store.commit(e,game.world.revision);game.world=e.world;game.store.audit(game.world)
    loaded=Game(game.store.path)
    try:assert loaded.world.to_dict()==json.loads(json.dumps(game.world.to_dict()))
    finally:loaded.close()


def test_additional_project_refused_without_staff_and_limit_is_enforced(game):
    e,b=fixture_engine(game,'engineering');r=BusinessRules(e)
    for emp in e.world.employments:
        if emp.employer==b.id:emp.leave_until='2026-02-28'
    before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError,match='Insufficient qualified capacity'):accept(r,b)
    assert e.world.to_dict()==before
    b.concurrent_project_limit=1
    with pytest.raises(RuleError,match='limit'):accept(r,b)


def test_each_contract_invoices_once_and_rounding_conserves_minutes(game):
    e,b=fixture_engine(game,'engineering');r=BusinessRules(e);accept(r,b);accept(r,b)
    original=jobs(b);fee=sum(j['fee'] for j in original)
    spent=0
    for day in range(50):
        e.world.date=f'2026-02-{day+1:02}' if day<28 else f'2026-03-{day-27:02}'
        progress,earned,allocation=deliver(r,b,97)
        assert progress==sum(j['minutes'] for j in allocation)<=97
        spent+=progress
        if not jobs(b):break
    assert not jobs(b) and spent==sum(j['minutes'] for j in original)
    assert sum(h['fee'] for h in b.project_history if h['number'] in {j['number'] for j in original})==fee
    assert len({i['id'] for i in b.receivables})==len(b.receivables)
    assert e.world.accounts[b.id]['asset:unbilled']==0
    assert deliver(r,b,100)==(0,0,[])
    e.validate()


def test_all_material_commitments_and_new_contract_value_are_checked(game):
    e,b=fixture_engine(game,'construction');r=BusinessRules(e)
    before=cash_forecast(e.world,b.id,1)['obligations'];offer=next_offer(e.world,b)
    accept(r,b)
    after=cash_forecast(e.world,b.id,1)['obligations']
    assert after-before==(offer['minutes']*b.material_hourly_cost+59)//60
    b.contract_base_fee=1000000
    key=contract(e,b,contracts='allow',project_limit=200000)
    preview=Engine(copy.deepcopy(e.world));preview.action('new_project',{'business_id':b.id},'third-project-preview')
    refusal=Authority(e).check(b,None,'new_project',{'business_id':b.id},0,preview.world)
    assert 'project contract value' in refusal


def test_automatic_multiple_jobs_and_required_approval(game):
    e,b=fixture_engine(game,'engineering');b.auto_projects=True
    r=BusinessRules(e);r.operate(b,date.fromisoformat(e.world.date))
    assert len(b.last_day['project_allocations'])==3
    e,b=fixture_engine_second(e,b)
    contract(e,b,contracts='approval')
    r=BusinessRules(e);r.operate(b,date.fromisoformat(e.world.date))
    assert len(jobs(b))==1
    assert any(x['action']=='new_project' and x['status']=='open' for x in e.world.systems['management_requests'])
    assert any(x['title']=='Owner approval needed' for x in e.pause_reasons)
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict());game._run(30)
    assert game.progress['completed']==0 and game.world.to_dict()==before


def fixture_engine_second(e,b):
    # Independent scenario from the existing engine, with balanced earned work.
    e=Engine(copy.deepcopy(e.world));b=next(x for x in e.world.businesses if x.id==b.id)
    unbilled=e.world.accounts[b.id]['asset:unbilled']
    e.post(b.id,'reset-second-test','Reset test fixture order',{'asset:unbilled':-unbilled,'income:fixture':unbilled})
    b.parallel_projects=[];b.project_progress=b.project_earned=0;b.project_active=True
    e.world.date='2026-01-13'
    return e,b


def test_ui_shows_multiple_jobs_combined_staffing_and_preview_is_read_only(game):
    e,b=fixture_engine(game,'engineering');accept(BusinessRules(e),b)
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        page=client.get('/',params=dict(page='business',business_id=b.id,scope=b.id))
        assert page.status_code==200,page.text
        assert '2 active projects' in page.text and 'Maximum concurrent projects' in page.text
        assert 'Total work remaining' in page.text and 'Active projects · 2 / 3' in page.text
        response=client.post('/api/preview',json=dict(action='new_project',args={'business_id':b.id},revision=game.world.revision,command_id='parallel-preview'))
        assert response.status_code==200,response.text
    assert game.world.to_dict()==before


def test_legacy_save_backup_preserves_contracts_and_accounts(game):
    purchase(game,'engineering');before=copy.deepcopy(game.world.to_dict())
    for b in before['businesses']:b.pop('parallel_projects');b.pop('concurrent_project_limit')
    with sqlite3.connect(game.store.path) as db:db.execute('update world set data=?',(json.dumps(before),))
    reopened=Game(game.store.path)
    try:
        assert reopened.world.accounts==before['accounts']
        for old,new in zip(before['businesses'],reopened.world.businesses):
            assert (new.contract_fee,new.contract_minutes,new.project_progress,new.project_earned)==tuple(old[k] for k in ('contract_fee','contract_minutes','project_progress','project_earned'))
        assert list(game.store.path.parent.glob('*before-parallel-projects*'))
        reopened.store.audit(reopened.world)
    finally:reopened.close()


def test_capacity_loss_retains_contracts_and_closure_writes_off_all_jobs(game):
    from economic_simulation.distress import Distress
    e,b=fixture_engine(game,'engineering');r=BusinessRules(e);accept(r,b)
    deliver(r,b,200)
    before=copy.deepcopy(jobs(b));unbilled=sum(j['earned'] for j in before)
    for emp in e.world.employments:
        if emp.employer==b.id:emp.leave_until='2026-02-28'
    r.operate(b,date.fromisoformat(e.world.date))
    assert jobs(b)==before and b.last_day['project_minutes']==0
    Distress(e).close(b,'Test closure')
    assert not jobs(b) and e.world.accounts[b.id]['asset:unbilled']==0
    assert e.world.accounts[b.id]['expense:project_writeoff']==unbilled
    e.validate()


def test_daily_and_skip_worker_agree_with_parallel_contracts(game,tmp_path):
    e,b=fixture_engine(game,'engineering');accept(BusinessRules(e),b)
    b.auto_projects=True;b.authority['operating_policy']['jobs']=True
    game.store.commit(e,game.world.revision);game.world=e.world
    copy_path=tmp_path/'skip.sqlite3'
    with sqlite3.connect(game.store.path) as src,sqlite3.connect(copy_path) as dst:src.backup(dst)
    skipped=Game(copy_path)
    try:
        skipped._run(5)
        count=skipped.progress['completed']
        assert count>0
        step(game,count)
        assert skipped.world.to_dict()==game.world.to_dict()
        skipped.store.audit(skipped.world)
    finally:skipped.close()


def test_planning_window_controls_admission_and_preserves_existing_work(game):
    e,b=fixture_engine(game,'engineering');r=BusinessRules(e)
    b.contract_base_minutes=planning_capacity(e.world,b)*25
    with pytest.raises(RuleError,match='Insufficient qualified'):accept(r,b)
    e.action('engineering_policy',dict(business_id=b.id,auto_projects=False,project_planning_days=60,concurrent_project_limit=4),'longer-planning-window')
    accept(r,b);assert len(jobs(b))==2
    existing=copy.deepcopy(jobs(b))
    e.action('engineering_policy',dict(business_id=b.id,auto_projects=False,project_planning_days=5,concurrent_project_limit=1),'shorter-planning-window')
    assert jobs(b)==existing
    e.validate()
