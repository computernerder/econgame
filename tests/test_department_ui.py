import copy,json,re
from test_game import game,act
from test_home_office_company import create_office
from test_specialists import add_specialist
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.service_office import ServiceOffice
from economic_simulation.campaign_views import campaign_view
from economic_simulation.ui_workflows import prepare


def configured(game):
    bid=create_office(game);e=Engine(copy.deepcopy(game.world))
    hr,_=add_specialist(e,bid,'hr');it,_=add_specialist(e,bid,'it')
    ServiceOffice(e).action('department_configure',dict(provider=bid,department='hr',staff=hr.id,tools=3,
        regions='Rutland County,Chittenden County',industries='retail,engineering',leader=hr.id),'hr-config')
    game.store.commit(e,game.world.revision);game.world=e.world
    return bid,hr,it


def test_departments_are_visible_before_queue_and_have_specific_edit_and_hire_links(game):
    bid,hr,it=configured(game);before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as c:
        html=c.get('/?page=home_office').text
        assert html.index('id="departments-title"')<html.index('<h2>Service work queue and digest</h2>')<html.index('Home-office company finances and setup')
        assert 'Add / configure department' in html and 'Edit department →' in html and 'Hire HR staff' in html
        assert 'department_id='+bid+'%3Ahr' in html and 'role=hr' in html
        assert html.count('data-action="department_configure"')==1
    assert game.world.to_dict()==before


def test_edit_loads_saved_staff_tools_coverage_and_preserves_config_without_extra_tool_cost(game):
    bid,hr,it=configured(game);key=bid+':hr';before=copy.deepcopy(game.world.to_dict())
    view=campaign_view(game.world,'home_office','personal')
    prepare(view,game.world,'personal',action_focus='department_configure',department_id=key)
    form=view['focused_task'];fields={f['name']:f for f in form['fields']}
    assert fields['tools']['value']==3 and fields['staff']['value']==[hr.id]
    assert fields['regions']['value']=='Rutland County,Chittenden County'
    assert fields['industries']['value']=='retail,engineering' and fields['leader']['value']==hr.id
    assert [o['value'] for o in fields['staff']['options']]==[hr.id]
    assert len(fields['provider']['options'])==len(fields['department']['options'])==1
    with client_for(game) as c:
        response=c.get('/?page=home_office&action_focus=department_configure&department_id='+key)
        assert response.status_code==200 and 'Edit HR · Group Services' in response.text
        assert 'id="department-setup" open' in response.text
        payload=json.loads(re.search(r'data-department-context>(.*?)</script>',response.text,re.S).group(1))
        assert payload['departments'][key]['tools']==3
    assert game.world.to_dict()==before
    cash=game.world.cash(bid);args={name:f['value'] for name,f in fields.items()};args['staff']=','.join(args['staff'])
    act(game,'department_configure',**args)
    assert game.world.cash(bid)==cash
    for name in ('staff','tools','regions','industries','leader'):
        assert game.world.systems['departments'][key][name]==before['systems']['departments'][key][name]


def test_new_and_invalid_department_routes_explain_state_without_mutating_save(game):
    bid=create_office(game);before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as c:
        html=c.get('/?page=home_office&scope='+bid).text
        assert 'No internal departments configured yet' in html and 'id="department-setup" open' in html
        assert 'New HR department' in html
        invalid=c.get('/?page=home_office&action_focus=department_configure&department_id=unknown').text
        assert 'That department is no longer available' in invalid and '<section id="task-focus"' not in invalid
    assert game.world.to_dict()==before
