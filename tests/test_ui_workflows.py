import copy
from urllib.parse import urlparse,parse_qs
from html import unescape
import re
from test_game import game,act
from test_business import acquire
from test_premises import business_property
from test_campaign_product import client_for
from test_home_office_company import create_office
from economic_simulation.campaign_views import campaign_view
from economic_simulation.ui_workflows import prepare
from economic_simulation.property_scale_views import detail
from economic_simulation.navigation import resolve_context
from economic_simulation.recovery_navigation import recovery_links
from economic_simulation.decision_inbox import items


def test_property_repair_link_preserves_owner_asset_and_system_without_mutation(game):
    bid,pid,_=business_property(game,'business');before=copy.deepcopy(game.world.to_dict())
    assert resolve_context(game.world,'property_workbench','personal',property_id=pid)['scope']==bid
    with client_for(game) as c:
        html=c.get('/?page=property&property_id='+pid).text
        links=re.findall(r'href="([^"]+)"',html)
        link=next(unescape(x) for x in links if 'work_system=electrical' in x)
        response=c.get(link);assert response.status_code==200
        assert '<section id="task-focus"' in response.text and 'Owner and paying account:' in response.text
        assert 'value="'+pid+'" ' in response.text
    view=campaign_view(game.world,'property_workbench',bid)
    prepare(view,game.world,bid,pid,'property_work','electrical')
    fields={f['name']:f['value'] for f in view['focused_task']['fields']}
    assert fields['property_id']==pid and fields['system']=='electrical'
    assert view['property_context']['owner']==next(b.name for b in game.world.businesses if b.id==bid)
    assert game.world.to_dict()==before


def test_unknown_property_or_incompatible_action_never_focuses_another_asset(game):
    bid,pid,_=business_property(game,'business')
    for target,action in [('missing','property_work'),(pid,'develop_property')]:
        view=campaign_view(game.world,'property_workbench',bid)
        prepare(view,game.world,bid,target,action)
        assert not view.get('focused_task')
        assert 'not available for the selected action' in view['notes'][0]


def test_property_recovery_link_preserves_exact_work_context(game):
    bid,pid,_=business_property(game,'business')
    links=recovery_links(game.world,'Qualified licensed repair staff are unavailable',dict(property_id=pid,system='electrical'))
    query=parse_qs(urlparse(links[0]['url']).query)
    assert query['property_id']==[pid] and query['scope']==[bid] and query['work_system']==['electrical']


def test_staffing_and_team_offer_visible_specialist_picker_and_policy_shortcuts(game):
    bid=create_office(game)
    with client_for(game) as c:
        for url in ('/?page=business&business_id='+bid,'/?page=people&business_id='+bid):
            html=c.get(url).text
            assert 'Role to hire' in html and 'HVAC technician' in html and '>HR</option>' in html
            assert '#vacancies' in html and '#staffing-policy-'+bid in html
        html=c.get('/?page=business&business_id='+bid).text
        assert html.index('Role to hire')<html.index('<h2>Staffing guide</h2>')


def test_management_directory_precedes_activity_and_policies_have_direct_targets(game):
    bid=acquire(game)
    with client_for(game) as c:
        html=c.get('/?page=management').text
        assert html.index('<h2 id="leader-directory">')<html.index('<section class="panel" id="leadership-activity">')
        assert 'id="staffing-policy-'+bid+'"' in html and 'authority_business='+bid in html


def test_home_office_queue_precedes_setup_and_direct_action_opens_once(game):
    bid=create_office(game);before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as c:
        html=c.get('/?page=home_office&scope='+bid).text
        assert html.index('<h2>Service work queue and digest</h2>')<html.index('Create a separate home-office company')
        focus=c.get('/?page=home_office&scope='+bid+'&action_focus=department_configure').text
        assert 'id="task-focus"' in focus and focus.count('data-action="department_configure"')==1
        assert 'id="department-setup" open' in focus
    assert game.world.to_dict()==before


def test_employee_leadership_and_supervisor_are_above_time_off(game):
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid)
    with client_for(game) as c:
        html=c.get('/?page=employee&employment_id='+emp.id).text
        assert html.index('Current leadership duties')<html.index('id="employee-time-off"')
        assert 'Primary supervisor:' in html and 'id="employee-pay"' in html and 'id="employee-career"' in html


def test_completed_land_description_is_current_without_overwriting_custom_text(game):
    p=next(p for p in game.world.properties if p.category=='land');p.category='commercial';p.kind='Fuel station premises';p.specialization=['gas_station']
    before=copy.deepcopy(game.world.to_dict());view=detail(game.world,p.id)
    assert 'Vacant serviced land' not in view['description'] and 'gas_station' not in view['specialization']
    assert game.world.to_dict()==before
    p.description='Custom owner note.';assert detail(game.world,p.id)['description']=='Custom owner note.'


def test_established_home_shows_actual_businesses_and_decisions(game):
    bid=acquire(game)
    with client_for(game) as c:
        html=c.get('/?page=overview').text
        assert 'Portfolio overview' in html and 'Businesses and teams' in html
        assert 'business_id='+bid in html and 'Decisions to review' in html
        assert 'Your next chapter starts here.' not in html


def test_invoice_cards_identify_records_and_explain_early_default(game):
    bid=acquire(game);b=next(b for b in game.world.businesses if b.id==bid)
    # Player-managed collections still expose individual invoice decisions.
    b.authority['routine_management']={'collections':False}
    b.receivables.extend([dict(id='invoice-alpha',amount=12000,due='2030-01-01',defaulted=True),dict(id='invoice-beta',amount=12000,due='2030-01-01',defaulted=True)])
    before=copy.deepcopy(game.world.to_dict());rows=[r for r in items(game.world) if r['kind']=='invoice']
    assert any('invoice-alpha' in r['title'] for r in rows) and any('invoice-beta' in r['title'] for r in rows)
    assert all('default recorded' in r['detail'] for r in rows)
    assert game.world.to_dict()==before


def test_license_recovery_goes_to_role_not_generic_directory(game):
    bid=create_office(game)
    links=recovery_links(game.world,'The required license is missing or expired',dict(business_id=bid,role='hvac_technician'))
    query=next(parse_qs(urlparse(x['url']).query) for x in links if 'page=hiring' in x['url'])
    assert query['role']==['hvac_technician'] and query['business_id']==[bid]
