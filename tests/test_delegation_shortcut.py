import copy
from test_game import game
from test_recovery_navigation import pending
from test_campaign_product import client_for
from economic_simulation.recovery_navigation import delegation_link


def test_approval_card_dialog_and_target_keep_business_and_state(game):
    b,request=pending(game);client=client_for(game)
    before=copy.deepcopy(game.world.to_dict())
    link=delegation_link(game.world,request['id'])
    assert 'authority_business='+b.id in link['url']
    for page in ('inbox','business','management'):
        response=client.get('/',params=dict(page=page,business_id=b.id,scope=b.id))
        assert response.status_code==200 and 'Change delegated limits' in response.text
    response=client.post('/api/preview',json=dict(action='management_approve',args=dict(request_id=request['id']),revision=game.world.revision,command_id='shortcut-preview'))
    assert response.status_code==200 and response.json()['action_links']==[link]
    target=client.get(link['url'].split('#')[0]+'&search=no-business-matches')
    assert target.status_code==200
    assert 'id="authority-limits-'+b.id+'" open' in target.text
    assert 'open><summary>Manager duties' in target.text
    assert 'name="purchasing_limit_dollars"' in target.text
    assert game.world.to_dict()==before


def test_shortcut_rejects_unknown_or_unowned_records(game):
    b,request=pending(game)
    assert delegation_link(game.world,'missing') is None
    request['business_id']='seller'
    assert delegation_link(game.world,request['id']) is None
    response=client_for(game).get('/?page=management&authority_business=seller')
    assert response.status_code==200 and 'id="authority-limits-seller"' not in response.text


def test_regular_previews_do_not_reuse_approval_shortcut(game):
    b,request=pending(game);client=client_for(game)
    response=client.post('/api/preview',json=dict(action='restock',args=dict(business_id=b.id,units=1),revision=game.world.revision,command_id='stock-shortcut-test'))
    assert response.status_code==200 and response.json()['action_links']==[]
