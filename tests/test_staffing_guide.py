import copy

import pytest

from test_game import game,act,step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.staffing import staffing_plan,hiring_view
from economic_simulation.domain import RuleError


def test_new_business_shows_opening_roles_and_workload_hours(game):
    act(game,'start_business',industry='retail',name='New Shop',region='Rutland County')
    bid=game.world.businesses[-1].id
    plan=staffing_plan(game.world,bid)
    rows={r['role']:r for r in plan['rows']}
    assert {r['role'] for r in plan['rows'] if r['required']}=={'manager','cashier','stocker'}
    assert all(r['status']=='Required role missing' for r in rows.values())
    assert rows['cashier']['target_hours']>rows['stocker']['target_hours']>0
    assert all(day['capacity']==0 for day in plan['projections'])


def test_guides_are_read_only_and_engineering_filters_qualifications(game):
    bid=acquire(game,2);before=copy.deepcopy(game.world.to_dict())
    plan=staffing_plan(game.world,bid);hire=hiring_view(game.world,bid,'engineer')
    assert '20 working days' in plan['workload']
    assert hire['eligible'] and hire['excluded']
    assert all(any('Engineering' in q for q in p['qualifications']) for p in hire['eligible'])
    assert game.world.to_dict()==before
    with client_for(game) as client:
        response=client.get('/',params={'page':'hiring','business_id':bid,'scope':bid,'role':'engineer'})
        assert response.status_code==200,response.text
        assert 'Engineering qualification required' in response.text
        assert 'data-action="hire_for_role"' in response.text
    assert game.world.to_dict()==before


def test_shift_mismatch_warns_before_more_hiring(game):
    bid=acquire(game,1)
    for emp in list(game.world.employments):
        if emp.employer==bid:
            role=next(p.role for p in game.world.positions if p.id==emp.position_id)
            if role=='server':act(game,'employment_terms',employment_id=emp.id,amount=emp.salary,weekly_hours=40,shift_start=16)
    plan=staffing_plan(game.world,bid)
    assert all(p['capacity']==0 for p in plan['projections'])
    assert 'overlapping shifts' in plan['summary']


def test_guided_hire_creates_one_vacancy_and_counts_incoming_staff(game):
    bid=acquire(game)
    guide=hiring_view(game.world,bid,'cashier')
    assert not guide['position_id']
    positions=len(game.world.positions);employments=len(game.world.employments)
    person=guide['eligible'][0]
    act(game,'hire_for_role',business_id=bid,role='cashier',person_id=person['id'],amount=guide['salary'],weekly_hours=guide['hours'])
    assert len(game.world.positions)==positions+1
    assert len(game.world.employments)==employments+1
    emp=game.world.employments[-1]
    assert emp.status=='joining'
    plan=staffing_plan(game.world,bid)
    row=next(r for r in plan['rows'] if r['role']=='cashier')
    assert row['joining']==1 and row['missing']==0
    step(game,3)
    assert next(e for e in game.world.employments if e.id==emp.id).status=='active'
    game.store.audit(game.world)


def test_failed_offer_does_not_leave_an_empty_position(game):
    bid=acquire(game);guide=hiring_view(game.world,bid,'cashier')
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError):
        act(game,'hire_for_role',business_id=bid,role='cashier',person_id=guide['eligible'][0]['id'],amount=1,weekly_hours=40)
    assert game.world.to_dict()==before


def test_guided_hire_reuses_license_restricted_vacancy(game):
    bid=acquire(game,2)
    act(game,'create_position',business_id=bid,role='engineer',required_license='professional_engineer')
    guide=hiring_view(game.world,bid,'engineer')
    assert guide['license']=='professional_engineer'
    assert any(p['reason']=='Required license missing or expired' for p in guide['excluded'])
    unqualified=next(p for p in guide['excluded'] if p['reason']=='Required license missing or expired')
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError):
        act(game,'hire_for_role',business_id=bid,role='engineer',position_id=guide['position_id'],person_id=unqualified['id'],amount=guide['salary'],weekly_hours=guide['hours'])
    assert game.world.to_dict()==before


def test_hiring_preview_shows_cost_without_creating_position(game):
    bid=acquire(game);guide=hiring_view(game.world,bid,'cashier');before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        response=client.post('/api/preview',json=dict(action='hire_for_role',args=dict(business_id=bid,role='cashier',person_id=guide['eligible'][0]['id'],weekly_hours=guide['hours'],amount_dollars=str(guide['salary']/100)),revision=game.world.revision,command_id='staffing-preview'))
        assert response.status_code==200,response.text
        assert 'Estimated monthly employer cost' in response.json()['message']
        assert 'Outside hiring support costs $300' in response.json()['message']
    assert game.world.to_dict()==before


def test_shared_staff_reduce_hours_gap_without_duplicate_hiring(game):
    source=acquire(game)
    act(game,'start_business',industry='retail',name='Shared Shop',region='Rutland County')
    target=game.world.businesses[-1].id
    stocker=next(e for e in game.world.employments if e.employer==source and next(p.role for p in game.world.positions if p.id==e.position_id)=='stocker')
    before=next(r for r in staffing_plan(game.world,target)['rows'] if r['role']=='stocker')
    act(game,'service_agreement',source=source,target=target)
    act(game,'assign_staff',employment_id=stocker.id,target=target,role='stocker',start_minute=480,minutes=120)
    after=next(r for r in staffing_plan(game.world,target)['rows'] if r['role']=='stocker')
    assert after['shared_hours']==10
    assert after['missing']==before['missing']-10
    assert after['required'] and after['status']=='Required role missing'
    assert next(r for r in staffing_plan(game.world,source)['rows'] if r['role']=='stocker')['shared_hours']==-10
