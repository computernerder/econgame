import copy

import pytest

from test_game import game, act
from test_leadership import setup
from test_campaign_product import client_for
from economic_simulation.authority import Authority
from economic_simulation.domain import Engine, RuleError, World
from economic_simulation.leadership_activity import activity_view, notification, mark_reviewed


def director(game):
    engine, leader, business, employee, _ = setup(game)
    leader.action('director_assign', dict(employment_id=employee.id, business_id=business.id,
                                        limit=10000000), 'appoint-director')
    return engine, leader, business, employee


def buy(leader, b, key='stock'):
    return leader.perform(b,key,'restock',dict(business_id=b.id,units=10),10*b.unit_cost,
                          True,'Purchase 10 units of inventory')


def test_director_actions_show_real_results_cost_and_stable_identity(game):
    engine, leader, b, emp = director(game)
    before = engine.world.cash(b.id)
    person = leader.rules.person(emp.person_id)
    name = person.name
    assert buy(leader, b)
    row = activity_view(engine.world)['rows'][0]
    assert row['actor_name'] == name and row['actor_role'] == 'Director'
    assert row['cash'] == before-engine.world.cash(b.id) == 10*b.unit_cost
    assert row['business_id'] == b.id and row['status'] == 'completed'
    assert row['outcome'] and row['new']
    person.name = 'Renamed leader'
    leader.action('director_remove', dict(business_id=b.id), 'remove-director')
    assert activity_view(engine.world)['rows'][0]['actor_name'] == name
    assert activity_view(engine.world)['rows'][0]['actor_role'] == 'Director'
    assert notification(engine.world)['new'] == 1
    engine.validate()


def test_requests_are_not_completed_actions_and_read_does_not_approve(game):
    engine, leader, b, emp = director(game)
    leader.director(b.id)[0]['limit'] = 0
    cash = engine.world.cash(b.id)
    assert not buy(leader,b)
    assert not buy(leader,b)  # Updates the existing request, not a second notification.
    view = activity_view(engine.world)
    assert view['total'] == 1
    row = view['rows'][0]
    assert row['status'] == 'open' and row['actor'] == emp.id
    assert row['cash'] is None and row['due']
    assert notification(engine.world)['new'] == 0
    assert notification(engine.world)['pending'] == 1
    mark_reviewed(engine.world, 0)
    assert notification(engine.world)['pending'] == 1
    assert engine.world.cash(b.id) == cash
    leader.action('management_approve',dict(request_id=row['id']),'player-approve')
    row = activity_view(engine.world)['rows'][0]
    assert row['status'] == 'resolved' and row['resolved_by'] == 'Player'
    assert row['cash'] == cash-engine.world.cash(b.id)
    assert row['outcome'] and notification(engine.world)['new'] == 0
    assert not engine.world.systems.get('authority_audit')


def test_read_cursor_persistence_and_later_actions(game):
    engine, leader, b, _ = director(game)
    assert buy(leader,b)
    cursor = notification(engine.world)['cursor']
    assert buy(leader,b,'second')
    mark_reviewed(engine.world,cursor)
    assert notification(engine.world)['new'] == 1
    mark_reviewed(engine.world,0)
    assert notification(engine.world)['new'] == 1
    with pytest.raises(RuleError):mark_reviewed(engine.world,3)
    before = copy.deepcopy(engine.world.to_dict())
    activity_view(engine.world)
    notification(engine.world)
    assert engine.world.to_dict() == before
    game.store.commit(engine,game.world.revision)
    game.world=engine.world
    assert game.store.load().to_dict() == game.world.to_dict()
    assert notification(game.store.load())['new'] == 1
    game.store.audit(game.world)


def test_old_records_remain_visible_without_inventing_attribution(game):
    engine, leader, b, emp = director(game)
    assert buy(leader,b)
    audit = engine.world.systems['authority_audit'][0]
    for key in ('actor_name','actor_role','outcome'):audit.pop(key)
    leader.request(b,'legacy','restock',dict(business_id=b.id,units=1),b.unit_cost,'Old request')
    request = engine.world.systems['management_requests'][0]
    for key in ('actor','actor_name','actor_role'):request.pop(key)
    world=World.from_dict(engine.world.to_dict())
    completed=activity_view(world,status='completed')['rows'][0]
    assert completed['actor_name']==leader.rules.person(emp.person_id).name
    assert completed['actor_role']=='Delegated leader'
    pending=activity_view(world,status='open')['rows'][0]
    assert pending['actor_name']=='No leader recorded'
    assert pending['cash'] is None


def test_filter_pagination_and_scope_do_not_count_parent_charges_twice(game):
    engine, leader, b, emp = director(game)
    for i in range(29):
        assert buy(leader,b,str(i))
    records=engine.world.systems['authority_audit']
    records[0]['charged_to']=['manager:'+b.id,'director:'+emp.id]
    assert notification(engine.world)['new']==29
    view=activity_view(engine.world,b.id,emp.id,'completed')
    assert len(view['rows'])==25 and view['total']==29 and view['next']
    assert len(activity_view(engine.world,b.id,emp.id,'completed',2)['rows'])==4
    assert not activity_view(engine.world,'unknown')['rows']
    records[0]['business_id']=next(x.id for x in engine.world.businesses if not x.owner)
    assert notification(engine.world)['new']==28
    assert activity_view(engine.world)['total']==28


def test_notification_history_and_read_command_render_on_real_pages(game):
    engine, leader, b, emp=director(game)
    assert buy(leader,b)
    game.store.commit(engine,game.world.revision);game.world=engine.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        response=client.get('/?page=management')
        assert response.status_code==200,response.text
        assert 'Leadership activity' in response.text and 'Purchase 10 units' in response.text
        assert 'Mark current actions as read' in response.text
        for page in ('overview','business','finance'):
            response=client.get('/',params=dict(page=page,business_id=b.id,scope=b.id))
            assert response.status_code==200
            assert '>Leadership activity</a>' in response.text
            assert '1 unread action' not in response.text
        assert 'Recent leadership actions' in client.get('/?page=business&business_id='+b.id).text
        assert client.get('/api/progress').json()['leadership_activity']['new']==1
        assert game.world.to_dict()==before
        response=client.post('/api/command',json=dict(action='leadership_activity_read',args=dict(cursor=1),
                             revision=game.world.revision,command_id='read-leadership-actions'))
        assert response.status_code==200,response.text
        assert client.get('/api/progress').json()['leadership_activity']['new']==0
        assert game.store.load().systems['leadership_activity_seen']==1


def test_automatic_stock_order_appears_after_daily_step(game):
    engine, leader, b, emp=director(game)
    b.auto_restock=True;b.inventory_units=0
    inventory=engine.world.accounts[b.id].get('asset:inventory',0)
    engine.post(b.id,'clear-stock','Test stock depletion',{'asset:inventory':-inventory,'expense:cost_of_sales':inventory})
    engine.advance_day()
    rows=activity_view(engine.world,b.id,emp.id,'completed')['rows']
    assert any(r['detail']=='Automatic stock replenishment' and r['cash']>0 for r in rows)
    engine.validate()


@pytest.mark.parametrize('with_director', [True, False])
def test_automatic_project_policy_records_the_acting_leader_and_commitment(game, with_director):
    from test_parallel_projects import fixture_engine
    from economic_simulation.leadership import Leadership
    from economic_simulation.project_portfolio import jobs

    engine,b=fixture_engine(game,'engineering')
    leader=Leadership(engine)
    employee=leader.rules.staff(b.id)[0]
    if with_director:
        leader.action('director_assign',dict(employment_id=employee.id,business_id=b.id,limit=1000000),'assign-director')
    before=len(jobs(b));cash=engine.world.cash(b.id)
    record=leader.director(b.id)[0]
    spending=record['spent'] if record else 0
    assert leader.accept_project(b)
    row=activity_view(engine.world,b.id,status='completed')['rows'][0]
    assert len(jobs(b))==before+1 and engine.world.cash(b.id)==cash
    assert row['action']=='New Project' and row['cash']==0
    assert row['actor_name']==leader.rules.person(employee.person_id).name
    expected='director:'+employee.id if with_director else 'manager:'+b.id
    assert engine.world.systems['authority_audit'][-1]['charged_to']==[expected]
    if record:assert record['spent']==spending
    engine.validate()
