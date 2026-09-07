import copy,json
import pytest
from test_game import game
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import Engine,RuleError
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_models import ROLE_PAY
from economic_simulation.staffing import hiring_view
from economic_simulation.specialists import LICENSES


def setup(game,role):
    e=Engine(copy.deepcopy(game.world))
    e.action('start_business',dict(industry='office',name='Specialist Office',region='Rutland County',entity='personal'),'start-office')
    b=e.world.businesses[-1];rules=BusinessRules(e)
    person=rules.make_person(role,candidate=True)
    return e,b,rules,person


@pytest.mark.parametrize('role',['hvac_technician','electrician','plumber','real_estate_agent','hr','legal','accounting'])
def test_create_specialist_position_then_hire_qualified_applicant(game,role):
    e,b,rules,person=setup(game,role)
    e.action('create_position',dict(business_id=b.id,role=role),'create-specialist')
    pos=e.world.positions[-1]
    assert pos.required_license==LICENSES.get(role)
    e.action('hire',dict(position_id=pos.id,person_id=person.id,amount=ROLE_PAY[role],weekly_hours=40),'hire-specialist')
    assert e.world.employments[-1].person_id==person.id and e.world.employments[-1].status=='joining'
    e.validate()


@pytest.mark.parametrize('vacancy',['none','legacy','explicit'])
def test_hiring_view_filters_missing_expired_license_even_without_vacancy(game,vacancy):
    e,b,rules,valid=setup(game,'hvac_technician')
    missing=rules.make_person('hvac_technician',candidate=True);missing.licenses={}
    expired=rules.make_person('hvac_technician',candidate=True);expired.licenses['hvac']='2025-01-01'
    if vacancy!='none':
        e.action('create_position',dict(business_id=b.id,role='hvac_technician'),'vacancy')
        if vacancy=='legacy':e.world.positions[-1].required_license=None
    before=copy.deepcopy(e.world.to_dict());view=hiring_view(e.world,b.id,'hvac_technician')
    assert view['license']=='hvac' and valid.id in [p['id'] for p in view['eligible']]
    assert {missing.id,expired.id}<={p['id'] for p in view['excluded']}
    assert e.world.to_dict()==before


def test_invalid_custom_license_does_not_create_position_or_consume_id(game):
    e,b,rules,person=setup(game,'hr');before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError,match='recognized license'):
        e.action('create_position',dict(business_id=b.id,role='hr',required_license='imaginary'),'bad-license')
    assert e.world.to_dict()==before


def test_guided_hvac_offer_preview_commit_and_reload(game):
    e,b,rules,person=setup(game,'hvac_technician')
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html=client.get('/?page=hiring&business_id='+b.id+'&role=hvac_technician').text
        assert 'Required license:' in html and 'set automatically for the role' in html
        payload=dict(action='hire_for_role',args=dict(business_id=b.id,role='hvac_technician',person_id=person.id,amount_dollars='4700',weekly_hours=40),revision=game.world.revision,command_id='guided-hvac')
        preview=client.post('/api/preview',json=payload)
        assert preview.status_code==200,preview.text
        assert game.world.to_dict()==before
        assert client.post('/api/command',json=payload).status_code==200
    assert game.world.positions[-1].required_license=='hvac'
    assert game.world.employments[-1].person_id==person.id
    loaded=Game(game.store.path)
    try:assert loaded.world.to_dict()==json.loads(json.dumps(game.world.to_dict()))
    finally:loaded.close()
    game.store.audit(game.world)
