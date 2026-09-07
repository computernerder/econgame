import copy
import pytest
from test_game import game, step
from test_new_industries import test_new_industry_acquisition_operations_staffing_and_startup as exercise, purchase
from economic_simulation.domain import Engine, new_game, PROPERTY_CONTENT_VERSION, CONTENT_VERSION
from economic_simulation.persistence import Store
from economic_simulation.application import Game
from economic_simulation.real_estate import required_category

@pytest.mark.parametrize('industry',['factory','boutique'])
def test_expansion_operations_hiring_startup_and_reload(game,industry):
    exercise(game,industry)
    b=next(b for b in game.world.businesses if b.industry==industry)
    assert required_category(b)==('industrial' if industry=='factory' else 'commercial')


def test_factory_completes_orders_and_automatically_takes_next(game):
    bid=purchase(game,'factory')
    step(game,70)
    b=next(b for b in game.world.businesses if b.id==bid)
    assert b.project_history and b.project_number>1
    assert game.world.accounts[bid]['expense:project_materials']>0
    assert any(p['title']=='Factory contract accepted' for p in game.world.events)
    game.store.audit(game.world)


def test_expansion_upgrade_preserves_records_and_is_idempotent(tmp_path):
    e=new_game();w=e.world
    removed={b.id for b in w.businesses if b.industry in ('factory','boutique')}
    w.businesses=[b for b in w.businesses if b.id not in removed]
    w.positions=[p for p in w.positions if p.business_id not in removed]
    w.employments=[x for x in w.employments if x.employer not in removed]
    w.content_version=PROPERTY_CONTENT_VERSION
    before=copy.deepcopy(w.to_dict());path=tmp_path/'old.sqlite3';Store(path,initial=e)
    g=Game(path);after=g.world.to_dict()
    assert after['accounts']==before['accounts']
    for key in ('businesses','people','properties','positions','employments'):
        now={row['id']:row for row in after[key]}
        assert all(now[row['id']]==row for row in before[key])
    assert {'factory','boutique'}<={b.industry for b in g.world.businesses}
    assert g.world.content_version==CONTENT_VERSION
    g.store.audit(g.world);g.close()
    again=Game(path);assert again.world.to_dict()==after;again.close()
    assert len(list(tmp_path.glob('old.before-factories-boutiques-*.sqlite3')))==1
