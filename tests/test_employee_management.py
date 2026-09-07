import copy
import json
import sqlite3
from datetime import date
import pytest
from test_game import game,act,step
from test_business import acquire
from test_leadership import setup
from test_specialists import add_specialist
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import Engine,RuleError
from economic_simulation.business_rules import BusinessRules
from economic_simulation.workforce import Workforce
from economic_simulation.time_off import TimeOff,requests,balances,absent,coverage
from economic_simulation.employee_reporting import supervisor
from economic_simulation.organization import employee_tree
from economic_simulation.decision_inbox import items
from economic_simulation.employee_management_views import view


def request(e,emp,kind='vacation',start='2026-01-13',end='2026-01-15'):
    TimeOff(e).action('time_off_request',dict(employment_id=emp.id,kind=kind,start=start,end=end),'request')
    return requests(e.world,emp)[-1]


def approve(e,row):return TimeOff(e).action('time_off_decide',dict(request_id=row['id'],choice='approve'),'approval')


@pytest.mark.parametrize('kind',['vacation','sick','floating','parental','unpaid'])
def test_dated_absence_removes_actual_work_and_has_expected_pay(game,kind):
    e,leader,b,_,_=setup(game)
    emp=next(x for x in leader.rules.staff(b.id) if leader.rules.position(x.position_id).role=='cashier')
    row=request(e,emp,kind,end='2026-01-13')
    assert not absent(e.world,emp,'2026-01-13')
    assert any(x['kind']=='time_off' for x in items(e.world))
    approve(e,row)
    assert not absent(e.world,emp,'2026-01-12') and absent(e.world,emp,'2026-01-13')
    e.world.date='2026-01-13';TimeOff(e).tick()
    buckets,_=leader.rules.work(b,date.fromisoformat(e.world.date))
    assert sum(buckets['cashier'])==0
    payroll=next(p for p in e.postings if p['source']=='payroll:'+emp.id+':2026-01-13')
    assert (payroll['lines']['expense:wages']==0)==(kind=='unpaid')
    assert payroll['lines']['expense:benefits']>0
    assert not any(x['kind']=='time_off' for x in items(e.world))


def test_reservations_overlap_cancel_and_actual_consumption(game):
    e,leader,b,emp,_=setup(game);before=emp.leave_balance
    row=request(e,emp);approve(e,row)
    assert emp.leave_balance==before and balances(e.world,emp)[0]['reserved']==3
    with pytest.raises(RuleError,match='overlap'):request(e,emp,start='2026-01-15',end='2026-01-16')
    with pytest.raises(RuleError,match='overlap'):leader.rules.action('leave',dict(employment_id=emp.id,days=7),'legacy')
    TimeOff(e).action('time_off_cancel',dict(request_id=row['id']),'cancel')
    assert balances(e.world,emp)[0]['reserved']==0 and emp.leave_balance==before
    row=request(e,emp);approve(e,row)
    e.world.date='2026-01-13';TimeOff(e).tick();TimeOff(e).tick()
    assert emp.leave_balance==before-1 and row['used_dates']==['2026-01-13']
    with pytest.raises(RuleError):TimeOff(e).action('time_off_cancel',dict(request_id=row['id']),'retroactive')


def test_approval_rechecks_banks_and_holidays_do_not_consume_days(game):
    e,leader,b,emp,_=setup(game)
    emp.leave_balance=3
    first=request(e,emp)
    second=request(e,emp,start='2026-01-19',end='2026-01-21')
    approve(e,first)
    with pytest.raises(RuleError,match='Insufficient'):approve(e,second)
    e.world.date='2026-12-21'
    emp.leave_balance=10
    Workforce(e).action('policy_set',dict(entity=b.id,paid_holidays=True,effective=e.world.date),'holiday')
    row=request(e,emp,start='2026-12-24',end='2026-12-28')
    assert row['work_dates']==['2026-12-24','2026-12-28']


def test_primary_supervisor_can_be_in_home_office_and_identity_survives_promotion(game):
    bid=acquire(game)
    act(game,'start_business',industry='office',name='Group People Office',region='Rutland County')
    office=game.world.businesses[-1].id
    e=Engine(copy.deepcopy(game.world));e.world.date='2026-01-12';rules=BusinessRules(e)
    boss,_=add_specialist(e,office,'hr')
    manager=next(x for x in rules.staff(bid) if rules.position(x.position_id).role=='manager')
    before=copy.deepcopy(e.world.accounts)
    Workforce(e).action('reporting',dict(employment_id=manager.id,reports_to=boss.id),'report')
    assert supervisor(e.world,manager).id==boss.id and manager.employer==bid and e.world.accounts==before
    with pytest.raises(RuleError,match='cycle'):Workforce(Engine(copy.deepcopy(e.world))).action('reporting',dict(employment_id=boss.id,reports_to=manager.id),'cycle')
    with pytest.raises(RuleError):Workforce(e).action('reporting',dict(employment_id=manager.id,reports_to=manager.id),'self')
    tree=employee_tree(e.world,bid)
    assert boss.position_id in json.dumps(tree) and 'Group People Office' in json.dumps(tree)
    assert manager.position_id in json.dumps(employee_tree(e.world,office))
    original=manager.person_id
    rules.action('create_position',dict(business_id=bid,role='manager'),'vacancy')
    Workforce(e).action('promote',dict(employment_id=manager.id,position_id=e.world.positions[-1].id,amount=500000),'promote')
    assert manager.person_id==original and supervisor(e.world,manager).id==boss.id


def test_outside_employee_cannot_be_supervisor_and_departure_returns_to_leadership(game):
    e,leader,b,emp,_=setup(game)
    outsider=next(x for x in e.world.employments if x.status=='seller')
    with pytest.raises(RuleError):Workforce(e).action('reporting',dict(employment_id=emp.id,reports_to=outsider.id),'outside')
    other=next(x for x in leader.rules.staff(b.id) if x.id!=emp.id)
    # Remove the old position reporting edge before reversing the relationship.
    Workforce(e).action('reporting',dict(employment_id=other.id,reports_to=''),'root')
    Workforce(e).action('reporting',dict(employment_id=emp.id,reports_to=other.id),'report')
    leader.rules.action('end_employment',dict(employment_id=other.id),'end')
    TimeOff(e).tick()
    assert emp.supervisor_id is None


def test_delegated_approval_needs_coverage_and_available_supervisor(game):
    e,leader,b,manager,_=setup(game)
    second,_=add_specialist(e,b.id,'cashier')
    cashier=next(x for x in leader.rules.staff(b.id) if x.id!=second.id and leader.rules.position(x.position_id).role=='cashier')
    row=request(e,cashier,end='2026-01-13')
    TimeOff(e).action('time_off_policy',dict(business_id=b.id,auto_approve=True,max_days=3,max_absent_percent=100),'policy')
    b.authority['enabled']=True
    manager.leave_until='2026-01-12'
    TimeOff(e).tick();assert row['status']=='pending'
    manager.leave_until=None
    TimeOff(e).tick();assert row['status']=='approved'
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    own=request(e,manager,end='2026-01-13')
    TimeOff(e).tick();assert own['status']=='pending'
    assert coverage(e.world,manager,own)['role_gap']


def test_approved_leave_removes_shared_services_and_department_work(game):
    from economic_simulation.shared_services import SharedServices
    from economic_simulation.service_office import ServiceOffice
    e,leader,b,_,other=setup(game,two=True)
    emp,_=add_specialist(e,b.id,'accounting')
    office=ServiceOffice(e)
    office.action('department_configure',dict(provider=b.id,department='accounting',staff=emp.id),'configure')
    office.action('service_request',dict(provider=b.id,recipient=b.id,department='accounting'),'task')
    row=request(e,emp,end='2026-01-13');approve(e,row)
    e.world.date='2026-01-13';TimeOff(e).tick()
    buckets,_=leader.rules.work(b,date.fromisoformat(e.world.date));office.deliver(leader.rules,b,buckets)
    assert sum(buckets['accounting'])==0 and e.world.systems['service_tasks'][-1]['worked']==0
    shared=SharedServices(e)
    shared.action('service_agreement',dict(source=b.id,target=other,markup=0),'agreement')
    shared.action('assign_staff',dict(employment_id=emp.id,target=other,role='accounting',start_minute=480,minutes=60),'assignment')
    target=leader.rules.company(other);target_buckets={'accounting':[0]*24}
    shared.incoming(target,date.fromisoformat(e.world.date),target_buckets)
    assert sum(target_buckets['accounting'])==0


def test_benefits_edit_is_prospective_and_respects_parent_locks(game):
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid)
    old=copy.deepcopy(game.world.accounts)
    act(game,'employee_benefits',employment_id=emp.id,medical='ppo',employer_share=75,vacation_days=25,sick_days=10)
    assert game.world.accounts==old
    current=next(e for e in game.world.employments if e.id==emp.id)
    assert current.leave_balance==emp.leave_balance and Workforce(Engine(game.world)).effective(bid,current)[0]['vacation_days']==25
    act(game,'policy_set',entity='personal',medical='hmo',locked=['medical'],effective=game.world.date)
    with pytest.raises(RuleError):act(game,'employee_benefits',employment_id=emp.id,medical='ppo')
    act(game,'employee_benefits',employment_id=emp.id,inherit=True)
    assert not game.world.employments[[e.id for e in game.world.employments].index(emp.id)].policy_overrides


def test_new_names_are_unique_without_numbers_and_rng_deterministic(game):
    a=Engine(copy.deepcopy(game.world));b=Engine(copy.deepcopy(game.world))
    for engine in (a,b):
        for _ in range(150):BusinessRules(engine).make_person('cashier',candidate=True)
    names=[p.name for p in a.world.people]
    assert len({n.casefold() for n in names})==len(names)
    assert not any(c.isdigit() for n in names for c in n)
    assert a.world.to_dict()==b.world.to_dict()


def test_old_campaign_name_migration_preserves_identity_and_ledger(tmp_path):
    path=tmp_path/'old.sqlite3';g=Game(path);before=g.world.to_dict();g.close()
    with sqlite3.connect(path) as db:
        data=json.loads(db.execute('SELECT data FROM world').fetchone()[0])
        data['systems'].pop('employee_management_version')
        data['people'][0]['name']='Jamie Clarke 2';data['people'][1]['name']='Jamie Clarke 2'
        db.execute('UPDATE world SET data=?',(json.dumps(data),))
    g=Game(path)
    assert [p.id for p in g.world.people]==[p['id'] for p in before['people']]
    assert g.world.accounts==before['accounts']
    assert json.dumps(g.world.business_rng_state)==json.dumps(before['business_rng_state'])
    assert len({p.name for p in g.world.people})==len(g.world.people)
    assert list(tmp_path.glob('old.before-employee-management-*.sqlite3'))
    g.store.audit(g.world);snapshot=g.world.to_dict();g.close()
    g=Game(path);assert g.world.to_dict()==snapshot;g.close()


def test_employee_ui_inbox_and_read_models_do_not_mutate(game):
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid)
    act(game,'time_off_request',employment_id=emp.id,start='2026-01-12',end='2026-01-13',kind='vacation')
    before=copy.deepcopy(game.world.to_dict());client=client_for(game)
    for page in ('employee','people','inbox','workforce','organization'):
        response=client.get('/',params=dict(page=page,scope=bid,business_id=bid,employment_id=emp.id,chart='employees'))
        assert response.status_code==200
    html=client.get('/',params=dict(page='employee',scope=bid,employment_id=emp.id)).text
    assert 'Change primary supervisor' in html and 'Edit individual benefits' in html and 'Request time off' in html
    assert game.world.to_dict()==before


def test_pending_time_off_blocks_long_skip_but_not_single_day(game):
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid)
    act(game,'time_off_request',employment_id=emp.id,start='2026-01-12',end='2026-01-13')
    previous=game.world.date
    act(game,'advance',period='week');game.worker.join(timeout=10)
    assert game.world.date==previous and game.progress['blocked']
    assert 'time-off' in game.view()['progress']['links'][0]['label'].lower()
    step(game)
    assert game.world.date!=previous


def test_approved_leave_replays_and_loads_identically(game,tmp_path):
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid)
    act(game,'time_off_request',employment_id=emp.id,start='2026-01-05',end='2026-01-09')
    rid=game.world.systems['time_off_requests'][-1]['id'];act(game,'time_off_decide',request_id=rid,choice='approve')
    initial=copy.deepcopy(game.world);step(game,7)
    replay=Engine(initial)
    for _ in range(7):replay.advance_day()
    # Revisions count persisted steps; simulation state and postings otherwise match.
    replay.world.revision=game.world.revision
    assert replay.world.to_dict()==game.world.to_dict()
    assert json.dumps(game.store.load().to_dict(),sort_keys=True)==json.dumps(game.world.to_dict(),sort_keys=True)
    game.store.audit(game.world)


def test_vacation_accrual_delivers_full_annual_entitlement(game):
    e,leader,b,emp,_=setup(game)
    emp.leave_balance=0
    Workforce(e).action('policy_set',dict(entity=b.id,vacation_days=20,effective=e.world.date),'policy')
    # The policy is already effective throughout the next calendar year.
    for month in range(1,13):
        e.world.date=f'2027-{month:02d}-01'
        leader.rules.work(b,date.fromisoformat(e.world.date))
    assert emp.leave_balance==20


def test_unapproved_request_expires_without_absence_or_deduction(game):
    e,leader,b,emp,_=setup(game);before=emp.leave_balance
    row=request(e,emp)
    e.world.date='2026-01-13';TimeOff(e).tick()
    assert row['status']=='expired' and emp.leave_balance==before and not absent(e.world,emp)
    with pytest.raises(RuleError):approve(e,row)


def test_absent_manager_reduces_operating_management_capacity(game):
    e,leader,b,manager,_=setup(game)
    row=request(e,manager,end='2026-01-13');approve(e,row)
    e.world.date='2026-01-13';TimeOff(e).tick()
    buckets,factor=leader.rules.work(b,date.fromisoformat(e.world.date))
    assert sum(buckets['manager'])==0 and factor==75
    assert not leader.available(manager)


def test_cross_company_supervisor_approval_and_authority_restriction(game):
    from test_authority import contract
    e,leader,b,_,other=setup(game,two=True)
    employee=next(x for x in leader.rules.staff(b.id) if leader.rules.position(x.position_id).role=='cashier')
    add_specialist(e,b.id,'cashier')
    boss=next(x for x in leader.rules.staff(other) if leader.rules.position(x.position_id).role=='manager')
    Workforce(e).action('reporting',dict(employment_id=employee.id,reports_to=boss.id),'report')
    row=request(e,employee,end='2026-01-13')
    TimeOff(e).action('time_off_policy',dict(business_id=b.id,auto_approve=True,max_absent_percent=100),'policy')
    # A prohibition still prevents an otherwise covered, free approval.
    contract(e,b,staffing='prohibit')
    TimeOff(e).tick();assert row['status']=='pending'
    e.world.systems['authority_contracts'].clear()
    TimeOff(e).tick();assert row['status']=='approved'
    assert row['reviewer']==leader.rules.person(boss.person_id).name
    assert e.world.systems['authority_audit'][-1]['actor']==boss.id


def test_employee_requested_vacation_is_seeded_and_reaches_inbox(game):
    from economic_simulation.simulation_support import stable_roll
    e,leader,b,emp,_=setup(game)
    chosen=next(f'{year}-{month:02d}-01' for year in range(2026,2030) for month in range(1,13)
                if stable_roll(e.world,emp.id+':leave-request:'+f'{year}-{month:02d}-01',100)<12)
    e.world.date=chosen;other=Engine(copy.deepcopy(e.world))
    TimeOff(e).tick();TimeOff(other).tick()
    assert requests(e.world)==requests(other.world)
    assert any(r['employment_id']==emp.id and r['submitted_by']==leader.rules.person(emp.person_id).name for r in requests(e.world))
    assert any(row['kind']=='time_off' for row in items(e.world))
