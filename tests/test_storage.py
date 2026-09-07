import copy
import json
from datetime import date
import pytest
from test_game import game, act, step
from test_new_industries import purchase
from test_campaign_product import client_for
from economic_simulation.domain import Engine, new_game, daily_share, EXPANSION_CONTENT_VERSION, CONTENT_VERSION
from economic_simulation.application import Game
from economic_simulation.persistence import Store
from economic_simulation.storage import operate_storage
from economic_simulation.business_rules import BusinessRules
from economic_simulation.staffing import staffing_plan


def test_storage_acquisition_income_guidance_and_startup(game):
    bid=purchase(game,'self_storage');step(game,8)
    b=next(b for b in game.world.businesses if b.id==bid)
    assert 0<b.storage_occupied<=b.storage_units
    assert game.world.accounts[bid]['income:storage_rent']<0
    assert {r['role'] for r in staffing_plan(game.world,bid)['rows']}=={'property_manager','maintenance'}
    with client_for(game) as client:
        response=client.get('/',params={'page':'business','business_id':bid})
        assert response.status_code==200 and 'Contracted monthly rent' in response.text
        assert 'Storage occupancy' in response.text
    act(game,'start_business',industry='self_storage',name='New storage facility',region='Rutland County')
    b=game.world.businesses[-1]
    assert b.storage_occupied==0 and b.storage_units==120 and b.status=='developing'
    game.store.audit(game.world)
    restored=Game(game.store.path);assert json.dumps(restored.world.to_dict(),sort_keys=True)==json.dumps(game.world.to_dict(),sort_keys=True);restored.close()


def test_storage_weekend_rent_vacancies_and_staff_constraints(game):
    bid=purchase(game,'self_storage')
    e=Engine(copy.deepcopy(game.world));b=next(b for b in e.world.businesses if b.id==bid);r=BusinessRules(e)
    e.world.date='2026-01-10';b.storage_occupied=5
    out=operate_storage(r,b,date(2026,1,10),{},False)
    assert out['storage_rent']==5*daily_share(b.storage_monthly_rent,date(2026,1,10))
    assert out['moved_in']==0
    b.storage_occupied=0;e.world.date='2026-01-12'
    out=operate_storage(r,b,date(2026,1,12),{'property_manager':0,'maintenance':240},True)
    assert out['storage_rent']==0 and b.storage_occupied==0
    e.world.date='2026-01-13'
    out=operate_storage(r,b,date(2026,1,13),{'property_manager':60,'maintenance':240},True)
    assert out['moved_in']==2 and b.storage_occupied==2
    assert out['storage_rent']==2*daily_share(b.storage_monthly_rent,date(2026,1,13))
    e.validate()


def test_storage_turnover_and_maintenance_cost(game):
    bid=purchase(game,'self_storage');e=Engine(copy.deepcopy(game.world));b=next(b for b in e.world.businesses if b.id==bid)
    b.storage_occupied=80;e.world.date='2026-02-01'
    out=operate_storage(BusinessRules(e),b,date(2026,2,1),{},False)
    assert out['moved_out']==2 and b.storage_occupied==78
    e.world.date='2026-02-02'
    operate_storage(BusinessRules(e),b,date(2026,2,2),{},True)
    assert e.world.accounts[bid]['expense:outsourced_maintenance']>=120*2*60
    e.validate()


def test_storage_upgrade_preserves_records_and_runs_once(tmp_path):
    e=new_game();w=e.world
    ids={b.id for b in w.businesses if b.industry=='self_storage'}
    w.businesses=[b for b in w.businesses if b.id not in ids]
    w.positions=[p for p in w.positions if p.business_id not in ids]
    w.employments=[x for x in w.employments if x.employer not in ids]
    w.content_version=EXPANSION_CONTENT_VERSION;before=w.to_dict();path=tmp_path/'old.sqlite3';Store(path,initial=e)
    g=Game(path);after=g.world.to_dict();assert after['accounts']==before['accounts']
    for key in ('properties','businesses','people','positions','employments'):
        now={row['id']:row for row in after[key]}
        assert all(now[row['id']]==row for row in before[key])
    assert g.world.content_version==CONTENT_VERSION
    assert sum(b.industry=='self_storage' for b in g.world.businesses)==1
    g.store.audit(g.world);g.close()
    again=Game(path);assert again.world.to_dict()==after;again.close()
    assert len(list(tmp_path.glob('old.before-storage-*.sqlite3')))==1
