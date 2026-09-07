import copy
from datetime import date
from test_game import game,act,step
from test_business import acquire
from test_leadership import setup
from test_specialists import add_specialist
from test_employee_management import request
from test_authority import contract
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.leadership import Leadership
from economic_simulation.time_off import TimeOff,blockers,review_status,absent
from economic_simulation.decision_inbox import items,inbox_view


def team(game):
    e,l,b,manager,_=setup(game)
    add_specialist(e,b.id,'cashier');add_specialist(e,b.id,'stocker')
    employee=next(emp for emp in l.rules.staff(b.id) if l.rules.position(emp.position_id).role=='cashier')
    return e,l,b,manager,employee


def test_three_day_trades_vacation_at_twenty_percent_is_manager_work(game):
    bid=acquire(game,6);e=Engine(copy.deepcopy(game.world));e.world.date='2026-04-01'
    l=Leadership(e);b=l.rules.company(bid)
    add_specialist(e,b.id,'tradesperson')
    manager=next(emp for emp in l.rules.staff(b.id) if l.rules.position(emp.position_id).role=='manager')
    employee=next(emp for emp in l.rules.staff(b.id) if l.rules.position(emp.position_id).role=='tradesperson')
    employee.leave_balance=10
    r=request(e,employee,start='2026-04-15',end='2026-04-17')
    from economic_simulation.time_off import coverage
    assert coverage(e.world,employee,r)==dict(hours=24.0,max_absent_percent=20,role_gap=False)
    assert review_status(e.world,r)['state']=='manager' and r not in blockers(e.world)
    TimeOff(e).review_pending()
    assert r['status']=='approved' and r['reviewer']==l.rules.person(manager.person_id).name
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    assert not any(row['kind']=='time_off' for row in items(e.world))
    e.validate()


def test_absent_manager_keeps_future_leave_queued_and_approves_on_return(game):
    e,l,b,manager,employee=team(game);manager.leave_until='2026-01-13'
    r=request(e,employee,start='2026-01-15',end='2026-01-16')
    before=copy.deepcopy(e.world.to_dict());review=review_status(e.world,r)
    assert e.events[-1]['title']=='Time-off request with manager' and not e.events[-1]['important']
    assert review['state']=='manager' and review['review_on']=='2026-01-14'
    assert not blockers(e.world) and not any(row['kind']=='time_off' for row in items(e.world))
    assert inbox_view(e.world)['manager_leave'][0]['review']['reviewer']==l.rules.person(manager.person_id).name
    assert e.world.to_dict()==before
    TimeOff(e).review_pending();assert r['status']=='pending'
    e.advance_day();assert r['status']=='pending'
    e.advance_day();assert r['status']=='approved'
    bank=employee.leave_balance;e.advance_day()
    assert absent(e.world,employee) and employee.leave_balance==bank-1
    TimeOff(e).tick();assert employee.leave_balance==bank-1
    assert sum(row['action']=='time_off_decide' for row in e.world.systems['authority_audit'])==1
    e.validate()


def test_no_reviewer_before_start_is_explained_and_blocks_skip(game):
    e,l,b,manager,employee=team(game);manager.leave_until='2026-01-14'
    r=request(e,employee,start='2026-01-15',end='2026-01-16')
    status=review_status(e.world,r)
    assert status['state']=='player' and 'unavailable before' in status['reason']
    assert l.rules.person(manager.person_id).name in status['reason'] and r in blockers(e.world)
    TimeOff(e).review_pending();assert r['status']=='pending'
    game.store.commit(e,game.world.revision);game.world=e.world
    act(game,'advance',period='week');game.worker.join(timeout=10)
    assert game.progress['completed']==0


def test_queued_request_rechecks_authority_and_staff_coverage(game):
    e,l,b,manager,employee=team(game);manager.leave_until='2026-01-13'
    r=request(e,employee,start='2026-01-15',end='2026-01-16')
    assert review_status(e.world,r)['state']=='manager'
    contract(e,b,staffing='prohibit')
    assert 'prohibits' in review_status(e.world,r)['reason'] and r in blockers(e.world)
    e.world.systems['authority_contracts'].clear()
    peer=next(emp for emp in l.rules.staff(b.id) if emp.id!=employee.id and l.rules.position(emp.position_id).role=='cashier')
    peer.leave_until='2026-01-17'
    assert 'coverage' in review_status(e.world,r)['reason'] and r in blockers(e.world)
    e.world.date='2026-01-14';TimeOff(e).review_pending();assert r['status']=='pending'


def test_explicit_manual_leave_policy_stays_in_player_inbox(game):
    e,l,b,manager,employee=team(game)
    TimeOff(e).action('time_off_policy',dict(business_id=b.id,auto_approve=False),'manual')
    r=request(e,employee,start='2026-01-15',end='2026-01-16')
    assert review_status(e.world,r)['state']=='player'
    assert 'policy requires player review' in review_status(e.world,r)['reason']
    TimeOff(e).review_pending();assert r['status']=='pending'
    game.store.commit(e,game.world.revision);game.world=e.world;before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html=client.get('/?page=inbox').text
        assert 'Why this needs you:' in html and 'Review time-off policy' in html
        assert '#time-off-policy' in html
        employee_html=client.get('/?page=employee&employment_id='+employee.id).text
        assert 'id="time-off-policy"' in employee_html
    assert game.world.to_dict()==before


def test_manager_queue_visible_without_becoming_a_player_decision(game):
    e,l,b,manager,employee=team(game);manager.leave_until='2026-01-13'
    r=request(e,employee,start='2026-01-15',end='2026-01-16')
    game.store.commit(e,game.world.revision);game.world=e.world;before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html=client.get('/?page=inbox').text
        assert 'With your managers' in html and '2026-01-14' in html
        assert 'id="time_off:'+r['id']+'"' not in html
        employee_html=client.get('/?page=employee&employment_id='+employee.id).text
        assert 'Assigned to management' in employee_html
    assert game.world.to_dict()==before


def test_queued_leave_does_not_stop_skip_and_replays_after_reload(game):
    e,l,b,manager,employee=team(game);manager.leave_until='2026-01-13'
    r=request(e,employee,start='2026-01-15',end='2026-01-16')
    game.store.commit(e,game.world.revision);game.world=e.world
    batch=Engine(copy.deepcopy(e.world))
    for _ in range(7):batch.advance_day()
    step(game,3);game.world=game.store.load();step(game,4)
    batch.world.revision=game.world.revision
    assert batch.world.to_dict()==game.world.to_dict()
    assert next(x for x in game.world.systems['time_off_requests'] if x['id']==r['id'])['status']=='completed'
    game.store.audit(game.world)


def test_long_skip_waits_for_manager_without_stopping_at_initial_request(game):
    e,l,b,manager,employee=team(game);manager.leave_until='2026-01-13'
    # Stock enough inventory before the manager goes away, so a separate
    # purchasing exception does not interrupt this leave-routing scenario.
    e.action('fund_business',dict(business_id=b.id,amount=10000000),'leave-test-funding')
    e.action('settle_obligations',dict(entity=b.id),'leave-test-settlement')
    e.action('restock',dict(business_id=b.id,units=1000),'leave-test-stock')
    r=request(e,employee,start='2026-01-15',end='2026-01-16')
    game.store.commit(e,game.world.revision);game.world=e.world
    act(game,'advance',period='week');game.worker.join(timeout=10)
    assert game.progress['completed']>=2,game.progress.get('reason')
    saved=next(x for x in game.world.systems['time_off_requests'] if x['id']==r['id'])
    assert saved['status'] in ('approved','completed') and saved['reviewer']==l.rules.person(manager.person_id).name
    game.store.audit(game.world)
