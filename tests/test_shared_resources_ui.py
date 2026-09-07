import copy,json
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_business import acquire
from test_department_ui import configured
from test_campaign_product import client_for
from test_internal_property_services import team
from economic_simulation.domain import Engine,RuleError
from economic_simulation.business_rules import BusinessRules
from economic_simulation.service_office import ServiceOffice
from economic_simulation.shared_services import SharedServices
from economic_simulation.shared_team_views import describe
from economic_simulation.campaign_views import campaign_view
from economic_simulation.ui_workflows import prepare
from economic_simulation.specialists import apply,available,recruitment_fee


def setup(game):
    target_id=acquire(game)
    bid,hr,it=configured(game)
    engine=Engine(copy.deepcopy(game.world))
    target=next(b for b in engine.world.businesses if b.id==target_id)
    office=next(b for b in engine.world.businesses if b.id==bid);office.status='operating';office.opening_on=None
    while date.fromisoformat(engine.world.date).weekday()>4:
        engine.world.date=(date.fromisoformat(engine.world.date)+timedelta(days=1)).isoformat()
    dept=engine.world.systems['departments'][bid+':hr']
    dept['regions']=list({target.region,next(b.region for b in engine.world.businesses if b.id==bid)})
    game.store.commit(engine,game.world.revision);game.world=engine.world
    return bid,hr,target


def args(bid,hr,target,**extra):
    return dict(department_id=bid+':hr',employment_id=hr.id,target=target.id,start_time='08:00',minutes=120,**extra)


def test_team_cards_show_names_actions_real_coverage_and_honest_idle_state(game):
    bid,hr,target=setup(game);before=copy.deepcopy(game.world.to_dict())
    d=game.world.systems['departments'][bid+':hr'];d['regions']=['Other County']
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html=client.get('/?page=home_office').text
        assert 'Schedule regular support' in html and 'Recruit for a selected role' in html
        assert 'Outside coverage — add this county' in html
        assert 'Staff may still support their own employer' in html
        assert 'service_product=role_search' in html and 'shared_team='+bid+'%3Ahr' in html
        assert next(p.name for p in game.world.people if p.id==hr.person_id) in html
    assert game.world.to_dict()==before


@pytest.mark.parametrize('product',['role_search','assessment','onboarding','succession',''])
def test_service_links_focus_exact_product_and_internal_provider(game,product):
    bid,hr,target=setup(game);before=copy.deepcopy(game.world.to_dict())
    view=campaign_view(game.world,'home_office',bid)
    prepare(view,game.world,bid,action_focus='service_request',shared_team=bid+':hr',service_product=product)
    task=view['focused_task'];fields={f['name']:f for f in task['fields']}
    assert fields.get('product',{}).get('value','')==product
    assert fields['department']['value']=='hr'
    assert fields['mode']['value']=='internal'
    assert fields['provider']['value']==bid
    assert {o['value'] for o in fields['provider']['options']}=={bid}
    assert all(o['value']==bid for o in task['field_context']['provider']['options'])
    assert 'outside reservation $' not in task['description']
    assert game.world.to_dict()==before


def test_stale_or_wrong_team_links_do_not_focus_a_different_task(game):
    bid,hr,target=setup(game)
    with client_for(game) as client:
        for team_id,product in [('missing','role_search'),(bid+':hr','property_representation')]:
            result=client.get('/',params=dict(page='home_office',shared_team=team_id,action_focus='service_request',service_product=product))
            assert result.status_code==200 and '<section id="task-focus"' not in result.text


def test_no_receiving_county_or_staff_shows_recovery_not_wrong_account(game):
    bid,hr,target=setup(game)
    d=game.world.systems['departments'][bid+':hr'];d['regions']=[]
    view=campaign_view(game.world,'home_office',bid)
    prepare(view,game.world,bid,action_focus='share_department_staff',shared_team=d['id'])
    assert any('No eligible receiving business' in error for error in view['focused_task']['context_errors'])
    assert 'department_id=' in view['shared_context']['edit']


def test_regular_support_preview_is_read_only_and_confirmation_persists(game):
    bid,hr,target=setup(game);before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        payload=dict(action='share_department_staff',args=args(bid,hr,target),revision=game.world.revision,command_id='shared-resource-preview')
        response=client.post('/api/preview',json=payload)
        assert response.status_code==200,response.text
        assert 'Estimated allocation' in response.json()['message']
        assert game.world.to_dict()==before
        response=client.post('/api/command',json=payload)
        assert response.status_code==200,response.text
    a=game.world.systems['assignments'][-1]
    assert a['employment_id']==hr.id and a['target']==target.id and a['minutes']==120
    assert game.world.systems['agreements'][-1]['markup']==0
    assert game.world.accounts==before['accounts']
    assert json.dumps(game.store.load().to_dict(),sort_keys=True)==json.dumps(game.world.to_dict(),sort_keys=True)
    with client_for(game) as client:
        html=client.get('/?page=home_office').text
        assert 'Regular support in progress' in html and 'data-action="end_assignment"' in html
    view=campaign_view(game.world,'home_office',bid)
    prepare(view,game.world,bid,action_focus='share_department_staff',shared_team=bid+':hr')
    assert next(f['value'] for f in view['focused_task']['fields'] if f['name']=='start_time')=='10:00'
    act(game,'end_assignment',assignment_id=a['id'])
    assert not game.world.systems['assignments'][-1]['active']
    assert next(e for e in game.world.employments if e.id==hr.id).status=='active'


def test_shared_support_produces_recipient_hr_hours_without_duplicating_time_or_cash(game):
    bid,hr,target=setup(game);act(game,'share_department_staff',**args(bid,hr,target))
    e=Engine(copy.deepcopy(game.world));rules=BusinessRules(e)
    source=rules.company(bid);target=rules.company(target.id)
    baseline=Engine(copy.deepcopy(e.world));baseline.world.systems['assignments'][-1]['active']=False
    own,_=BusinessRules(baseline).work(BusinessRules(baseline).company(bid),date.fromisoformat(e.world.date))
    source_buckets,_=rules.work(source,date.fromisoformat(e.world.date))
    target_buckets,_=rules.work(target,date.fromisoformat(e.world.date))
    assert 0<sum(target_buckets['hr'])
    assert sum(source_buckets['hr'])<sum(own['hr'])
    assert sum(source_buckets['hr'])+sum(target_buckets['hr'])<=sum(own['hr'])+2
    apply(rules,target,target_buckets)
    assert available(e.world,target.id,'hr')>=60
    assert recruitment_fee(e.world,target.id)==0
    group_cash=sum(e.world.cash(entity) for entity in e.world.accounts)
    SharedServices(e).settle(date.fromisoformat(e.world.date))
    assert sum(e.world.cash(entity) for entity in e.world.accounts)==group_cash
    assert e.world.systems['assignments'][-1]['last_cost']>0
    e.validate()


def test_shared_support_daily_and_skip_equivalence_and_forecast(game,tmp_path):
    import sqlite3
    from economic_simulation.application import Game
    from economic_simulation.authority import cash_forecast
    bid,hr,target=setup(game);act(game,'share_department_staff',**args(bid,hr,target))
    assert any('shared-service charges' in r['detail'] for r in cash_forecast(game.world,target.id)['rows'])
    e=Engine(copy.deepcopy(game.world))
    for b in e.world.businesses:
        if b.owner:b.authority['operating_policy']={'hiring':'freeze','training':False,'growth':'off'}
    e.events=[];e.pause_reasons=[]
    game.store.commit(e,game.world.revision);game.world=e.world
    with game.store.connection() as source,sqlite3.connect(tmp_path/'daily-shared.sqlite3') as dest:source.backup(dest)
    daily=Game(tmp_path/'daily-shared.sqlite3')
    try:
        target_date=(date.fromisoformat(game.world.date)+timedelta(days=2)).isoformat()
        act(game,'advance',target=target_date);game.worker.join(timeout=30)
        assert game.progress['completed']==2,game.progress
        for _ in range(2):act(daily,'advance',period='day');daily.worker.join(timeout=30)
        left=copy.deepcopy(game.world.to_dict());right=copy.deepcopy(daily.world.to_dict());left['revision']=right['revision']
        assert json.loads(json.dumps(left))==json.loads(json.dumps(right))
        assert available(game.world,target.id,'hr')>0
        game.store.audit(game.world);daily.store.audit(daily.world)
    finally:daily.close()


@pytest.mark.parametrize('problem',['overlap','shift','county','wrong_staff','inactive','no_access','director'])
def test_invalid_shared_support_is_atomic(game,problem):
    bid,hr,target=setup(game);e=Engine(copy.deepcopy(game.world));values=args(bid,hr,target)
    if problem=='overlap':e.action('share_department_staff',values,'first')
    if problem=='shift':values['start_time']='23:00'
    if problem=='county':e.world.systems['departments'][bid+':hr']['regions']=[]
    if problem=='wrong_staff':values['employment_id']=next(emp.id for emp in e.world.employments if emp.id!=hr.id)
    if problem=='inactive':next(emp for emp in e.world.employments if emp.id==hr.id).status='joining'
    if problem=='no_access':SharedServices(e).action('service_agreement',dict(source=bid,target=target.id,staff_access=False),'blocked')
    if problem=='director':e.world.systems.setdefault('directors',[]).append(dict(active=True,employment_id=hr.id,business_ids=[target.id]))
    before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError):e.action('share_department_staff',values,'invalid')
    assert e.world.to_dict()==before


def test_existing_markup_is_preserved_and_leave_stops_shared_delivery(game):
    bid,hr,target=setup(game)
    act(game,'service_agreement',source=bid,target=target.id,markup=10,staff_access=True)
    act(game,'share_department_staff',**args(bid,hr,target))
    agreements=[a for a in game.world.systems['agreements'] if a['source']==bid and a['target']==target.id]
    assert len(agreements)==1 and agreements[0]['markup']==10
    e=Engine(copy.deepcopy(game.world));emp=next(e for e in e.world.employments if e.id==hr.id);emp.leave_until='2027-01-01'
    buckets={};SharedServices(e).incoming(BusinessRules(e).company(target.id),date.fromisoformat(e.world.date),buckets)
    assert not buckets
    SharedServices(e).settle(date.fromisoformat(e.world.date))
    assert e.world.systems['assignments'][-1]['last_cost']==0


def test_maintenance_and_agent_cards_open_correct_existing_workflows(game):
    e,l,b,manager,p,office,maintenance,agent=team(game)
    ServiceOffice(e).action('department_configure',dict(provider=office.id,department='maintenance',regions=p.region),'maintenance')
    e.action('property_service',dict(property_id=p.id,provider=office.id,kind='cleaning',visits=4),'care')
    card=describe(e.world,e.world.systems['departments'][office.id+':maintenance'])
    assert any(job['label']=='Cleaning visits' and job['remaining']==480 for job in card['queue'])
    game.store.commit(e,game.world.revision);game.world=e.world
    for role,action,product,page in [('maintenance','property_work','','property_workbench'),('real_estate_agent','service_request','property_representation','home_office')]:
        view=campaign_view(game.world,page,office.id)
        prepare(view,game.world,office.id,action_focus=action,shared_team=office.id+':'+role,service_product=product)
        f=view['focused_task'];fields={x['name']:x for x in f['fields']}
        assert fields['provider']['value']==office.id
        assert all(o['value']==office.id for o in fields['provider']['options'])
        assert not f.get('context_errors')
        if role=='real_estate_agent':assert fields['product']['value']=='property_representation'
        else:assert p.id in f['work_properties']


def test_selected_recruiting_work_is_really_queued_and_delivered(game):
    bid,hr,target=setup(game)
    view=campaign_view(game.world,'home_office',bid)
    prepare(view,game.world,bid,action_focus='service_request',shared_team=bid+':hr',service_product='role_search')
    f=view['focused_task'];values={x['name']:x['value'] for x in f['fields'] if not x.get('hidden')}
    assert not f.get('context_errors')
    act(game,'service_request',**values)
    task=game.world.systems['service_tasks'][-1]
    assert task['provider']==bid and task['mode']=='internal' and task['product']=='role_search'
    e=Engine(copy.deepcopy(game.world));rules=BusinessRules(e);office=rules.company(bid)
    buckets,_=rules.work(office,date.fromisoformat(e.world.date))
    ServiceOffice(e).deliver(rules,office,buckets)
    task=e.world.systems['service_tasks'][-1]
    assert task['remaining']<task['effort'] and task['internal_cost']>0
    e.validate()
