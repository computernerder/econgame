import copy
from html import unescape
from urllib.parse import urlparse, parse_qs

from economic_simulation.navigation import navigation_view, resolve_context
from test_game import game, act
from test_business import acquire
from test_campaign_product import client_for
from test_premises import business_property


def scope_in(html,scope):
    assert f'<meta name="scope" content="{scope}">' in html


def test_business_employee_and_finance_tabs_share_the_same_context(game):
    a=acquire(game,0);b=acquire(game,2)
    emp=next(e for e in game.world.employments if e.employer==b)
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        for page,extra in [('business',dict(business_id=b)),('employee',dict(employment_id=emp.id)),('workforce',dict(employment_id=emp.id)),('people',dict(business_id=b))]:
            response=client.get('/',params=dict(page=page,scope=a,**extra))
            assert response.status_code==200
            scope_in(response.text,b)
            assert 'Business sections' in response.text
        nav=navigation_view(game.world,'business',b,b)
        for tab in nav['tabs']:
            response=client.get(tab['url'])
            assert response.status_code==200
            scope_in(response.text,b)
        response=client.get('/',params=dict(page='overview',scope=b))
        assert 'Staffing guide' in response.text
        response=client.get('/?page=people&scope=personal')
        scope_in(response.text,'personal')
        assert 'All employees' in response.text
    assert before==game.world.to_dict()


def test_switcher_clears_stale_records_but_keeps_relevant_section(game):
    a=acquire(game,0);b=acquire(game,2)
    for page,expected in [('employee','people'),('hiring','people'),('property','portfolio'),('finance','finance'),('business','business')]:
        nav=navigation_view(game.world,page,a,a)
        destination=next(c['url'] for c in nav['choices'] if c['id']==b)
        query=parse_qs(urlparse(destination).query)
        assert query['scope']==[b] and query['page']==[expected]
        assert 'employment_id' not in query and 'property_id' not in query
        if expected in ('business','people'):assert query['business_id']==[b]
    act(game,'create_holding_company',name='Portfolio Holdings')
    nav=navigation_view(game.world,'organization',b,b,chart='employees')
    query=parse_qs(urlparse(next(c['url'] for c in nav['choices'] if c['id']=='company')).query)
    assert query['chart']==['ownership'] and query['org_root']==['company']


def test_owned_property_selects_owner_but_market_listing_preserves_buyer(game):
    bid,pid,_=business_property(game,'company')
    market=next(p for p in game.world.properties if p.status=='market')
    with client_for(game) as client:
        owned=client.get('/',params=dict(page='property',property_id=pid,scope=bid))
        scope_in(owned.text,'company')
        listing=client.get('/',params=dict(page='property',property_id=market.id,scope=bid))
        scope_in(listing.text,bid)
        assert "PURCHASE ACCOUNT" in listing.text
        for page in ('market','business_market'):
            response=client.get('/',params=dict(page=page,scope=bid))
            assert 'PURCHASE ACCOUNT' in response.text
            scope_in(response.text,bid)
        directory=client.get('/?page=portfolio&scope=personal&all_properties=true')
        assert market.name not in directory.text
        assert f'scope=company&property_id={pid}' in unescape(directory.text)
        assert 'Your property company' in directory.text
        local=client.get('/',params=dict(page='portfolio',scope=bid))
        assert f'property_id={pid}' not in local.text


def test_chart_context_matches_selected_business_and_owner(game):
    act(game,'create_holding_company',name='Your property company')
    bid=acquire(game)
    with client_for(game) as client:
        chart=client.get('/?page=organization&chart=employees')
        scope_in(chart.text,bid)
        chart=client.get('/',params=dict(page='organization',chart='ownership',org_root='company',scope=bid))
        scope_in(chart.text,'company')
        personal=client.get('/',params=dict(page='owner',scope=bid))
        scope_in(personal.text,'personal')
    context=resolve_context(game.world,'businesses',bid)
    assert context['scope']=='personal'
