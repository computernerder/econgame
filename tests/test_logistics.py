import copy,json
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_new_industries import purchase
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import Engine,new_game,STORAGE_CONTENT_VERSION,CONTENT_VERSION
from economic_simulation.persistence import Store
from economic_simulation.business_rules import BusinessRules
from economic_simulation.logistics import freight_capacity,providers,group_benefits,settle_transport
from economic_simulation.staffing import staffing_plan


def buy(game,industry):
    bid=next(b.id for b in game.world.businesses if b.industry==industry and b.status=='market')
    act(game,'acquire_business',business_id=bid,entity='personal');step(game,3);return bid


def operating_day(game):
    day=date.fromisoformat(game.world.date)+timedelta(days=1)
    while day.weekday()>4:day+=timedelta(days=1)
    step(game,(day-date.fromisoformat(game.world.date)).days)


def test_logistics_acquisition_startup_staffing_and_external_income(game):
    bid=purchase(game,'logistics');step(game,8)
    b=next(b for b in game.world.businesses if b.id==bid)
    assert game.world.accounts[bid]['income:freight_sales']<0
    assert game.world.accounts[bid]['expense:freight_running']>0
    assert {r['role'] for r in staffing_plan(game.world,bid)['rows']}=={'manager','driver','dispatcher'}
    with client_for(game) as c:
        page=c.get('/',params={'page':'business','business_id':bid})
        assert page.status_code==200 and 'Truck fleet' in page.text and 'Ownership benefits' in page.text
    act(game,'start_business',industry='logistics',name='New fleet',region='Chittenden County')
    assert game.world.businesses[-1].fleet_vehicles==4
    assert game.world.businesses[-1].status=='developing'
    game.store.audit(game.world)


def test_bank_and_transport_benefits_stack_with_real_cost_and_capacity(game):
    fleet=purchase(game,'logistics');grocery=buy(game,'grocery');bank=buy(game,'bank')
    act(game,'transfer_business',business_id=grocery,new_owner=bank)
    act(game,'transfer_business',business_id=fleet,new_owner=grocery)
    act(game,'borrow',entity=grocery,lender=bank,amount=100000,months=12)
    operating_day(game)
    b=next(b for b in game.world.businesses if b.id==grocery);carrier=next(b for b in game.world.businesses if b.id==fleet)
    assert b.last_day['transport_internal']>0 and b.last_day['transport_savings']>0
    row=next(c for c in carrier.last_day['group_clients'] if c['id']==grocery)
    assert row['charge']==row['capacity_used']*carrier.last_day['freight_unit_cost']
    assert carrier.last_day['output']<=carrier.last_day['freight_capacity']
    assert carrier.last_day['output']==carrier.last_day['internal_deliveries']+carrier.last_day['external_deliveries']
    benefits=group_benefits(game.world,b)
    assert any(x['id']==bank and x['parent_bank'] for x in benefits['banks'])
    assert any(x['id']==fleet for x in benefits['transport'])
    assert game.world.systems['loans'][-1]['rate_bps']==game.world.systems['interest_bps']
    assert game.world.accounts[grocery]['expense:internal_transport:'+fleet]==-game.world.accounts[fleet]['income:internal_transport:'+grocery]
    game.store.audit(game.world)
    act(game,'transfer_business',business_id=fleet,new_owner='personal');operating_day(game)
    b=next(b for b in game.world.businesses if b.id==grocery)
    assert not providers(game.world,b) and b.last_day['transport_internal']==0
    assert b.last_day['transport_cost']==b.last_day['transport_deliveries']*30000
    restored=Game(game.store.path);restored.store.audit(restored.world);restored.close()


def test_capacity_requires_overlap_and_limits_group_and_external_work(game):
    act(game,'create_holding_company',name='Your property company')
    fleet=purchase(game,'logistics');b=next(b for b in game.world.businesses if b.id==fleet)
    buckets={'driver':[0]*24,'dispatcher':[0]*24}
    buckets['driver'][8]=600;buckets['dispatcher'][9]=600
    assert freight_capacity(b,buckets)==0
    buckets['dispatcher'][8]=600
    assert freight_capacity(b,buckets)<=b.fleet_vehicles*8
    grocery=buy(game,'grocery');retail=buy(game,'retail')
    for bid in (fleet,grocery,retail):act(game,'transfer_business',business_id=bid,new_owner='company')
    e=Engine(copy.deepcopy(game.world));e.world.date='2026-02-02'
    for company in e.world.businesses:
        if company.id in (grocery,retail):company.last_day={'date':e.world.date,'output':1000};company.history=[]
        if company.id==fleet:company.last_day={'date':e.world.date,'freight_capacity':3};company.history=[]
    settle_transport(BusinessRules(e),date(2026,2,2))
    carrier=next(b for b in e.world.businesses if b.id==fleet)
    assert carrier.last_day['internal_deliveries']==3 and carrier.last_day['external_deliveries']==0
    assert sum(next(b for b in e.world.businesses if b.id==bid).last_day['transport_internal'] for bid in (grocery,retail))==3
    count=len(e.postings);settle_transport(BusinessRules(e),date(2026,2,2));assert len(e.postings)==count
    e.validate()


def test_logistics_save_upgrade_once_preserves_existing_assets(tmp_path):
    e=new_game();w=e.world;ids={b.id for b in w.businesses if b.industry=='logistics'}
    w.businesses=[b for b in w.businesses if b.id not in ids]
    w.positions=[p for p in w.positions if p.business_id not in ids]
    w.employments=[x for x in w.employments if x.employer not in ids]
    w.content_version=STORAGE_CONTENT_VERSION;before=w.to_dict();path=tmp_path/'old.sqlite3';Store(path,initial=e)
    g=Game(path);after=g.world.to_dict();assert after['accounts']==before['accounts']
    for key in ('properties','businesses','people','positions','employments'):
        now={row['id']:row for row in after[key]};assert all(now[row['id']]==row for row in before[key])
    assert g.world.content_version==CONTENT_VERSION and any(b.industry=='logistics' for b in g.world.businesses)
    g.store.audit(g.world);g.close();again=Game(path);assert again.world.to_dict()==after;again.close()
    assert len(list(tmp_path.glob('old.before-logistics-*.sqlite3')))==1

def test_freight_revenue_can_fund_friday_payroll_without_duplicate_work(game):
    fleet=purchase(game,'logistics');e=Engine(copy.deepcopy(game.world));e.world.date='2026-01-09'
    carrier=next(b for b in e.world.businesses if b.id==fleet)
    cash=e.world.cash(fleet);e.post(fleet,'test-cash-used','Test expense',{'asset:cash':-cash,'expense:test':cash})
    rules=BusinessRules(e);rules.operate(carrier,date(2026,1,9))
    owed=-e.world.accounts[fleet]['liability:payroll'];assert owed>0
    counts={x.id:x.worked_days for x in e.world.employments if x.employer==fleet}
    assert not settle_transport(rules,date(2026,1,9))
    assert not carrier.payroll_overdue and e.world.accounts[fleet]['liability:payroll']==0
    assert counts=={x.id:x.worked_days for x in e.world.employments if x.employer==fleet}
    e.validate()
