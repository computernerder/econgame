import copy
from datetime import date
import pytest
from economic_simulation.domain import Engine,RuleError
from economic_simulation.workforce import Workforce
from economic_simulation.shared_services import SharedServices
from test_game import game,act,step
from test_business import acquire


def test_policy_inherit_zero_reset_and_future_history(game):
    bid=acquire(game)
    act(game,'policy_set',entity='personal',medical='ppo',transport=10000,effective=game.world.date)
    act(game,'policy_set',entity=bid,transport=0,effective=game.world.date)
    wf=Workforce(Engine(game.world));values,sources,_=wf.effective(bid)
    assert values['transport']==0 and values['medical']=='ppo' and sources['transport']==bid
    act(game,'policy_reset',entity=bid,effective=game.world.date)
    act(game,'policy_set',entity='personal',transport=20000,effective=game.world.date)
    assert Workforce(Engine(game.world)).effective(bid)[0]['transport']==20000
    posted=copy.deepcopy(game.world.accounts)
    act(game,'policy_set',entity=bid,medical='hmo',effective='2026-02-01')
    assert Workforce(Engine(game.world)).effective(bid)[0]['medical']=='ppo'
    assert Workforce(Engine(game.world)).effective(bid,on='2026-02-01')[0]['medical']=='hmo'
    assert game.world.accounts==posted


def test_locked_policy_rejects_child_atomically(game):
    bid=acquire(game)
    act(game,'policy_set',entity='personal',medical='hmo',locked=['medical'],effective=game.world.date)
    before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'policy_set',entity=bid,medical='ppo',effective=game.world.date)
    assert game.world.to_dict()==before


def test_benefits_cost_enrollment_and_payroll(game):
    bid=acquire(game);act(game,'policy_set',entity=bid,medical='hmo',employer_share=50,dental='basic',vision=True,effective=game.world.date)
    emp=next(e for e in game.world.employments if e.employer==bid)
    wf=Workforce(Engine(game.world));policy=wf.effective(bid,emp)[0]
    assert wf.benefit_cost(emp,policy)==12500+21000+2200+1200
    step(game)
    emp=next(e for e in game.world.employments if e.id==emp.id)
    assert emp.enrollment['monthly_employer_cost']==36900
    game.store.audit(game.world)


def test_promotion_reporting_and_identity(game):
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid)
    original_person=emp.person_id;original_pos=emp.position_id
    act(game,'create_position',business_id=bid,role='manager');pos=game.world.positions[-1]
    act(game,'promote',employment_id=emp.id,position_id=pos.id,amount=400000)
    promoted=next(e for e in game.world.employments if e.id==emp.id)
    assert promoted.person_id==original_person and promoted.position_id!=original_pos
    before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'reporting',employment_id=emp.id,reports_to=pos.id)
    assert game.world.to_dict()==before


def test_shared_time_not_duplicated_and_group_cost_reconciles(game):
    source=acquire(game);target=acquire(game,1)
    emp=next(e for e in game.world.employments if e.employer==source and next(p for p in game.world.positions if p.id==e.position_id).role=='manager')
    act(game,'service_agreement',source=source,target=target,markup=20)
    act(game,'assign_staff',employment_id=emp.id,target=target,role='manager',start_minute=480,minutes=192)
    before=game.world.to_dict()
    with pytest.raises(RuleError):act(game,'assign_staff',employment_id=emp.id,target=target,role='manager',start_minute=600,minutes=200)
    assert game.world.to_dict()==before
    step(game,7)
    group=game.store.report('personal','2026-01-01',game.view()['group_entities'])
    expenses=sum(v for e in game.view()['group_entities'] for k,v in game.world.accounts[e].items() if k.startswith('expense:') and not k.startswith('expense:internal_'))
    assert group['expense']==expenses
    assert any(k.startswith('income:internal_services:') for k in game.world.accounts[source])
    game.store.audit(game.world)


def test_manager_authority_and_recruitment_lead_time(game):
    bid=acquire(game);act(game,'create_position',business_id=bid,role='cashier')
    act(game,'delegation',business_id=bid,enabled=True,salary_limit=200000,staffing_target=4,training_budget=0)
    step(game,7)
    assert len([e for e in game.world.employments if e.employer==bid and e.status in ('active','joining')])==3
    act(game,'delegation',business_id=bid,enabled=True,salary_limit=300000,staffing_target=4,training_budget=0)
    step(game,7)
    assert len([e for e in game.world.employments if e.employer==bid and e.status in ('active','joining')])==4
    count=len(game.world.people);act(game,'recruit',business_id=bid,role='cashier',channel='referral')
    assert len(game.world.people)==count
    step(game,3);assert len(game.world.people)==count+3
