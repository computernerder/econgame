import copy
import json
import sqlite3
from datetime import date,timedelta
import pytest
from test_game import game,act
from test_property_manager_scope import portfolio
from test_specialists import add_specialist
from test_authority import contract
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.internal_property_services import InternalPropertyServices
from economic_simulation.operating_automation import OperatingAutomation
from economic_simulation.property_operations import PropertyOperations,systems_for
from economic_simulation.property_development import brokerage,representation
from economic_simulation.service_office import ServiceOffice
from economic_simulation.authority import cash_forecast


def team(game):
    e,l,b,manager,p,_=portfolio(game)
    e.action('start_business',dict(industry='office',name='Property Home Office',region=p.region,entity='personal'),'office')
    office=e.world.businesses[-1];office.status='operating';office.opening_on=None
    maintenance,person=add_specialist(e,office.id,'maintenance')
    person.skills['maintenance']=100;person.morale=person.engagement=90;person.burnout=0
    agent,person=add_specialist(e,office.id,'real_estate_agent')
    person.skills['service']=100;person.morale=person.engagement=90;person.burnout=0
    b.authority['purchasing_limit']=1000000
    return e,l,b,manager,p,office,maintenance,agent


def request(e,p,system='interior'):
    PropertyOperations(e).ensure(p)[system]['condition']=25
    ticket=dict(id='repair-'+system,property_id=p.id,system=system,severity='routine',status='open',created=e.world.date,due='2026-02-01')
    e.world.systems.setdefault('property_requests',[]).append(ticket)
    return ticket


def deliver(e,l,office,days=6):
    for _ in range(days):
        buckets,_=l.rules.work(office,date.fromisoformat(e.world.date))
        initial=sum(e.named_initial[office.id].values())
        PropertyOperations(e).deliver(l.rules,office,buckets)
        ServiceOffice(e).deliver(l.rules,office,buckets)
        assert 0<=sum(e.named_capacity[office.id].values())<=initial
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()


def test_home_office_repairs_use_named_staff_and_real_allocated_labor(game):
    e,l,b,manager,p,office,emp,_=team(game);ticket=request(e,p)
    before=copy.deepcopy(e.world.to_dict())
    choice=InternalPropertyServices(e).repair(b,p,'interior','repair')
    assert choice['provider']==office.id and e.world.to_dict()==before
    cash=e.world.cash(b.id)
    OperatingAutomation(e).properties(b,l,b.authority['purchasing_limit'],requests_only=True)
    job=e.world.systems['property_work'][-1]
    assert job['provider']==office.id and job['assigned_staff']==[emp.id]
    assert cash-e.world.cash(b.id)==job['materials'] and job['prepaid']==job['materials']
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    assert any('internal contractor labor' in row['detail'] for row in cash_forecast(e.world,b.id)['rows'])
    deliver(e,l,office,3)
    assert job['status']=='complete' and job['staff']==[emp.id]
    assert job['actual_cost']>job['materials'] and systems_for(e.world,p)['interior']['condition']>25
    receivable=e.world.accounts[office.id]['asset:intercompany:'+b.id]
    assert receivable==-e.world.accounts[b.id]['liability:intercompany:'+office.id]>0
    e.validate()


@pytest.mark.parametrize('reason',['leave','license','backlog','disabled','county','cash'])
def test_unavailable_or_restricted_internal_staff_fall_back_to_outside(game,reason):
    e,l,b,_,p,office,emp,_=team(game)
    system='electrical' if reason=='license' else 'interior'
    if reason=='leave':emp.leave_until='2026-02-01'
    if reason=='disabled':OperatingAutomation(e).action(dict(business_id=b.id,prefer_internal_property=False))
    if reason=='county':ServiceOffice(e).action('department_configure',dict(provider=office.id,department='maintenance',regions=b.region),'restrict')
    if reason=='cash':
        amount=e.world.cash(office.id)
        e.post(office.id,'liability','Due obligation',{'expense:testing':amount,'liability:payable':-amount})
    if reason=='backlog':
        e.action('property_work',dict(property_id=p.id,system='roof',kind='replacement',provider=office.id),'backlog')
        e.world.systems['property_work'][-1]['remaining']=10000
    choice=InternalPropertyServices(e).repair(b,p,system,'repair')
    assert choice['provider']=='outside'


def test_licensed_trade_and_home_office_priority(game):
    e,l,b,_,p,office,emp,_=team(game)
    other,person=add_specialist(e,b.id,'maintenance');person.skills['maintenance']=100
    l.rules.person(emp.person_id).licenses['electrical']='2030-12-31'
    choice=InternalPropertyServices(e).repair(b,p,'electrical','repair')
    assert choice['provider']==office.id
    request(e,p,'electrical');OperatingAutomation(e).properties(b,l,1000000,requests_only=True)
    assert e.world.systems['property_work'][-1]['required_license']=='electrical'
    l.rules.person(emp.person_id).licenses['electrical']='2020-01-01'
    remaining=e.world.systems['property_work'][-1]['remaining'];deliver(e,l,office,1)
    assert e.world.systems['property_work'][-1]['remaining']==remaining


def test_agent_is_queued_without_manual_department_and_only_completed_work_reduces_fees(game):
    e,l,b,_,p,office,_,agent=team(game)
    before=copy.deepcopy(e.world.to_dict());internal=InternalPropertyServices(e)
    assert internal.agent(b,p)['provider']==office.id and e.world.to_dict()==before
    ordinary=brokerage(e.world,p,b.id,p.value,3)
    assert not internal.prepare_closing(b,p,l,1000000)
    task=e.world.systems['service_tasks'][-1]
    assert task['provider']==office.id and task['status']=='queued' and task['labor_remaining']>=960
    assert e.world.systems['departments'][office.id+':real_estate_agent']['tools']==0
    assert brokerage(e.world,p,b.id,p.value,3)==ordinary
    assert not internal.prepare_closing(b,p,l,1000000) and len(e.world.systems['service_tasks'])==1
    deliver(e,l,office,8)
    assert task['status']=='complete' and task['staff']==[agent.id] and task['internal_cost']>0
    assert internal.prepare_closing(b,p,l,1000000) and len(e.world.systems['service_tasks'])==1
    assert brokerage(e.world,p,b.id,p.value,3)==ordinary*30//100
    e.action('market_property',dict(property_id=p.id,asking=p.value),'market')
    listing=e.world.systems['property_listings'][p.id]
    listing['offers']=[dict(id='sale-test',price=p.value,concession=0,finance_risk=0,status='open')]
    e.action('accept_property_offer',dict(property_id=p.id,offer_id='sale-test'),'accept')
    e.world.date=listing['due'];PropertyOperations(e).sales_tick()
    assert task['used']==e.world.date and task['fee_avoided']==ordinary-ordinary*30//100
    assert not representation(e.world,p,b.id)
    e.validate()


def test_agent_explicit_department_coverage_and_staff_restrictions_apply(game):
    e,l,b,_,p,office,_,agent=team(game)
    ServiceOffice(e).action('department_configure',dict(provider=office.id,department='real_estate_agent',staff=agent.id,regions=b.region),'limited-agent')
    assert InternalPropertyServices(e).agent(b,p) is None
    assert InternalPropertyServices(e).prepare_closing(b,p,l,1000000)
    assert not e.world.systems.get('service_tasks')
    ServiceOffice(e).action('department_configure',dict(provider=office.id,department='real_estate_agent',staff=agent.id,regions=p.region),'expand-agent')
    assert not InternalPropertyServices(e).prepare_closing(b,p,l,1000000)
    deliver(e,l,office,8)
    assert e.world.systems['service_tasks'][-1]['status']=='complete'


def test_internal_repair_respects_manager_and_parent_authority(game):
    e,l,b,_,p,office,_,_=team(game);request(e,p)
    contract(e,b,regions=[b.region])
    cash=e.world.cash(b.id);OperatingAutomation(e).properties(b,l,1000000,requests_only=True)
    assert not e.world.systems.get('property_work') and e.world.cash(b.id)==cash
    r=e.world.systems['management_requests'][-1]
    assert r['args']['provider']==office.id and 'scope' in r['detail']


def test_director_cover_also_prefers_home_office_staff(game):
    e,l,b,manager,p,office,_,_=team(game)
    director,_=add_specialist(e,office.id,'manager')
    l.action('director_assign',dict(employment_id=director.id,business_id=b.id,limit=1000000),'director')
    manager.leave_until='2026-02-01';request(e,p)
    OperatingAutomation(e).properties(b,l,1000000,requests_only=True)
    assert e.world.systems['authority_audit'][-1]['actor']==director.id
    assert e.world.systems['property_work'][-1]['provider']==office.id
    e.validate()


@pytest.mark.parametrize('reason',['license','leave','too_late'])
def test_agent_uses_ordinary_closing_when_internal_preparation_is_unavailable(game,reason):
    e,l,b,_,p,office,_,agent=team(game)
    if reason=='license':l.rules.person(agent.person_id).licenses['real_estate']='2020-01-01'
    elif reason=='leave':agent.leave_until='2026-02-01'
    else:e.world.systems.setdefault('property_listings',{})[p.id]=dict(status='closing',due=e.world.date)
    assert InternalPropertyServices(e).prepare_closing(b,p,l,1000000)
    assert not e.world.systems.get('service_tasks')


def test_delegated_flip_prepares_agent_before_attempting_acquisition(game):
    from economic_simulation.manager_defaults import automation
    e,l,b,_,p,office,_,_=team(game)
    target=min((p for p in e.world.properties if p.owner is None and p.status=='market' and p.region==b.region and p.category!='land' and not p.id.startswith('covenant')),key=lambda p:p.asking)
    e.action('inspect_property',dict(property_id=target.id,entity=b.id),'inspect')
    e.action('flip_budget',dict(property_id=target.id,entity=b.id,renovation=100000,days=30),'budget')
    policy={**automation(e.world,b),'flip_capital':1000000000,'flip_downside':1000000000}
    OperatingAutomation(e).flips(b,l,1000000,policy)
    assert target.owner is None
    assert e.world.systems['service_tasks'][-1]['target_id']==target.id
    assert e.world.systems['service_tasks'][-1]['provider']==office.id
    assert not any(r['action']=='fund_flip' for r in e.world.systems.get('management_requests',[]))


def test_cancelled_agent_work_and_outside_override_are_respected(game):
    e,l,b,_,p,office,_,_=team(game);internal=InternalPropertyServices(e)
    OperatingAutomation(e).action(dict(business_id=b.id,prefer_internal_property=False))
    assert internal.prepare_closing(b,p,l,1000000) and not e.world.systems.get('service_tasks')
    OperatingAutomation(e).action(dict(business_id=b.id,prefer_internal_property=True))
    assert not internal.prepare_closing(b,p,l,1000000)
    task=e.world.systems['service_tasks'][-1]
    e.action('cancel_service',dict(task_id=task['id']),'cancel-agent')
    assert internal.prepare_closing(b,p,l,1000000) and len(e.world.systems['service_tasks'])==1


def test_internal_flip_releases_only_materials_then_actual_labor_from_reserve(game):
    e,l,b,_,_,office,emp,_=team(game)
    p=min((p for p in e.world.properties if p.owner is None and p.status=='market' and p.category!='land' and not p.id.startswith('covenant')),key=lambda p:p.asking)
    e.post('personal','fixture-capital','Test capital',{'asset:cash':100000000,'equity:capital':-100000000})
    e.action('fund_business',dict(business_id=b.id,amount=100000000),'fixture-funding')
    e.action('inspect_property',dict(property_id=p.id,entity=b.id),'inspect-flip')
    e.action('flip_budget',dict(property_id=p.id,entity=b.id,renovation=1000000,days=30),'budget')
    e.action('fund_flip',dict(property_id=p.id,entity=b.id),'fund')
    progress=e.world.systems['flip_progress'][p.id];reserve=progress['reserve']
    e.action('flip_work',dict(property_id=p.id,provider=office.id,assigned_staff=emp.id),'work')
    job=e.world.systems['property_work'][-1]
    assert reserve-progress['reserve']==job['materials'] and job['flip_funded']
    deliver(e,l,office,5)
    assert job['status']=='complete' and reserve-progress['reserve']==job['actual_cost']
    assert e.world.accounts[b.id]['asset:flip_reserve']==progress['reserve']
    e.validate()


def test_daily_and_skip_keep_internal_work_and_payroll_identical(game,tmp_path):
    from economic_simulation.application import Game
    e,l,b,_,p,office,_,_=team(game);request(e,p)
    for company in (b,office):
        company.authority['operating_policy']={'hiring':'freeze','training':False,'growth':'off'}
    e.action('settle_obligations',dict(entity=b.id),'pay')
    assert not InternalPropertyServices(e).prepare_closing(b,p,l,1000000)
    e.events=[];e.pause_reasons=[]
    game.store.commit(e,game.world.revision);game.world=e.world
    with game.store.connection() as source,sqlite3.connect(tmp_path/'daily.sqlite3') as dest:source.backup(dest)
    daily=Game(tmp_path/'daily.sqlite3')
    try:
        act(game,'advance',target='2026-01-14');game.worker.join(timeout=30)
        assert game.progress['completed']==2,game.progress
        for _ in range(2):act(daily,'advance',period='day');daily.worker.join(timeout=30)
        left=copy.deepcopy(game.world.to_dict());right=copy.deepcopy(daily.world.to_dict());left['revision']=right['revision']
        assert json.loads(json.dumps(left))==json.loads(json.dumps(right))
        assert game.store.load().to_dict()==json.loads(json.dumps(game.world.to_dict()))
        game.store.audit(game.world);daily.store.audit(daily.world)
    finally:daily.close()


def test_ui_shows_default_preference_and_home_office_agent_without_setup(game):
    e,l,b,_,p,office,_,_=team(game);game.store.commit(e,game.world.revision);game.world=e.world
    with client_for(game) as c:
        html=c.get('/?page=operations_center&scope='+b.id).text
        assert 'Prefer home-office and owned property specialists' in html
        assert 'name="prefer_internal_property"' in html
        html=c.get('/?page=property_workbench&scope='+b.id).text
        assert 'without separate department setup' in html and office.name in html


def test_old_daily_capacity_does_not_force_outside_repairs(game):
    e,l,b,_,p,office,_,_=team(game)
    l.rules.work(office,date.fromisoformat(e.world.date))
    e.named_capacity[office.id]={uid:0 for uid in e.named_capacity[office.id]}
    internal=InternalPropertyServices(e)
    assert internal.repair(b,p,'interior','repair')['provider']=='outside'
    e.world.date='2026-01-13'
    assert internal.repair(b,p,'interior','repair')['provider']==office.id


@pytest.mark.parametrize('kind',['cleaning','landscaping'])
def test_home_office_maintenance_handles_basic_care_with_shared_hours(game,kind):
    from economic_simulation.routine_management import RoutineManagement
    from economic_simulation.property_services import PropertyServices
    e,l,b,_,p,office,emp,_=team(game)
    assert RoutineManagement(e).provider(p,kind,True)==office.id
    e.action('property_service',dict(property_id=p.id,kind=kind,provider=office.id,visits=1),'care')
    job=e.world.systems['property_service_jobs'][-1]
    e.world.date='2026-07-06' # Summer grounds work, with no winter weather delay.
    for _ in range(5):
        buckets,_=l.rules.work(office,date.fromisoformat(e.world.date))
        initial=e.named_initial[office.id][emp.id]
        PropertyServices(e).deliver_home_office(l.rules,office,buckets)
        assert 0<=e.named_capacity[office.id][emp.id]<=initial
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    assert job['completed_visits']==1 and job['supplies']>0 and job['labor_cost']>0
    assert job['staff']==[emp.id] and job['prepaid']==0
    e.validate()


def test_home_office_care_cannot_reuse_hours_spent_on_repairs_or_provide_security(game):
    from economic_simulation.routine_management import RoutineManagement
    from economic_simulation.property_services import PropertyServices
    e,l,b,_,p,office,emp,_=team(game)
    assert RoutineManagement(e).provider(p,'security',True)=='outside'
    e.action('property_work',dict(property_id=p.id,system='interior',kind='repair',provider=office.id),'repair')
    e.action('property_service',dict(property_id=p.id,kind='cleaning',provider=office.id,visits=1),'care')
    buckets,_=l.rules.work(office,date.fromisoformat(e.world.date))
    PropertyOperations(e).deliver(l.rules,office,buckets)
    assert e.named_capacity[office.id][emp.id]==0
    PropertyServices(e).deliver_home_office(l.rules,office,buckets)
    assert e.world.systems['property_service_jobs'][-1]['worked']==0
    OperatingAutomation(e).action(dict(business_id=b.id,prefer_internal_property=False))
    assert RoutineManagement(e).provider(p,'cleaning',True)=='outside'
