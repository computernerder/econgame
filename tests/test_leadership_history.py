import copy,json
import pytest
from test_game import game
from test_leadership import setup
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import RuleError
from economic_simulation.executives import Executives
from economic_simulation.leadership_history import duties


def appoint(e,emp,bid,limit=100000):
    e.action('director_assign',dict(employment_id=emp.id,business_id=bid,limit=limit),'appoint-'+bid+str(limit))


def career(l,emp):
    return [r for r in l.rules.person(emp.person_id).history
            if r['event'].startswith(('Appointed ','Leadership duties changed:','Leadership duties ended:'))]


def test_appointment_scope_limit_removal_and_repeat_history(game):
    e,l,b,emp,other=setup(game,True)
    appoint(e,emp,b.id)
    first=career(l,emp)
    assert len(first)==1 and first[0]['date']==e.world.date
    assert 'Appointed Director for '+b.name in first[0]['event']
    assert 'Employer: '+b.name in first[0]['event'] and '$3,910' in first[0]['event']
    appoint(e,emp,b.id);assert career(l,emp)==first
    appoint(e,emp,other);assert len(career(l,emp))==2
    assert l.rules.company(other).name in career(l,emp)[-1]['event']
    appoint(e,emp,other,200000);assert len(career(l,emp))==3
    assert '$1,000' in career(l,emp)[-1]['event'] and '$2,000' in career(l,emp)[-1]['event']
    for bid in (other,b.id):e.action('director_remove',dict(business_id=bid),'remove-'+bid)
    assert len(career(l,emp))==5 and career(l,emp)[-1]['event'].startswith('Leadership duties ended:')
    e.action('director_remove',dict(business_id=b.id),'remove-again')
    assert len(career(l,emp))==5 and duties(e.world,emp)==[]
    e.validate()


def test_replacement_records_both_employees_and_preserves_other_scope(game):
    e,l,b,emp,other=setup(game,True)
    replacement=next(x for x in l.rules.staff(other) if l.rules.position(x.position_id).role=='manager')
    appoint(e,emp,b.id);appoint(e,emp,other)
    appoint(e,replacement,b.id)
    assert 'Replaced by '+l.rules.person(replacement.person_id).name in career(l,emp)[-1]['event']
    assert [x['id'] for x in duties(e.world,emp)[0]['businesses']]==[other]
    assert 'Appointed Director for '+b.name in career(l,replacement)[-1]['event']
    assert emp.employer==b.id and replacement.employer==other
    e.validate()


def test_executive_role_and_scope_changes_have_history_without_repeat_noise(game):
    e,l,b,emp,other=setup(game,True);x=Executives(e)
    args=dict(employment_id=emp.id,business_ids=b.id,role='home_office_director')
    x.action(args);assert 'Appointed Home Office Director' in career(l,emp)[-1]['event']
    x.action(args);assert len(career(l,emp))==1
    x.action(dict(args,role='division_vp',business_ids=b.id+','+other))
    assert len(career(l,emp))==2 and 'Division VP' in career(l,emp)[-1]['event']
    assert len(duties(e.world,emp)[0]['businesses'])==2
    e.validate()


def test_rejected_appointment_has_no_career_change(game):
    e,l,b,emp,_=setup(game);emp.weekly_hours=10
    before=copy.deepcopy(e.world.to_dict())
    with pytest.raises(RuleError,match='scheduled hour'):appoint(e,emp,b.id)
    assert e.world.to_dict()==before


def test_legacy_duties_display_read_only_and_new_history_roundtrips(game):
    e,l,b,emp,_=setup(game)
    e.world.systems['directors']=[dict(employment_id=emp.id,business_ids=[b.id],limit=100000,active=True,day=e.world.date,spent=0)]
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        url='/?page=employee&employment_id='+emp.id
        result=client.get(url)
        assert result.status_code==200 and 'Current leadership duties' in result.text
        assert '<h3>Director</h3>' in result.text and '#leadership' in result.text
        assert game.world.to_dict()==before and not career(l,emp)
        payload=dict(action='director_assign',args=dict(employment_id=emp.id,business_id=b.id,limit_dollars='2000'),revision=game.world.revision,command_id='history-preview')
        assert client.post('/api/preview',json=payload).status_code==200
        assert game.world.to_dict()==before
        assert client.post('/api/command',json=payload).status_code==200
        html=client.get(url).text
        assert 'Leadership duties changed:' in html and '$2,000' in html
    loaded=Game(game.store.path)
    try:assert loaded.world.to_dict()==json.loads(json.dumps(game.world.to_dict()))
    finally:loaded.close()
    game.store.audit(game.world)
