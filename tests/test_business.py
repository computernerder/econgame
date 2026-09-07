import copy
import calendar
import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from economic_simulation.application import Game
from economic_simulation.domain import Engine, RuleError, new_game
from economic_simulation.business_rules import BusinessRules, weekday_share
from economic_simulation.business_views import business_context, employee_view
from economic_simulation.persistence import Store
from economic_simulation.web import create_app
from test_game import act, step, game

def legacy_copy(path):
    source=Path(__file__).parents[1]/'qa'/'v1-campaign.sqlite3'
    if source.exists():
        shutil.copy2(source,path)
        return
    from economic_simulation.domain import V1_CONTENT_VERSION
    Store(path)
    with sqlite3.connect(path) as db:
        data=json.loads(db.execute('SELECT data FROM world').fetchone()[0])
        for key in ('businesses','people','positions','employments','business_rng_state','next_business_id','next_person_id','next_position_id','next_employment_id'):
            data.pop(key,None)
        data['properties']=[p for p in data['properties'] if p['status']!='business_asset']
        data['simulation_version']=1;data['content_version']=V1_CONTENT_VERSION
        db.execute('UPDATE world SET data=?',(json.dumps(data),))
        db.execute('PRAGMA user_version=1')

def acquire(game,index=0,parent='personal'):
    bid=game.world.businesses[index].id
    act(game,'acquire_business',business_id=bid,entity=parent)
    step(game,3)
    return bid

def test_weekday_shares():
    for year in (2027,2028):
        for month in range(1,13):
            assert sum(weekday_share(123457,date(year,month,d)) for d in range(1,calendar.monthrange(year,month)[1]+1))==123457

def test_acquisition_preserves_identity_and_escrow(game):
    b=game.world.businesses[0];bid=b.id
    people=[e.person_id for e in game.world.employments if e.employer==bid]
    cash=game.world.cash('personal');asking=b.asking
    act(game,'acquire_business',business_id=bid)
    assert game.world.cash('personal')==cash-asking-asking//100
    assert bid not in game.world.accounts
    before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'acquire_business',business_id=bid)
    assert game.world.to_dict()==before
    step(game,3)
    assert [e.person_id for e in game.world.employments if e.employer==bid]==people
    assert all(e.status=='active' for e in game.world.employments if e.employer==bid)
    assert game.world.accounts['personal'][f'asset:escrow:{bid}']==0
    game.store.audit(game.world)

@pytest.mark.parametrize('index,streams',[(0,{'retail_sales'}),(1,{'meal_sales'}),(2,{'hourly_consulting','support_retainer','project_work'}),(3,{'management_fees','maintenance_services'}),(4,{'rent'})])
def test_revenue_models(game,index,streams):
    bid=acquire(game,index);step(game,18)
    b=next(b for b in game.world.businesses if b.id==bid)
    actual={k for day in b.history for k,v in day['streams'].items() if v>0}
    assert streams<=actual
    assert game.world.accounts[bid]['expense:wages']>0
    game.store.audit(game.world)

def test_restaurant_needs_overlapping_shifts(game):
    bid=acquire(game,1)
    # Keep the intentional coverage gap instead of letting the manager fix it.
    act(game,'autonomy_policy',business_id=bid,scheduling=False)
    rules=BusinessRules(Engine(game.world))
    for emp in rules.staff(bid):
        if rules.position(emp.position_id).role=='server':
            act(game,'employment_terms',employment_id=emp.id,amount=emp.salary,weekly_hours=40,shift_start=16)
    step(game,7)
    b=next(b for b in game.world.businesses if b.id==bid)
    assert all(day['output']==0 for day in b.history[-7:])

def test_no_cashier_no_sales_and_stock_is_asset(game):
    bid=acquire(game);rules=BusinessRules(Engine(game.world))
    act(game,'management_policy',target=bid,hiring='freeze')
    emp=next(e for e in rules.staff(bid) if rules.position(e.position_id).role=='cashier')
    act(game,'end_employment',employment_id=emp.id)
    before=game.world.accounts[bid].get('expense:cost_of_sales',0)
    act(game,'restock',business_id=bid,units=5)
    assert game.world.accounts[bid].get('expense:cost_of_sales',0)==before
    step(game,7)
    b=next(b for b in game.world.businesses if b.id==bid)
    assert all(d['output']==0 for d in b.history[-7:])
    game.store.audit(game.world)

def test_engineering_invoice_collection_not_new_income(game):
    bid=acquire(game,2)
    act(game,'engineering_policy',business_id=bid,auto_projects=False)
    step(game,75)
    b=next(b for b in game.world.businesses if b.id==bid)
    assert not b.project_active
    assert game.world.accounts[bid]['income:project_work']==-b.contract_fee
    assert game.world.accounts[bid]['asset:unbilled']==0
    with game.store.connection() as db:
        rows=db.execute("SELECT j.id,l.account FROM journal j JOIN lines l ON j.id=l.journal_id WHERE j.entity=? AND j.memo='Customer invoice collected'",(bid,)).fetchall()
    assert rows and all(not r['account'].startswith('income:') for r in rows)
    act(game,'new_project',business_id=bid)
    assert next(b for b in game.world.businesses if b.id==bid).project_active
    game.store.audit(game.world)

def test_larger_business_contains_premises_and_rental():
    e=new_game();e.post('personal','test-capital','Test starting capital',{'asset:cash':50000000,'equity:capital':-50000000})
    bid=e.world.businesses[5].id;e.action('acquire_business',{'business_id':bid},'acquire-large')
    for _ in range(10):
        e=Engine(e.world);e.advance_day();e.validate()
    props=[p for p in e.world.properties if p.owner==bid]
    assert {p.status for p in props}=={'occupied','rented'}
    assert e.world.accounts[bid].get('expense:premises_rent',0)==0
    assert e.world.accounts[bid]['income:rent']<0
    assert e.world.accounts[bid]['income:retail_sales']<0

def test_nested_company_ownership_and_funding(game):
    bid=acquire(game)
    before=game.view()['total_wealth']
    act(game,'fund_business',business_id=bid,amount=10000000)
    assert game.view()['total_wealth']==before
    child=game.world.businesses[3].id
    act(game,'acquire_business',business_id=child,entity=bid);step(game,3)
    assert next(b for b in game.world.businesses if b.id==child).owner==bid
    assert child in game.view(bid)['group_entities']
    game.store.audit(game.world)

def test_business_can_buy_property(game):
    bid=acquire(game);act(game,'fund_business',business_id=bid,amount=12000000)
    prop=next(p for p in game.world.properties if p.status=='market')
    act(game,'buy',property_id=prop.id,entity=bid)
    assert next(p for p in game.world.properties if p.id==prop.id).owner==bid
    game.store.audit(game.world)

def test_hire_delay_train_leave_and_hidden_skills(game):
    bid=acquire(game);act(game,'create_position',business_id=bid,role='cashier')
    pos=game.world.positions[-1];person=next(p for p in game.world.people if p.candidate)
    act(game,'hire',position_id=pos.id,person_id=person.id,amount=260000,weekly_hours=40)
    eid=game.world.employments[-1].id
    assert game.world.employments[-1].status=='joining'
    step(game,3);assert game.world.employments[-1].status=='active'
    act(game,'train',employment_id=eid);step(game,14)
    person=next(p for p in game.world.people if p.id==person.id)
    assert 'retail' in person.demonstrated and person.training_until is None
    act(game,'leave',employment_id=eid)
    assert next(e for e in game.world.employments if e.id==eid).leave_until
    rules=BusinessRules(Engine(game.world))
    ee=next(e for e in game.world.employments if rules.position(e.position_id).role=='cashier' and any('Engineering' in q for q in rules.person(e.person_id).qualifications))
    view=employee_view(rules,ee)
    assert 'engineering' not in view['known_skills'] and 'engineering' in view['unknown_skills']
    game.store.audit(game.world)

def test_invalid_schedule_and_failed_acquisition_atomic(game):
    before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'acquire_business',business_id=game.world.businesses[5].id)
    assert game.world.to_dict()==before
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid)
    before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'employment_terms',employment_id=emp.id,amount=emp.salary,weekly_hours=60,shift_start=20)
    assert game.world.to_dict()==before

def test_all_screens_and_nonmutating_preview(game):
    bid=acquire(game);eid=next(e.id for e in game.world.employments if e.employer==bid)
    token='test-token';client=TestClient(create_app(game,token,'testserver'))
    client.get('/?key='+token)
    for page in ('overview','market','portfolio','finance','owner','activity','business_market','businesses','business','people','employee','organization'):
        response=client.get('/',params=dict(page=page,business_id=bid,employment_id=eid,scope=bid))
        assert response.status_code==200,(page,response.text)
    for b in game.world.businesses:
        assert client.get('/',params=dict(page='business',business_id=b.id)).status_code==200
    assert client.get('/?page=finance&consolidated=true').status_code==200
    before=game.world.to_dict()
    response=client.post('/api/preview',json=dict(action='business_policy',args=dict(business_id=bid,benefits='supportive',auto_restock=False),revision=game.world.revision,command_id='preview-test'),headers={'Origin':'http://testserver','X-Game-Token':token})
    assert response.status_code==200,response.text
    assert game.world.to_dict()==before

def test_v1_migration_preserves_campaign(tmp_path):
    path=tmp_path/'campaign.sqlite3';legacy_copy(path)
    with sqlite3.connect(path) as db:
        old=json.loads(db.execute('SELECT data FROM world').fetchone()[0]);journal=db.execute('SELECT * FROM journal').fetchall()
    store=Store(path);world=store.load()
    assert world.accounts==old['accounts'] and world.date==old['date']
    assert json.loads(json.dumps(world.rng_state))==old['rng_state']
    for original in old['properties']:
        current=next(p for p in world.to_dict()['properties'] if p['id']==original['id'])
        assert all(current[k]==v for k,v in original.items())
    with sqlite3.connect(path) as db:assert db.execute('SELECT * FROM journal').fetchall()==journal
    assert world.businesses and world.revision==old['revision']+1
    assert Store(path).load().revision==world.revision
    assert len(list(tmp_path.glob('*before-v2*')))==1
    store.audit(world)

def test_decision_costs_in_rolling_profit_and_dividend_elimination(game):
    bid=acquire(game,2)
    step(game,20)
    e=next(e for e in game.world.employments if e.employer==bid)
    before=next(b for b in game.view()['businesses'] if b['id']==bid)['profit_30']
    act(game,'train',employment_id=e.id)
    assert next(b for b in game.view()['businesses'] if b['id']==bid)['profit_30']==before-50000
    report=game.store.report('personal','2026-01-01',game.view()['group_entities'])
    wealth=game.view()['total_wealth']
    act(game,'distribute_profit',business_id=bid,amount=10000)
    after=game.store.report('personal','2026-01-01',game.view()['group_entities'])
    assert after['profit']==report['profit'] and after['cash_flow']==report['cash_flow']
    assert game.view()['total_wealth']==wealth
    game.store.audit(game.world)

def test_failed_migration_keeps_original(tmp_path,monkeypatch):
    path=tmp_path/'campaign.sqlite3';legacy_copy(path)
    before=path.read_bytes()
    def fail(self):raise RuleError('Injected migration failure')
    monkeypatch.setattr(BusinessRules,'initialize',fail)
    with pytest.raises(RuleError,match='Injected'):Store(path)
    assert path.read_bytes()==before

def test_reject_fractional_units(game):
    bid=acquire(game);before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'restock',business_id=bid,units=1.5)
    assert game.world.to_dict()==before

def test_payroll_friday_and_leave_reduces_output(game):
    bid=acquire(game)
    cashier=next(e for e in game.world.employments if e.employer==bid and next(p for p in game.world.positions if p.id==e.position_id).role=='cashier')
    act(game,'leave',employment_id=cashier.id)
    step(game,5)
    assert date.fromisoformat(game.world.date).weekday()==4
    assert game.world.accounts[bid]['liability:payroll']==0
    b=next(b for b in game.world.businesses if b.id==bid)
    assert all(d['output']==0 for d in b.history)
    assert game.world.accounts[bid]['expense:wages']>0
