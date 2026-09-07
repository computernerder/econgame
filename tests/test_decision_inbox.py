import copy
from datetime import date, timedelta

import pytest

from test_game import game, act, step
from test_leadership import setup
from test_campaign_product import client_for
from test_service_projects import tenant
from test_commercial_contracts import request, deliver
from economic_simulation.domain import Engine, RuleError, World
from economic_simulation.campaign import Campaign
from economic_simulation.campaign_views import campaign_view
from economic_simulation.decision_inbox import items, count, focus
from economic_simulation.property_operations import PropertyOperations
from economic_simulation.property_requests import PropertyRequests
from economic_simulation.service_office import ServiceOffice


def of_kind(world, kind):
    return [r for r in items(world) if r['kind']==kind]


def proposals(game):
    p=game.world.properties[0];act(game,'buy',property_id=p.id)
    act(game,'advertise_space',property_id=p.id,rent=100000);step(game,5)
    return p.id


def test_tenant_offers_reconcile_with_acceptance_decline_and_reload(game):
    pid=proposals(game)
    rows=of_kind(game.world,'tenant_offer');assert len(rows)==3
    before=copy.deepcopy(game.world.to_dict())
    assert items(game.world)==items(game.world)
    assert game.world.to_dict()==before
    first=rows[0];cash=game.world.cash('personal')
    act(game,'inbox_decline_offer',inbox_id=first['id'])
    assert len(of_kind(game.world,'tenant_offer'))==2 and game.world.cash('personal')==cash
    with pytest.raises(RuleError):act(game,'inbox_decline_offer',inbox_id=first['id'])
    chosen=next(o for o in game.world.systems['tenant_offers'] if o['status']=='open' and o['area']<=game.world.properties[0].spaces[0]['area'])
    act(game,'accept_tenant',property_id=pid,offer_id=chosen['id'],rent=chosen['rent'])
    assert not of_kind(game.world,'tenant_offer')
    assert items(game.store.load())==items(game.world)
    game.store.audit(game.world)


def test_offer_link_opens_correct_prefilled_form_and_count(game):
    proposals(game);row=of_kind(game.world,'tenant_offer')[-1]
    before=copy.deepcopy(game.world.to_dict())
    view=campaign_view(game.world,'property_workbench','personal')
    focus(view,game.world,row['id'])
    target=next(f for f in view['forms'] if f.get('focused'))
    values={f['name']:f['value'] for f in target['fields']}
    assert target['action']=='accept_tenant'
    assert all(values[k]==v for k,v in row['targets'].items())
    with client_for(game) as client:
        response=client.get('/?page=inbox')
        assert response.status_code==200 and 'Tenant proposal' in response.text
        assert 'data-inbox-count' in response.text
        response=client.get(row['url'])
        assert response.status_code==200 and 'open id="inbox-target"' in response.text
        assert client.get('/api/progress').json()['inbox_count']==count(game.world)
    assert game.world.to_dict()==before


def test_repairs_appear_and_clear_when_work_is_committed_elsewhere(game):
    e=Engine(copy.deepcopy(game.world));p,ops,lease=tenant(e)
    requests=PropertyRequests(e);requests.tick()
    row=of_kind(e.world,'repair')[0]
    assert row['due'] and row['targets']['property_id']==p.id
    requests.action(dict(property_id=p.id,request_id=row['targets']['request_id'],provider='outside'), 'respond')
    assert not of_kind(e.world,'repair')
    assert e.world.systems['property_work'][-1]['remaining']>0
    e.validate()


def test_renewals_and_normal_accrued_rent_are_distinguished(game):
    e=Engine(copy.deepcopy(game.world));p,ops,lease=tenant(e)
    assert not of_kind(e.world,'renewal') and not of_kind(e.world,'rent_arrears')
    e.world.date=(date.fromisoformat(lease['end_date'])-timedelta(days=30)).isoformat()
    assert of_kind(e.world,'renewal')
    ops.action('renew_property_lease',dict(property_id=p.id,lease_id=lease['id'],rent=lease['rent']),'renew')
    assert not of_kind(e.world,'renewal')


def test_supplier_quotes_and_expiration_follow_source_records(game):
    e=Engine(copy.deepcopy(game.world))
    office,task=request(e,'personal','supplier_tender',service_department='accounting')
    deliver(e,office,3)
    rows=of_kind(e.world,'supplier_offer');assert rows
    row=rows[0];e.action('inbox_decline_offer',dict(inbox_id=row['id']),'decline')
    assert row['id'] not in {r['id'] for r in of_kind(e.world,'supplier_offer')}
    e.world.date='2030-01-01'
    assert not of_kind(e.world,'supplier_offer')


def test_property_sale_offer_leaves_inbox_on_acceptance(game):
    pid=game.world.properties[0].id;act(game,'buy',property_id=pid)
    act(game,'market_property',property_id=pid,asking=5000000)
    step(game,7)
    rows=of_kind(game.world,'sale_offer');assert rows
    act(game,'accept_property_offer',**rows[0]['targets'])
    assert not of_kind(game.world,'sale_offer')
    assert game.world.systems['property_listings'][pid]['status']=='closing'


def test_deferred_approval_can_return_without_spending_and_expires_once(game):
    e,leader,b,emp,_=setup(game)
    leader.request(b,'test','restock',dict(business_id=b.id,units=5),b.unit_cost*5,'Inventory request')
    r=e.world.systems['management_requests'][-1]
    leader.action('management_defer',dict(request_id=r['id']),'defer')
    assert of_kind(e.world,'management')[0]['status']=='deferred'
    cash=copy.deepcopy(e.world.accounts)
    leader.action('management_reopen',dict(request_id=r['id']),'reopen')
    assert r['status']=='open' and e.world.accounts==cash
    leader.action('management_defer',dict(request_id=r['id']),'defer-again')
    e.world.date=(date.fromisoformat(r['deferred_until'])+timedelta(days=1)).isoformat()
    leader.start_day()
    assert r['status']=='open'
    assert len([x for x in e.world.systems['management_requests'] if x['key']=='test'])==1
    assert any(x['title']=='Owner approval needed' for x in e.pause_reasons)


def test_overdue_service_queue_and_obligations_require_attention(game):
    e,leader,b,emp,_=setup(game);office=ServiceOffice(e)
    office.action('department_configure',dict(provider=b.id,department='accounting',staff=''),'department')
    office.action('service_request',dict(recipient=b.id,provider=b.id,department='accounting',mode='internal',days=1),'task')
    e.post(b.id,'bill','Supplier bill',{'expense:test':50000,'liability:payable':-50000})
    e.world.date='2026-02-20'
    assert of_kind(e.world,'service') and of_kind(e.world,'obligations')
    e.action('settle_obligations',dict(entity=b.id),'pay')
    assert not [r for r in of_kind(e.world,'obligations') if r['entity']==b.id]
    office.action('cancel_service',dict(task_id=e.world.systems['service_tasks'][-1]['id']),'cancel')
    assert not of_kind(e.world,'service')


def test_ownership_filter_applies_to_native_and_dynamic_decisions(game):
    pid=proposals(game);e=Engine(copy.deepcopy(game.world))
    c=Campaign(e)
    c.decision('own','Owned choice','Review this.','personal')
    c.decision('not-owned','External choice','Not yours.','outside-owner')
    e.world.properties[0].owner='outside-owner'
    assert not of_kind(e.world,'tenant_offer')
    assert [r['title'] for r in of_kind(e.world,'decision')]==['Owned choice']
    with pytest.raises(RuleError):e.action('inbox_decline_offer',dict(inbox_id='tenant_offer:'+e.world.systems['tenant_offers'][0]['id']),'invalid')


def test_focus_does_not_change_another_hidden_lease_identity(game):
    e=Engine(copy.deepcopy(game.world));p,ops,lease=tenant(e)
    lease['arrears']=1000
    e.post(p.owner,'missed-rent','Missed rent',{'asset:rent_receivable:'+lease['id']:1000,'income:rent':-1000})
    c=Campaign(e);d=c.decision('tenant-arrears:'+lease['id']+':'+e.world.date,'Tenant payment missed','Arrears',p.owner)
    view=dict(page='spaces',forms=[dict(action='lease_response',fields=[dict(name='lease_id',kind='hidden',value='different')]),
                                  dict(action='lease_response',fields=[dict(name='lease_id',kind='hidden',value=lease['id'])])],notes=[])
    focus(view,e.world,'decision:'+d['id'])
    assert not view['forms'][0].get('focused') and view['forms'][1]['focused']


def test_legacy_world_and_inbox_do_not_change_seed_or_ledger(game):
    e,leader,b,emp,_=setup(game)
    leader.request(b,'pending','restock',dict(business_id=b.id,units=5),b.unit_cost*5,'Review stock')
    saved=copy.deepcopy(e.world.to_dict());loaded=World.from_dict(saved)
    for _ in range(3):
        assert items(loaded)==items(e.world)
        campaign_view(loaded,'inbox','personal')
    assert loaded.to_dict()==saved


def test_repricing_failure_clears_when_new_advertising_starts(game):
    pid=game.world.properties[0].id;act(game,'buy',property_id=pid)
    act(game,'advertise_space',property_id=pid,rent=10000000);step(game,5)
    assert len(of_kind(game.world,'vacancy_price'))==1
    act(game,'advertise_space',property_id=pid,rent=100000)
    assert not of_kind(game.world,'vacancy_price')


def test_native_rent_alert_clears_after_payment_plan_without_acknowledging(game):
    e=Engine(copy.deepcopy(game.world));p,ops,lease=tenant(e)
    lease['arrears']=1000
    e.post(p.owner,'rent-missed','Missed rent',{'asset:rent_receivable:'+lease['id']:1000,'income:rent':-1000})
    d=Campaign(e).decision('tenant-arrears:'+lease['id']+':'+e.world.date,'Missed rent','Payment needed',p.owner)
    assert any(r['id']=='decision:'+d['id'] for r in items(e.world))
    e.action('lease_response',dict(lease_id=lease['id'],response='plan'),'payment-plan')
    assert not of_kind(e.world,'rent_arrears')
    assert not any(r['id']=='decision:'+d['id'] for r in items(e.world))
    assert lease['arrears']==1000  # Booking a plan did not invent a payment.


def test_credential_course_removes_duplicate_requests_for_the_same_action(game):
    from test_parallel_projects import fixture_engine
    e,b=fixture_engine(game,'engineering')
    emp=next(x for x in e.world.employments if x.employer==b.id and next(p for p in e.world.positions if p.id==x.position_id).role=='engineer')
    person=next(p for p in e.world.people if p.id==emp.person_id)
    next(p for p in e.world.positions if p.id==emp.position_id).required_license='professional_engineer'
    person.licenses['professional_engineer']='2020-01-01'
    d=Campaign(e).decision('license:'+emp.id+':2020-01-01','Required license unavailable','Credential expired',b.id)
    view=campaign_view(e.world,'inbox','personal')
    row=next(r for r in view['inbox_items'] if r['id']=='decision:'+d['id'])
    assert any(f['action']=='renew_license' for f in row['forms'])
    e.action('renew_license',dict(employment_id=emp.id,license='professional_engineer'),'renew-license')
    assert not any(r['id']=='decision:'+d['id'] or r['id']=='license:'+emp.id for r in items(e.world))
    assert person.licenses['professional_engineer']=='2020-01-01'


def test_flip_stages_follow_actual_work_and_sale_marketing(game):
    pid=game.world.properties[0].id
    act(game,'inspect_property',property_id=pid)
    act(game,'flip_budget',property_id=pid,renovation=500000,days=30)
    act(game,'fund_flip',property_id=pid)
    assert of_kind(game.world,'flip')[0]['action']=='flip_work'
    act(game,'flip_work',property_id=pid)
    assert not of_kind(game.world,'flip')
    step(game,5)
    assert of_kind(game.world,'flip')[0]['action']=='market_property'
    act(game,'market_property',property_id=pid,asking=5000000)
    assert not of_kind(game.world,'flip')
    game.store.audit(game.world)
