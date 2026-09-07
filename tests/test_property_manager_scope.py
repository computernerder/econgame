import copy
import json
import sqlite3

import pytest

from test_game import game,act
from test_leadership import setup
from test_authority import contract
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.authority import Authority
from economic_simulation.manager_defaults import owned_counties
from economic_simulation.routine_management import RoutineManagement,ready_property_care
from economic_simulation.property_services import PropertyServices
from economic_simulation.decision_inbox import items,inbox_view
from economic_simulation.leadership_activity import notification,activity_view
from economic_simulation.leadership import Leadership


def portfolio(game,two=False):
    e,l,b,manager,other=setup(game,two)
    e.action('fund_business',dict(business_id=b.id,amount=15000000),'portfolio-funding')
    p=min((p for p in e.world.properties if p.owner is None and p.status=='market'
           and p.region!=b.region and p.category!='land' and not p.id.startswith('covenant-')),key=lambda p:p.asking)
    e.action('buy',dict(property_id=p.id,entity=b.id),'portfolio-property')
    p.usable_area=600
    PropertyServices(e).initialize()
    e.world.systems['property_care'][p.id].update(cleanliness=30,grounds=90)
    return e,l,b,manager,p,other


def old_request(e,l,b,p):
    args=dict(property_id=p.id,kind='cleaning',visits=4,interval=7,provider='outside')
    l.request(b,'property-care:'+p.id+':cleaning','property_service',args,57600,
              'Book cleaning. The business is outside the organizational or geographic scope.')
    return e.world.systems['management_requests'][-1]


def test_manager_books_remote_owned_property_at_real_cost_without_question(game):
    e,l,b,manager,p,_=portfolio(game)
    assert p.region!=b.region and p.region in owned_counties(e.world,[b.id])
    cash=e.world.cash(b.id);personal=e.world.cash('personal')
    RoutineManagement(e).tick()
    job=e.world.systems['property_service_jobs'][-1]
    assert job['property_id']==p.id and job['paid']==57600 and job['visits']==4
    assert e.world.cash(b.id)==cash-57600 and e.world.cash('personal')==personal
    row=e.world.systems['authority_audit'][-1]
    assert row['actor']==manager.id and row['charged_to']==['manager:'+b.id]
    assert not any(r['status']=='open' for r in e.world.systems.get('management_requests',[]))
    e.validate()


def test_building_ownership_does_not_grant_tenant_or_parent_property_scope(game):
    e,l,b,_,p,other=portfolio(game,True)
    assert 'scope' in Authority(e).check(b,None,'restock',dict(business_id=other),100)
    other_property=next(x for x in e.world.properties if x.owner is None and x.status=='market')
    # Even in the newly covered county, an unrelated owner's property is excluded.
    other_property.region=p.region;other_property.owner='personal'
    refusal=Authority(e).check(b,None,'property_service',dict(property_id=other_property.id,kind='cleaning'),57600)
    assert 'organizational scope' in refusal


def test_explicit_county_scope_remains_binding(game):
    e,l,b,_,p,_=portfolio(game)
    key=contract(e,b,regions=[b.region])
    cash=e.world.cash(b.id);before=copy.deepcopy(e.world.systems['authority_contracts'])
    RoutineManagement(e).tick()
    assert not e.world.systems.get('property_service_jobs') and e.world.cash(b.id)==cash
    request=e.world.systems['management_requests'][-1]
    assert 'scope' in request['detail'] and not ready_property_care(e.world)
    assert e.world.systems['authority_contracts']==before
    contract(e,b,regions=[b.region,p.region])
    assert request['id'] in ready_property_care(e.world)
    RoutineManagement(e).recheck_property_care()
    assert request['status']=='resolved' and Authority(e).spent(key)==57600
    e.validate()


def test_local_manager_wins_and_director_can_cover_remote_asset(game):
    e,l,b,manager,p,other=portfolio(game,True)
    director=next(emp for emp in l.rules.staff(other) if l.rules.position(emp.position_id).role=='manager')
    l.action('director_assign',dict(employment_id=director.id,business_id=b.id,limit=10000000),'director-cover')
    assert l.actor(b)[1].id==manager.id
    manager.leave_until='2026-02-01'
    RoutineManagement(e).tick()
    assert e.world.systems['authority_audit'][-1]['actor']==director.id
    assert e.world.systems['property_service_jobs'][-1]['property_id']==p.id
    e.validate()


def test_explicit_parent_restriction_cannot_be_bypassed_by_default_manager(game):
    e,l,b,manager,p,other=portfolio(game,True)
    director=next(emp for emp in l.rules.staff(other) if l.rules.position(emp.position_id).role=='manager')
    l.action('director_assign',dict(employment_id=director.id,business_id=b.id,limit=10000000),'director-cover')
    contract(e,b,target='director:'+director.id,regions=[b.region])
    before=e.world.cash(b.id);RoutineManagement(e).tick()
    assert not e.world.systems.get('property_service_jobs') and e.world.cash(b.id)==before
    assert not ready_property_care(e.world)


@pytest.mark.parametrize('restriction',['purchase','monthly','cash','disabled','deferred','absent'])
def test_recheck_never_bypasses_real_restrictions(game,restriction):
    e,l,b,manager,p,_=portfolio(game);r=old_request(e,l,b,p)
    if restriction=='purchase':b.authority['purchasing_limit']=0
    elif restriction=='monthly':b.authority['routine_management']={'period_limit':57599}
    elif restriction=='cash':
        amount=e.world.cash(b.id)
        e.post(b.id,'fixture-liability','Dated obligation',{'expense:testing':amount,'liability:payable':-amount})
    elif restriction=='disabled':b.authority['routine_management']={'property_care':False}
    elif restriction=='deferred':r.update(status='deferred',deferred_until='2026-02-01')
    else:manager.leave_until='2026-02-01'
    before=copy.deepcopy(e.world.to_dict())
    assert not ready_property_care(e.world) and e.world.to_dict()==before
    RoutineManagement(e).recheck_property_care()
    assert not e.world.systems.get('property_service_jobs')
    assert r['status']==('deferred' if restriction=='deferred' else 'open')
    assert e.world.accounts==before['accounts']


def test_stale_request_moves_to_manager_queue_without_spending_on_read(game):
    e,l,b,_,p,_=portfolio(game);r=old_request(e,l,b,p)
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    assert ready_property_care(game.world)=={r['id']}
    assert not any(x['kind']=='management' for x in items(game.world))
    assert notification(game.world)['pending']==0
    assert any(row['status']=='manager_queue' for row in activity_view(game.world)['rows'])
    assert not Leadership(Engine(game.world)).view(b)['requests']
    view=inbox_view(game.world)
    assert len(view['manager_care'])==1 and view['manager_care'][0]['property']==p.name
    with client_for(game) as c:
        html=c.get('/?page=inbox').text
        assert 'With your managers' in html and 'Advance time for the manager' in html
    assert game.world.to_dict()==before
    next_engine=Engine(copy.deepcopy(game.world));next_engine.advance_day()
    game.store.commit(next_engine,game.world.revision);game.world=next_engine.world
    assert next(record for record in game.world.systems['management_requests'] if record['id']==r['id'])['status']=='resolved'
    assert len(game.world.systems['property_service_jobs'])==1
    assert game.store.load().to_dict()==json.loads(json.dumps(game.world.to_dict()))
    game.store.audit(game.world)


def test_multiple_rechecks_share_monthly_budget(game):
    e,l,b,_,p,_=portfolio(game)
    old_request(e,l,b,p)
    # A second needed service competes for the same total budget.
    e.world.systems['property_care'][p.id]['grounds']=10
    cost=PropertyServices(e).quote(p,'landscaping',4)['total']
    l.request(b,'property-care:'+p.id+':landscaping','property_service',
              dict(property_id=p.id,kind='landscaping',visits=4,interval=14,provider='outside'),cost,'Book grounds care.')
    b.authority['routine_management']={'period_limit':57600+cost-1}
    assert len(ready_property_care(e.world))==1
    RoutineManagement(e).recheck_property_care()
    assert len(e.world.systems['property_service_jobs'])==1
    assert sum(r['status']=='open' for r in e.world.systems['management_requests'])==1
    assert sum(r['commitment'] for r in e.world.systems['authority_audit'] if r['action']=='property_service')==57600
    e.validate()


def test_long_skip_rechecks_stale_care_and_matches_daily_steps(game,tmp_path):
    from economic_simulation.application import Game
    e,l,b,_,p,_=portfolio(game);old_request(e,l,b,p)
    # Disable unrelated optional activity; actual payroll and property costs continue.
    b.authority['operating_policy']={'hiring':'freeze','training':False,'growth':'off'}
    e.action('settle_obligations',dict(entity=b.id),'fixture-settlement')
    e.events=[];e.pause_reasons=[]
    game.store.commit(e,game.world.revision);game.world=e.world
    with game.store.connection() as source,sqlite3.connect(tmp_path/'daily.sqlite3') as dest:source.backup(dest)
    daily=Game(tmp_path/'daily.sqlite3')
    try:
        act(game,'advance',target='2026-01-14');game.worker.join(timeout=30)
        assert game.progress['completed']==2,game.progress
        for _ in range(2):
            act(daily,'advance',period='day');daily.worker.join(timeout=30)
        left=copy.deepcopy(game.world.to_dict());right=copy.deepcopy(daily.world.to_dict())
        left['revision']=right['revision']
        assert json.loads(json.dumps(left))==json.loads(json.dumps(right))
        assert len(game.world.systems['property_service_jobs'])==1
        game.store.audit(game.world);daily.store.audit(daily.world)
    finally:daily.close()


def test_long_skip_still_stops_for_explicit_county_restriction(game):
    e,l,b,_,p,_=portfolio(game);old_request(e,l,b,p)
    contract(e,b,regions=[b.region])
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    act(game,'advance',period='week');game.worker.join(timeout=30)
    assert game.progress['completed']==0 and game.progress['blocker']=='approval'
    # The command receipt is saved even when zero simulation days execute.
    before['revision']=game.world.revision
    # A blocked skip may remember its target, but cannot change the simulation.
    before['systems']['time_skip']={'target':game.progress['target']}
    assert game.world.to_dict()==before
    assert any(row['kind']=='management' for row in items(game.world))


def test_owner_repair_allowance_does_not_block_manager_preview(game):
    e,l,b,_,p,_=portfolio(game);r=old_request(e,l,b,p)
    e.action('property_work',dict(property_id=p.id,provider='owner',system='interior',kind='repair'),'owner-repair')
    e.world.systems['owner_decisions']={e.world.date:2}
    before=copy.deepcopy(e.world.to_dict())
    assert ready_property_care(e.world)=={r['id']}
    assert e.world.to_dict()==before
    e.advance_day()
    assert r['status']=='resolved'
    assert len(e.world.systems['property_service_jobs'])==1
    e.validate()
