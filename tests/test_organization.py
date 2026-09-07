import copy
from urllib.parse import urlparse, parse_qs

from economic_simulation.domain import Engine
from economic_simulation.organization import employee_tree, ownership_tree
from test_game import game, act, step
from test_business import acquire
from test_campaign_product import client_for
from test_premises import business_property


def nodes(root):
    if root:
        yield root
        for child in root['children']:
            yield from nodes(child)


def test_ownership_uses_real_owner_including_holding_company_tenant(game):
    bid,pid,_=business_property(game,'company')
    act(game,'lease_premises',business_id=bid,property_id=pid,rent=110000,deposit_months=1)
    before=copy.deepcopy(game.world.to_dict())
    chart=ownership_tree(game.world)
    by_id={n['id']:n for n in nodes(chart['root'])}
    prop=by_id['property:'+pid]
    assert prop in by_id['company']['children']
    assert prop not in by_id[bid]['children']
    assert any(line.startswith('Leased to ') for line in prop['meta'])
    assert chart['properties']==1 and chart['companies']==2
    focused=ownership_tree(game.world,bid)
    assert focused['root']['id']==bid and focused['properties']==0
    assert game.world.to_dict()==before


def test_ownership_displays_nested_subsidiaries_and_company_real_estate(game):
    engine=Engine(copy.deepcopy(game.world))
    engine.post('personal','test-org-capital','Test capital',{'asset:cash':500000000,'equity:capital':-500000000})
    game.store.commit(engine,game.world.revision);game.world=engine.world
    root=next(b for b in game.world.businesses if any(child.market_parent==b.id for child in game.world.businesses))
    act(game,'acquire_business',business_id=root.id,entity='personal');step(game,3)
    chart=ownership_tree(game.world,root.id)
    assert chart['companies']==3 and chart['properties']==2
    assert sum(c['kind']=='company' for c in chart['root']['children'])==2
    assert sum(c['kind']=='property' for c in chart['root']['children'])==2
    all_ids=[n['id'] for n in nodes(chart['root'])]
    assert len(all_ids)==len(set(all_ids))
    assert not chart['warnings']


def test_employee_chart_keeps_vacant_supervisor_and_incoming_hires(game):
    bid=acquire(game)
    act(game,'create_position',business_id=bid,role='manager')
    vacancy=game.world.positions[-1]
    cashier=next(e for e in game.world.employments if e.employer==bid and next(p for p in game.world.positions if p.id==e.position_id).role=='cashier')
    act(game,'reporting',employment_id=cashier.id,reports_to=vacancy.id)
    before=copy.deepcopy(game.world.to_dict())
    tree=employee_tree(game.world,bid)
    by_id={n['id']:n for n in nodes(tree['root'])}
    assert by_id[vacancy.id]['kind']=='vacancy'
    assert by_id[cashier.position_id] in by_id[vacancy.id]['children']
    assert game.world.to_dict()==before
    candidate=next(p for p in game.world.people if p.candidate)
    act(game,'hire',position_id=vacancy.id,person_id=candidate.id,amount=340000,weekly_hours=40)
    after=employee_tree(game.world,bid)
    by_id={n['id']:n for n in nodes(after['root'])}
    assert after['joining']==1
    assert by_id[vacancy.id]['title']==candidate.name and by_id[vacancy.id]['status']=='joining'
    assert by_id[cashier.position_id] in by_id[vacancy.id]['children']


def test_organization_routes_empty_selection_links_and_escaping(game):
    with client_for(game) as client:
        assert 'Your team starts with a business' in client.get('/?page=organization&chart=employees').text
    bid=acquire(game)
    # Views must escape saved names and preserve valid navigation parameters.
    person=next(p for p in game.world.people if any(e.person_id==p.id and e.employer==bid for e in game.world.employments))
    person.name='<script>alert("test")</script>'
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        for chart in ('ownership','employees'):
            response=client.get('/',params=dict(page='organization',chart=chart,business_id=bid,org_root='invalid'))
            assert response.status_code==200
            assert 'data-org-chart' in response.text
            assert 'Fit chart' in response.text and '/static/organization.js' in response.text
            assert '<script>alert(' not in response.text
        assert '&lt;script&gt;' in response.text
        detail=client.get('/',params=dict(page='business',business_id=bid)).text
        assert 'View employee hierarchy' in detail and 'View subsidiaries and real estate' in detail
        for n in nodes(employee_tree(game.world,bid)['root']):
            if n['url']:
                assert client.get(n['url']).status_code==200
            for l in n['links']:
                assert parse_qs(urlparse(l['url']).query)['page']==['workforce']
                assert client.get(l['url']).status_code==200
    assert game.world.to_dict()==before


def test_invalid_reporting_cycle_stays_visible_and_outside_ownership_is_excluded(game):
    bid=acquire(game)
    positions=[p for p in game.world.positions if p.business_id==bid]
    positions[0].reports_to=positions[1].id;positions[1].reports_to=positions[0].id
    tree=employee_tree(game.world,bid)
    assert len(list(nodes(tree['root'])))==len(positions)+1
    assert tree['warnings']
    market=next(b for b in game.world.businesses if b.status=='market')
    assert ownership_tree(game.world,market.id)['focus']=='personal'
    assert market.id not in {n['id'] for n in nodes(ownership_tree(game.world)['root'])}


def test_vacancy_card_targets_exact_position_when_role_has_multiple_openings(game):
    bid=acquire(game)
    act(game,'create_position',business_id=bid,role='manager')
    act(game,'create_position',business_id=bid,role='manager')
    selected=game.world.positions[-1]
    card=next(n for n in nodes(employee_tree(game.world,bid)['root']) if n['id']==selected.id)
    with client_for(game) as client:
        response=client.get(card['url'])
        assert response.status_code==200
        assert f'name="position_id" value="{selected.id}"' in response.text
