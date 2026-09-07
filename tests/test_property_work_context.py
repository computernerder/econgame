import copy,json,re
from test_game import game
from test_property_services import property_for
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.property_operations import PropertyOperations,systems_for


def test_booking_conditions_match_selected_property_and_existing_work_without_mutation(game):
    e=Engine(copy.deepcopy(game.world));first=property_for(e);second=property_for(e)
    operations=PropertyOperations(e)
    operations.ensure(first)['roof']['condition']=23
    operations.ensure(second)['roof']['condition']=81
    e.action('property_work',dict(property_id=second.id,system='plumbing',kind='repair',provider='outside'),'plumbing-work')
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as c:
        general=c.get('/?page=property_workbench')
        assert general.status_code==200 and 'Current system conditions' in general.text
        data=json.loads(re.search(r'data-work-properties>(.*?)</script>',general.text,re.S).group(1))
        assert set(data)=={first.id,second.id}
        for p in (first,second):
            assert {r['key']:r['condition'] for r in data[p.id]['systems']}=={k:v['condition'] for k,v in systems_for(game.world,p).items()}
        focused=c.get('/?page=property_workbench&property_id='+second.id+'&action_focus=property_work&work_system=plumbing')
        assert focused.status_code==200 and 'Roof · 81/100' in focused.text
        assert 'data-work-system="plumbing" aria-pressed="true"' in focused.text
        assert 'Repair underway · 12.0 hours remaining' in focused.text
        assert 'Licensed plumbing contractor' in focused.text
        focused_data=json.loads(re.search(r'data-work-properties>(.*?)</script>',focused.text,re.S).group(1))
        assert set(focused_data)=={second.id}
    assert game.world.to_dict()==before


def test_empty_property_booking_has_no_invented_conditions(game):
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as c:
        html=c.get('/?page=property_workbench').text
        assert 'Choose an owned building to see its current system conditions.' in html
        assert re.search(r'data-work-properties>\{\}</script>',html)
        assert 'data-work-system="roof"' not in html
    assert game.world.to_dict()==before
