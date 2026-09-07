import copy
from html.parser import HTMLParser
from urllib.parse import parse_qs,urlsplit

import pytest
from test_game import game,act
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.navigation import navigation_view,resolve_context


class Document(HTMLParser):
    def __init__(self,text):
        super().__init__();self.nodes=[];self.feed(text)
    def handle_starttag(self,tag,attrs):self.nodes.append((tag,dict(attrs)))


@pytest.mark.parametrize('page',['inbox','activity','services','home_office','forecast','expansion','financing','property_workbench','commercial_contracts'])
def test_company_switch_keeps_the_current_tool_and_discards_record_selection(game,page):
    bid=acquire(game)
    nav=navigation_view(game.world,page,'personal')
    choice=next(c for c in nav['choices'] if c['id']==bid)
    assert parse_qs(urlsplit(choice['url']).query)==dict(page=[page],scope=[bid])
    with client_for(game) as client:
        html=client.get(choice['url']).text
        assert '<meta name="scope" content="'+bid+'">' in html


@pytest.mark.parametrize('page,section,primary',[('property_workbench','properties','portfolio'),('property_services','properties','portfolio'),
    ('services','services','services'),('home_office','services','home_office'),('finance','finance','finance'),('people','team','people')])
def test_tools_highlight_the_right_business_section_and_sidebar(game,page,section,primary):
    bid=acquire(game);nav=navigation_view(game.world,page,bid,bid)
    assert nav['section']==section and nav['primary']==primary
    with client_for(game) as client:
        doc=Document(client.get('/?page='+page+'&scope='+bid).text)
        current=[attrs['href'] for tag,attrs in doc.nodes if tag=='a' and attrs.get('aria-current')]
        assert any(parse_qs(urlsplit(href).query).get('page')==[page] for href in current)


def test_stale_details_show_a_directory_notice_and_consistent_context(game):
    bid=acquire(game);before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        for page,key,expected in [('business','business_id','businesses'),('employee','employment_id','people'),('property','property_id','portfolio')]:
            response=client.get('/',params=dict(page=page,scope=bid,**{key:'missing-record'}))
            assert response.status_code==200
            assert 'unavailable' in response.text or 'no longer available' in response.text
            assert '<title>Empire Manager · '+expected.title()+'</title>' in response.text
            if expected=='businesses':assert '<meta name="scope" content="personal">' in response.text
        assert resolve_context(game.world,'business',bid)['business_id']==bid
    assert game.world.to_dict()==before


def test_former_employee_link_returns_to_the_employing_team(game):
    bid=acquire(game)
    emp=next(e for e in game.world.employments if e.employer==bid)
    emp.status='ended'
    ctx=resolve_context(game.world,'employee','personal',employment_id=emp.id)
    assert (ctx['page'],ctx['scope'],ctx['business_id'])==('people',bid,bid)


def test_mobile_navigation_contains_all_tools_and_visible_inbox_count(game):
    with client_for(game) as client:
        html=client.get('/').text;doc=Document(html)
        assert ('nav',dict(id='main-navigation',**{'aria-label':'Main navigation'})) in doc.nodes
        button=next(a for t,a in doc.nodes if a.get('id')=='navigation-toggle')
        assert button['aria-controls']=='main-navigation' and button['aria-expanded']=='false'
        assert 'Decisions <b data-inbox-count>' in html
        for page in ('property_workbench','operations_center','property_services','commercial_contracts','settings'):
            assert any(t=='a' and parse_qs(urlsplit(a.get('href','')).query).get('page')==[page] for t,a in doc.nodes)
        assert any(a.get('id')=='main-content' for _,a in doc.nodes)
        assert any(a.get('href')=='#main-content' for _,a in doc.nodes)


def test_end_of_campaign_link_opens_actual_game_creation_controls(game):
    game.world.systems['campaign_outcome']=dict(status='insolvent',reason='Test campaign ending',date=game.world.date)
    with client_for(game) as client:
        html=client.get('/').text
        assert 'href="/?page=games#new-game"' in html
        destination=Document(client.get('/?page=games').text)
        assert any(t=='details' and a.get('id')=='new-game' for t,a in destination.nodes)


def test_unrelated_sidebar_sections_do_not_open_on_home_office_page(game):
    with client_for(game) as client:
        html=client.get('/?page=home_office').text
        sidebar=html.split('<nav id="main-navigation"',1)[1].split('</nav>',1)[0]
        assert '<details open' not in sidebar
