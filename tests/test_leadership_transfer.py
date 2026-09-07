import copy,json
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_leadership import setup
from test_campaign_product import client_for
from test_financial_detail import detail
from economic_simulation.domain import Engine,RuleError,World
from economic_simulation.leadership import Leadership,review
from economic_simulation.director_scope import assigned,workload
from economic_simulation.executives import Executives,records
from economic_simulation.authority import Authority
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_models import Position,Employment


def team(game):
    e,l,b,emp,other=setup(game,True)
    e.post('personal','test-capital','Test capital',{'asset:cash':100000000,'equity:capital':-100000000})
    e.action('start_business',dict(industry='office',name='Group Home Office',region=b.region),'new-office')
    office=e.world.businesses[-1];office.status='operating';office.opening_on=None
    for bid in (b.id,other):l.action('director_assign',dict(employment_id=emp.id,business_id=bid),'director-'+bid)
    return e,l,b,emp,office,other


def promote(e,emp,office,role='division_vp',**kwargs):
    return e.action('promote_home_office',dict(employment_id=emp.id,office_id=office.id,role=role,**kwargs),'promote-test')


@pytest.mark.parametrize('role',['home_office_director','division_vp','corporate_services_vp'])
def test_transfer_preserves_identity_leave_history_scope_and_spending(game,role):
    e,l,b,emp,office,other=team(game);old_id=emp.position_id;salary=emp.salary;due=review(e.world,emp)['due']
    before=copy.deepcopy(e.world.accounts);count=len(e.world.employments)
    emp.leave_balance=17;emp.sick_balance=6;emp.floating_balance=1
    e.action('time_off_request',dict(employment_id=emp.id,kind='vacation',start='2026-01-20',end='2026-01-21'),'test-leave')
    leave=e.world.systems['time_off_requests'][-1]
    e.action('time_off_decide',dict(request_id=leave['id'],choice='approve'),'approve-leave')
    old_leave=copy.deepcopy(leave);record=l.director(b.id,False)[0];record.update(day=e.world.date,spent=12345)
    key='director:'+emp.id
    Authority(e).set_contract(dict(target=key,period_limit=2000000,transaction_limit=1000000,financing='prohibit',horizon=7))
    contract=copy.deepcopy(Authority(e).contracts()[key]);Authority(e).record(b,record,emp,'restock',54321,54321,'Existing commitment')
    old_audit=copy.deepcopy(e.world.systems['authority_audit'])
    result=promote(e,emp,office,role)
    assert len(e.world.employments)==count and emp.employer==office.id and emp.position_id!=old_id
    assert l.rules.position(old_id).business_id==b.id and l.rules.position(old_id).role=='manager'
    assert not any(x.position_id==old_id and x.status in ('active','joining') for x in e.world.employments)
    assert (emp.leave_balance,emp.sick_balance,emp.floating_balance)==(17,6,1)
    assert {k:leave[k] for k in ('status','work_dates','used_dates','start','end')}=={k:old_leave[k] for k in ('status','work_dates','used_dates','start','end')}
    assert leave['entity']==office.id and review(e.world,emp)['due']==due
    assert {b.id,other,office.id}<=set(assigned(e.world,record)) and record['spent']==12345
    assert Authority(e).contracts()[key]==contract and e.world.systems['authority_audit']==old_audit
    assert Authority(e).spent(key)==54321 and record['authority_key']==key
    assert emp.salary>salary and e.world.accounts==before
    assert len([r for r in records(e.world) if r['employment_id']==emp.id and r['active']])==1
    assert l.reserved_minutes(emp)==90 and workload(e.world,emp)['minutes']==90
    assert 'old position is vacant' in result and 'Future payroll is paid by Group Home Office' in result
    assert any('promoted to' in item['event'] for item in l.rules.person(emp.person_id).history)
    e.validate()


@pytest.mark.parametrize('problem',['cash','inactive','non_office','unowned','developing','bad_role','shared','department','self','cycle','scope'])
def test_rejected_transfer_leaves_no_partial_changes(game,problem):
    e,l,b,emp,office,other=team(game);args={};role='division_vp'
    if problem=='cash':
        cash=e.world.cash(office.id);e.post(office.id,'spend','Test expense',{'asset:cash':-cash,'expense:test':cash})
    if problem=='inactive':emp.status='ended'
    if problem=='non_office':office=b
    if problem=='unowned':office.owner=None
    if problem=='developing':office.status='developing'
    if problem=='bad_role':role='cashier'
    if problem=='shared':e.world.systems['assignments'].append(dict(active=True,employment_id=emp.id))
    if problem=='department':e.world.systems['departments']={'test':dict(staff=[emp.id])}
    if problem=='self':args['supervisor_id']=emp.id
    if problem=='cycle':
        child=next(x for x in l.rules.staff(b.id) if x.id!=emp.id);child.supervisor_id=emp.id;args['supervisor_id']=child.id
    if problem=='scope':emp.weekly_hours=12
    before=copy.deepcopy(e.world.to_dict());postings=copy.deepcopy(e.postings);events=copy.deepcopy(e.events)
    with pytest.raises(RuleError):promote(e,emp,office,role,**args)
    assert e.world.to_dict()==before and e.postings==postings and e.events==events


def test_payroll_moves_prospectively_and_former_employee_remains_named(game):
    e,l,b,emp,office,other=team(game)
    l.rules.work(b,date.fromisoformat(e.world.date))
    game.store.commit(e,game.world.revision);game.world=e.world
    old_owed=game.world.accounts[b.id]['liability:payroll'];old_payroll=copy.deepcopy(detail(game,b.id)['payroll'])
    act(game,'promote_home_office',employment_id=emp.id,office_id=office.id,role='division_vp')
    assert game.world.accounts[b.id]['liability:payroll']==old_owed
    old=detail(game,b.id);new=detail(game,office.id)
    assert any(r['employment_id']==emp.id and r['name']==l.rules.person(emp.person_id).name for r in old['payroll'])
    assert any(r['employment_id']==emp.id and r['role']=='Manager' for r in old['payroll'])
    assert not any(r['employment_id']==emp.id for r in old['contracts'])
    assert len([r for r in new['contracts'] if r['employment_id']==emp.id])==1
    step(game,1)
    with game.store.connection() as db:
        rows=db.execute("SELECT entity FROM journal WHERE source=?",('payroll:'+emp.id+':'+game.world.date,)).fetchall()
    assert [row['entity'] for row in rows]==[office.id]
    assert detail(game,b.id)['payroll']==old_payroll or any(r['employment_id']==emp.id for r in detail(game,b.id)['payroll'])
    game.store.audit(game.world)


def test_local_replacement_manages_daily_work_and_vp_keeps_strategy(game):
    e,l,b,emp,office,other=team(game);oldpos=emp.position_id;promote(e,emp,office)
    assert all(x.id!=emp.id for x in l.rules.staff(b.id))
    replacement=l.rules.make_person('manager');new=Employment('replacement-manager',replacement.id,oldpos,b.id,340000,40,e.world.date)
    e.world.employments.append(new)
    assert l.actor(b,'restock')[1].id==new.id
    assert l.actor(b,'upgrade_business')[1].id==emp.id
    assert l.actor(b,'time_off_decide',dict(employment_id=new.id))[1].id==emp.id
    e.validate()


def test_home_office_director_delivers_real_priority_management(game):
    from economic_simulation.service_office import ServiceOffice
    e,l,b,emp,office,other=team(game);promote(e,emp,office,'home_office_director')
    service=ServiceOffice(e)
    service.action('department_configure',dict(provider=office.id,department='finance'),'dept')
    service.action('service_request',dict(provider=office.id,recipient=b.id,department='finance',priority=3),'task')
    task=e.world.systems['service_tasks'][-1];worked=task['worked'];cash=copy.deepcopy(e.world.accounts)
    Authority(e).set_contract(dict(target='director:'+emp.id,objective='preserve_cash'))
    Executives(e).tick()
    assert task['priority']==1 and task['worked']==worked and e.world.accounts==cash
    assert e.world.systems['authority_audit'][-1]['action']=='service_priority'
    assert e.world.systems['authority_audit'][-1]['actor']==emp.id
    contract=Authority(e).contracts()['director:'+emp.id]
    parent=copy.deepcopy(contract);parent['actions']['purchasing']='prohibit'
    e.world.systems['authority_contracts']['inherited-parent']=parent;contract['parent']='inherited-parent'
    task['priority']=3;Executives(e).tick();assert task['priority']==3


def test_vp_capital_allocation_uses_real_parent_cash_and_shared_daily_budget(game):
    from economic_simulation.authority import cash_forecast
    e,l,b,emp,office,other=team(game);promote(e,emp,office)
    e.action('transfer_business',dict(business_id=b.id,new_owner=office.id),'parent-office')
    cash=e.world.cash(b.id);e.post(b.id,'test-loss','Test expense',{'asset:cash':-cash,'expense:test':cash})
    record=l.director(b.id,False)[0];key=record['authority_key']
    Authority(e).set_contract(dict(target=key,transaction_limit=20000000,period_limit=40000000,horizon=1,growth='allow'))
    needed=-cash_forecast(e.world,b.id,14)['available'];assert needed>0
    record['spent']=record['limit']-1;before=e.world.cash(office.id)
    Executives(e).tick();assert e.world.cash(office.id)==before and e.world.cash(b.id)==0
    assert any(r['key']=='vp-funding:'+b.id for r in e.world.systems['management_requests'])
    record['limit']+=needed;spent=record['spent']
    Executives(e).tick()
    assert e.world.cash(office.id)==before-needed and e.world.cash(b.id)==needed
    assert record['spent']==spent+needed and Authority(e).spent(key)==needed
    e.validate()


def test_preview_ui_confirm_retry_and_persistence(game):
    e,l,b,emp,office,other=team(game);game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    payload=dict(action='promote_home_office',args=dict(employment_id=emp.id,office_id=office.id,role='division_vp'),revision=game.world.revision,command_id='promote-and-move',campaign_session=game.session_id)
    with client_for(game) as c:
        html=c.get('/?page=employee&employment_id='+emp.id).text
        assert 'Move to home-office leadership' in html and 'Group Home Office' in html and 'cash available' in html
        preview=c.post('/api/preview',json=payload);assert preview.status_code==200,preview.text
        assert 'monthly employer payroll' in preview.text and 'old position is vacant' in preview.text
        assert game.world.to_dict()==before
        confirmed=c.post('/api/command',json=payload);assert confirmed.status_code==200,confirmed.text
        after=copy.deepcopy(game.world.to_dict())
        assert c.post('/api/command',json=payload).status_code==200 and game.world.to_dict()==after
        for page in ('employee&employment_id='+emp.id,'management','organization&chart=employees&business_id='+office.id,'operations_center'):
            response=c.get('/?page='+page);assert response.status_code==200,response.text
            assert 'Division VP' in response.text or 'division_vp' in response.text
    assert game.store.load().to_dict()==json.loads(json.dumps(game.world.to_dict()))
    with pytest.raises(RuleError,match='already holds'):act(game,'promote_home_office',**payload['args'])
    game.store.audit(game.world)


def test_promotion_continues_identically_through_save_roundtrips(game):
    e,l,b,emp,office,other=team(game);promote(e,emp,office);saved=Engine(copy.deepcopy(e.world))
    for _ in range(3):
        e.advance_day();saved=Engine(World.from_dict(json.loads(json.dumps(saved.world.to_dict()))));saved.advance_day()
        assert json.dumps(e.world.to_dict(),sort_keys=True)==json.dumps(saved.world.to_dict(),sort_keys=True)


def test_changing_office_designation_replaces_position_without_duplicate_raise(game):
    e,l,b,emp,office,other=team(game);promote(e,emp,office,'division_vp')
    previous_position=emp.position_id;salary=emp.salary;count=len(e.world.employments)
    result=promote(e,emp,office,'corporate_services_vp')
    assert emp.salary==salary and len(e.world.employments)==count
    assert previous_position in e.world.systems['closed_positions']
    assert l.rules.position(emp.position_id).role=='corporate_services_vp'
    assert 'prior executive position is replaced' in result and 'old position is vacant' not in result
    e.validate()
