import copy
import pytest
from test_game import game,act
from test_business import acquire
from test_campaign_product import client_for
from test_leadership import setup
from economic_simulation.management import Management,policy,growth_status
from economic_simulation.domain import Engine,RuleError
from economic_simulation.expansion import Expansion


def test_overview_is_read_only_and_groups_director_assignments(game):
    engine,leader,b,manager,second=setup(game,True)
    for bid in (b.id,second):leader.action('director_assign',dict(employment_id=manager.id,business_id=bid,limit=5000000),'test-director-'+bid)
    before=copy.deepcopy(engine.world.to_dict())
    view=Management(engine).overview()
    person=next(p for p in view['people'] if p['id']==manager.id)
    assert person['director'] and len(person['businesses'])==2
    assert len([p for p in view['people'] if p['id']==manager.id])==1
    assert view['business_count']==2
    assert len(next(r for r in view['rows'] if r['id']==b.id)['managers'])==1
    assert Management(engine).overview('does not exist')['rows']==[]
    assert before==engine.world.to_dict()


def test_overview_route_and_policy_forms(game):
    bid=acquire(game)
    with client_for(game) as c:
        response=c.get('/?page=management')
        assert response.status_code==200
        assert 'Management overview' in response.text and 'Policies by business' in response.text
        assert 'Create roles up to staff target' in response.text
        assert 'data-action="management_policy"' in response.text
        assert f'policy-{bid}' in response.text
        assert 'No businesses match' in c.get('/?page=management&search=unmatchable').text


def test_director_bulk_policy_preserves_business_budgets_and_authority(game):
    engine,leader,b,manager,second=setup(game,True)
    for bid in (b.id,second):leader.action('director_assign',dict(employment_id=manager.id,business_id=bid,limit=5000000),'assign-'+bid)
    other=leader.rules.company(second);b.authority.update(salary_limit=450000,spent=50000)
    Management(engine).action(dict(target=b.id,growth_budget=700000,cash_reserve=500000,hiring_role='cashier'))
    Management(engine).action(dict(target='director:'+manager.id,hiring='freeze',growth='review'))
    assert policy(b)['hiring']==policy(other)['hiring']=='freeze'
    assert policy(b)['growth_budget']==700000 and policy(other)['growth_budget']==0
    assert b.authority['salary_limit']==450000 and b.authority['spent']==50000
    assert leader.director(b.id)[0]['limit']==5000000


def test_hiring_freeze_and_growth_target_are_enforced(game):
    engine,leader,b,manager,_=setup(game)
    b.authority.update(enabled=True,salary_limit=600000,staffing_target=4)
    Management(engine).action(dict(target=b.id,hiring='freeze'))
    leader.start_day()
    assert len(leader.rules.staff(b.id,True))==3
    assert not any(r['action'] in ('hire','hire_for_role') for r in engine.world.systems.get('management_requests',[]))
    Management(engine).action(dict(target=b.id,hiring='grow',hiring_role='cashier'))
    before=len(engine.world.positions);leader.start_day()
    assert len(leader.rules.staff(b.id,True))==4 and len(engine.world.positions)==before+1
    leader.start_day();assert len(leader.rules.staff(b.id,True))==4
    engine.validate()


def growth_ready(game,mode='auto'):
    engine,leader,b,manager,_=setup(game)
    b.authority.update(enabled=True,salary_limit=600000,purchasing_limit=9000000)
    engine.post(b.id,'growth-seed-profit','Recorded revenue',{'asset:cash':10000000,'income:sales':-10000000})
    engine.world.date='2026-01-19'
    Management(engine).action(dict(target=b.id,hiring='freeze',growth=mode,growth_budget=10000000,cash_reserve=100000,growth_target=140))
    return engine,leader,b


def test_growth_proposal_requires_owner_and_budget_tracks_approval(game):
    engine,leader,b=growth_ready(game,'review')
    engine.world.systems['plans'].append(dict(id='test-license-plan',kind='license',person_id='unused',license='accounting',due='2026-12-01',status='active'))
    before=engine.world.cash(b.id);leader.start_day()
    assert engine.world.cash(b.id)==before
    request=next(r for r in engine.world.systems['management_requests'] if r['key']=='growth')
    leader.action('management_approve',dict(request_id=request['id']),'growth-owner-approve')
    assert growth_status(engine.world,b)['spent']==request['cost']
    assert growth_status(engine.world,b)['reason']=='Equipment expansion in progress'
    engine.validate()


def test_automatic_growth_respects_cash_floor_and_limit(game):
    engine,leader,b=growth_ready(game)
    Management(engine).action(dict(target=b.id,cash_reserve=engine.world.cash(b.id)))
    assert not growth_status(engine.world,b)['ready']
    leader.start_day();assert not any(p['kind']=='upgrade' for p in engine.world.systems['plans'])
    Management(engine).action(dict(target=b.id,cash_reserve=100000))
    b.authority['purchasing_limit']=100
    leader.start_day();assert not any(p['kind']=='upgrade' for p in engine.world.systems['plans'])
    b.authority['purchasing_limit']=9000000
    leader.start_day();assert len([p for p in engine.world.systems['plans'] if p['kind']=='upgrade'])==1
    leader.start_day();assert len([p for p in engine.world.systems['plans'] if p['kind']=='upgrade'])==1
    engine.validate()


def test_policy_and_authority_forms_preserve_each_other(game):
    bid=acquire(game)
    act(game,'management_policy',target=bid,hiring='freeze',growth='review',growth_budget=500000,stock=False)
    act(game,'delegation',business_id=bid,enabled=True,salary_limit=500000)
    b=next(b for b in game.world.businesses if b.id==bid)
    assert policy(b)['hiring']=='freeze' and not policy(b)['stock']
    with client_for(game) as c:
        response=c.post('/api/command',headers={'Origin':'http://testserver','X-Game-Token':'test-token'},json=dict(action='management_policy',args=dict(target=bid,growth_budget_dollars='7500'),revision=game.world.revision,command_id='policy-dollar-update'))
        assert response.status_code==200
    b=next(b for b in game.world.businesses if b.id==bid)
    assert policy(b)['growth_budget']==750000 and b.authority['enabled']
    assert policy(next(b for b in game.store.load().businesses if b.id==bid))['hiring']=='freeze'
    game.store.audit(game.world)


def test_invalid_policy_is_atomic(game):
    bid=acquire(game);before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'management_policy',target=bid,hiring='freeze',growth='invalid')
    assert game.world.to_dict()==before
