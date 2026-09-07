import copy
from urllib.parse import parse_qs, urlparse

from test_game import game, act
from test_leadership import setup
from test_campaign_product import client_for
from economic_simulation.recovery_navigation import approval_links, recovery_links, progress_links


def pending(game):
    engine,leader,b,emp,_=setup(game)
    leader.request(b,'navigation-stock','restock',dict(business_id=b.id,units=5),b.unit_cost*5,'Stock approval')
    game.store.commit(engine,game.world.revision)
    game.world=engine.world
    return b,game.world.systems['management_requests'][-1]


def test_stopped_skip_links_to_actual_approval_without_spending(game):
    b,request=pending(game)
    before=copy.deepcopy(game.world.to_dict())
    act(game,'advance',period='week');game.worker.join(10)
    assert not game.progress['running'] and game.progress['completed']==0
    assert game.progress['blocked'] and game.progress['blocker']=='approval'
    links=progress_links(game.world,game.progress)
    assert links[0]['url'].endswith('#management:'+request['id']) and b.name in links[0]['label']
    assert game.world.date==before['date'] and game.world.accounts==before['accounts']
    client=client_for(game)
    response=client.get('/?page=businesses')
    assert 'Resolve time blocker' in response.text and links[0]['label'] in response.text
    inbox=client.get(links[0]['url'])
    assert 'id="management:'+request['id']+'"' in inbox.text
    assert client.get('/api/progress').json()['links']==links
    assert 'Owner approval needed before a long skip' in response.text


def test_resolution_removes_stale_anchor_and_preflight_warning(game):
    b,request=pending(game)
    game.progress.update(blocked=True,blocker='approval',running=False,total=7)
    act(game,'management_defer',request_id=request['id'])
    assert approval_links(game.world)==[]
    assert not any('#management:' in r['url'] for r in progress_links(game.world,game.progress))
    assert 'Owner approval needed before a long skip' not in client_for(game).get('/').text


def test_preview_and_command_errors_offer_owned_context_and_do_not_mutate(game):
    b,request=pending(game);client=client_for(game)
    # A real impossible purchase is refused by the existing funding guard.
    before=copy.deepcopy(game.world.to_dict())
    for endpoint in ('preview','command'):
        response=client.post('/api/'+endpoint,json=dict(action='restock',args=dict(business_id=b.id,units=10000),revision=game.world.revision,command_id='recovery-'+endpoint))
        assert response.status_code==409
        data=response.json();assert data['detail'] and data['recovery_links']
        funding=next(r for r in data['recovery_links'] if 'funding' in r['label'])
        assert parse_qs(urlparse(funding['url']).query)['scope']==[b.id]
        target=client.get(funding['url'])
        assert target.status_code==200 and 'id="business-capital"' in target.text
        assert funding['url'].endswith('#business-capital')
    assert game.world.to_dict()==before


def test_request_error_preserves_request_business_and_unknown_ids_are_not_links(game):
    b,request=pending(game)
    rows=recovery_links(game.world,'Not enough cash',dict(request_id=request['id']))
    assert all('scope='+b.id in r['url'] for r in rows)
    rows=recovery_links(game.world,'Not enough cash',dict(entity='https://untrusted.invalid',business_id=['invalid']))
    assert all(r['url'].startswith('/?') and 'untrusted' not in r['url'] for r in rows)
    assert all('scope=personal' in r['url'] for r in rows)


def test_error_shortcuts_cover_requirements_and_preserve_employee_identity(game):
    b,request=pending(game);emp=next(e for e in game.world.employments if e.employer==b.id)
    before=copy.deepcopy(game.world.to_dict())
    links=recovery_links(game.world,'Qualified employee needs more scheduled hours',dict(employment_id=emp.id))
    assert 'employment_id='+emp.id in links[0]['url']
    for text,page in [('Insufficient authority limit','management'),('Repair roof condition first','property_workbench'),('Obtain legal transfer consent','commercial_contracts'),('Department has no service capacity','home_office')]:
        assert any('page='+page in r['url'] for r in recovery_links(game.world,text,dict(business_id=b.id)))
    assert game.world.to_dict()==before


def test_successful_or_cancelled_skip_has_no_blocker_shortcuts(game):
    assert not progress_links(game.world,dict(running=True,blocked=True))
    assert not progress_links(game.world,dict(running=False,blocked=False))
    assert not progress_links(game.world,dict(running=False))
    assert recovery_links(game.world,'This screen is out of date')[0]['behavior']=='refresh'
    assert recovery_links(game.world,'Pause time advancement before making changes.')[0]['behavior']=='time'


def test_event_and_exception_stops_keep_recovery_available(game):
    for reason in ('Paused for an important event: Payroll unpaid.','Time stopped safely at the last saved day: Unknown failure'):
        links=progress_links(game.world,dict(running=False,blocked=True,reason=reason))
        assert links and any('page=inbox' in r['url'] for r in links)
        for link in links:assert client_for(game).get(link['url']).status_code==200


def test_multiple_approvals_are_named_and_old_seller_requests_are_excluded(game):
    b,request=pending(game)
    requests=game.world.systems['management_requests']
    for i in range(5):requests.append(dict(request,id='request-copy-'+str(i)))
    requests.append(dict(request,id='seller-request',business_id='unowned'))
    links=approval_links(game.world)
    assert len(links)==4 and 'all 6 approvals' in links[-1]['label']
    assert all('seller-request' not in r['url'] for r in links)

