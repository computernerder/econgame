import copy
import json
import sqlite3
from datetime import date,timedelta
import pytest
from test_game import game,act
from test_leadership import setup
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError,new_game
from economic_simulation.service_office import ServiceOffice
from economic_simulation.supplier_contracts import SupplierContracts
from economic_simulation.transaction_legal import TransactionLegal
from economic_simulation.simulation_support import stable_roll


def request(e,recipient,product,**extra):
    from economic_simulation.commercial_work import PRODUCTS
    office=ServiceOffice(e)
    office.action('service_request',dict(recipient=recipient,product=product,department=PRODUCTS[product][0],provider='outside',mode='outside',**extra),'request-'+str(e.world.systems['next_id']))
    return office,e.world.systems['service_tasks'][-1]


def deliver(e,office,days):
    for _ in range(days):
        office.tick();e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()


def agreement(e,buyer,department='accounting'):
    office,task=request(e,buyer,'supplier_tender',service_department=department);deliver(e,office,3)
    offers=[o for o in e.world.systems['supplier_offers'] if o['request']==task['id'] and o['status']=='open']
    assert offers
    offer=min(offers,key=lambda o:o['minutes'])
    SupplierContracts(e).action(dict(entity=buyer,offer_id=offer['id']),'accept-'+offer['id'])
    return office,e.world.systems['supplier_contracts'][-1]


def legal_property(e,buyer='personal',success=True):
    return next(p for p in e.world.properties if p.id.startswith('covenant-') and (stable_roll(e.world,'consent:'+p.id+':'+buyer)<75)==success)


def clearance(e,p,buyer='personal'):
    office,t=request(e,buyer,'transaction_review',target_id=p.id);deliver(e,office,3)
    office,t=request(e,buyer,'transfer_consent',target_id=p.id);deliver(e,office,5)
    return t


def test_disclosures_precede_review_and_ordinary_property_play_remains_available(game):
    e=Engine(copy.deepcopy(game.world));p=legal_property(e);legal=TransactionLegal(e)
    before=copy.deepcopy(legal.terms(p));condition=p.condition
    ordinary=next(p for p in e.world.properties if p.status=='market' and not p.id.startswith('covenant-'))
    e.action('buy',dict(property_id=ordinary.id),'ordinary-buy')
    assert ordinary.owner=='personal' and e.quote('buy',ordinary.id)['legal_fee']==0
    office,t=request(e,'personal','transaction_review',target_id=p.id);deliver(e,office,3)
    assert p.condition==condition and t['terms_snapshot']['roof_required']==before['roof_required']
    assert legal.terms(p)['original_fee']==before['original_fee'] and 'personal' in legal.terms(p)['reviews']
    e.validate()


def test_consent_blocks_purchase_then_records_real_future_fee_concession(game):
    e=Engine(copy.deepcopy(game.world));p=legal_property(e);before=e.world.cash('personal')
    with pytest.raises(RuleError,match='consent'):e.action('buy',dict(property_id=p.id),'blocked')
    assert e.world.cash('personal')==before
    t=clearance(e,p);assert t['improvement']>0
    fee=e.quote('buy',p.id)['legal_fee'];assert fee==100000-t['improvement']
    cost=e.quote('buy',p.id)['total'];before=e.world.cash('personal')
    e.action('buy',dict(property_id=p.id),'cleared-buy')
    assert p.owner=='personal' and p.basis==cost and e.world.cash('personal')==before-cost
    assert not any(k.startswith('income:') for k in e.world.accounts['personal'])
    assert e.world.systems['property_covenants'][-1]['property_id']==p.id
    e.validate()


def test_consent_is_buyer_specific_and_refusal_cannot_be_rerolled(game):
    e,l,b,_,_=setup(game);p=legal_property(e)
    clearance(e,p)
    with pytest.raises(RuleError,match='consent'):e.action('buy',dict(property_id=p.id,entity=b.id),'other-buyer')
    with pytest.raises(RuleError,match='already'):request(e,'personal','transfer_consent',target_id=p.id)
    # An internal counsel's poor negotiation can fail against the same disclosed facts.
    other=next(x for x in e.world.properties if x.id.startswith('covenant-') and x.id!=p.id)
    legal=TransactionLegal(e);office,t=request(e,'personal','transaction_review',target_id=other.id);deliver(e,office,3)
    office,t=request(e,'personal','transfer_consent',target_id=other.id)
    legal.finish(t,0)
    assert 'refused' in t['outcome'] and 'personal' not in legal.terms(other)['approved_for']


def test_covenant_future_work_is_reserved_then_can_be_satisfied(game):
    from economic_simulation.authority import cash_forecast
    from economic_simulation.property_operations import PropertyOperations
    e=Engine(copy.deepcopy(game.world));p=legal_property(e);clearance(e,p);e.action('buy',dict(property_id=p.id),'buy')
    legal=TransactionLegal(e);c=e.world.systems['property_covenants'][-1]
    assert any('covenant' in r['detail'].lower() for r in cash_forecast(e.world,'personal')['rows'])
    ops=PropertyOperations(e);ops.action('property_work',dict(property_id=p.id,system='roof',kind='replacement',provider='outside'),'roof')
    assert not any('covenant' in r['detail'].lower() for r in cash_forecast(e.world,'personal')['rows'])
    for _ in range(8):ops.tick();legal.tick();e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    assert c['status']=='satisfied' and not e.world.accounts['personal'].get('expense:contract_breach')
    e.validate()


def test_covenant_breach_is_dated_once_without_cash_invention(game):
    e=Engine(copy.deepcopy(game.world));p=legal_property(e);clearance(e,p);e.action('buy',dict(property_id=p.id),'buy')
    c=e.world.systems['property_covenants'][-1];cash=e.world.cash('personal')
    e.world.date=(date.fromisoformat(c['due'])+timedelta(days=1)).isoformat();legal=TransactionLegal(e);legal.tick();legal.tick()
    assert c['status']=='breached' and e.world.accounts['personal']['expense:contract_breach']==c['charge']
    assert e.world.cash('personal')==cash and e.world.accounts['personal']['liability:payable']==-c['charge']
    e.validate()


def test_supplier_agreement_pays_cash_and_projects_consume_credit_at_actual_rate(game):
    e,l,b,_,_=setup(game);office,c=agreement(e,b.id)
    credit=c['credit'];cash=e.world.cash(b.id)
    office.action('service_request',dict(recipient=b.id,department='accounting',mode='outside',provider='outside'),'report')
    task=e.world.systems['service_tasks'][-1]
    assert task['supplier_contract']==c['id'] and task['prepaid']==480*c['rate']
    assert e.world.cash(b.id)==cash and c['credit']==credit-task['prepaid']
    deliver(e,office,10)
    assert task['outside_cost']==480*c['rate']<480*150 and c['expense']==task['outside_cost']
    e.validate()


def test_agreement_daily_capacity_is_shared_and_priority_controls_delivery(game):
    e,l,b,_,_=setup(game);office,c=agreement(e,b.id)
    for priority in (3,1):office.action('service_request',dict(recipient=b.id,department='accounting',mode='outside',provider='outside',priority=priority),'report-'+str(priority))
    first,second=e.world.systems['service_tasks'][-2:];office.tick()
    assert first['worked']==0 and second['worked']==c['daily_capacity']
    assert c['used_today']==c['daily_capacity'];e.validate()


def test_cancelling_block_work_restores_credit_instead_of_cash(game):
    e,l,b,_,_=setup(game);office,c=agreement(e,b.id);cash=e.world.cash(b.id)
    office.action('service_request',dict(recipient=b.id,department='accounting',mode='outside',provider='outside'),'report')
    task=e.world.systems['service_tasks'][-1];office.tick();used=task['worked']
    office.action('cancel_service',dict(task_id=task['id']),'cancel')
    assert e.world.cash(b.id)==cash and c['available']==c['minutes']-used and task['prepaid']==0
    assert c['paid']==c['credit']+c['expense'];e.validate()


def test_expiry_writes_off_unassigned_credit_but_honors_reserved_work(game):
    e,l,b,_,_=setup(game);office,c=agreement(e,b.id)
    office.action('service_request',dict(recipient=b.id,department='accounting',mode='outside',provider='outside'),'report')
    task=e.world.systems['service_tasks'][-1];unused=c['credit'];cash=e.world.cash(b.id)
    e.world.date=(date.fromisoformat(c['expires'])+timedelta(days=1)).isoformat();office.tick()
    assert c['status']=='expired' and c['expired_cost']==unused and task['worked']>0 and e.world.cash(b.id)==cash
    office.action('cancel_service',dict(task_id=task['id']),'cancel-after-expiry')
    assert c['credit']==0 and c['expired_cost']+c['expense']==c['paid'] and e.world.cash(b.id)==cash
    e.validate()


def test_contract_cannot_be_used_by_another_account_or_changed_into_cash(game):
    e,l,b,_,_=setup(game);office,c=agreement(e,b.id)
    office.action('service_request',dict(recipient='personal',department='accounting',mode='outside',provider='outside'),'personal-report')
    assert not e.world.systems['service_tasks'][-1].get('supplier_contract')
    office.action('service_request',dict(recipient=b.id,department='accounting',mode='outside',provider='outside'),'company-report')
    task=e.world.systems['service_tasks'][-1]
    with pytest.raises(RuleError,match='already reserves'):office.action('outsource_service',dict(task_id=task['id']),'change')


def test_contract_purchase_counts_full_prepaid_commitment_and_scope(game):
    from test_authority import contract
    e,l,b,_,_=setup(game);office,t=request(e,b.id,'supplier_tender',service_department='legal');deliver(e,office,3)
    offer=next(o for o in e.world.systems['supplier_offers'] if o['status']=='open')
    e.world.date='2026-01-19';contract(e,b,period_limit=1000)
    before=copy.deepcopy(e.world.accounts)
    assert not l.perform(b,'supplier','accept_supplier_contract',dict(entity=b.id,offer_id=offer['id']),0,True,'Purchase service credit')
    assert e.world.accounts==before and not e.world.systems.get('supplier_contracts')


def test_contract_state_replays_and_reload_reconciles(game,tmp_path):
    from economic_simulation.persistence import Store
    act(game,'service_request',recipient='personal',department='purchasing',product='supplier_tender',service_department='legal',mode='outside',provider='outside')
    with game.store.connection() as source,sqlite3.connect(tmp_path/'replay.sqlite3') as dest:source.backup(dest)
    store=Store(tmp_path/'replay.sqlite3');left=copy.deepcopy(game.world);right=store.load()
    for _ in range(10):
        e=Engine(left);e.advance_day();e.validate();left=e.world
        e=Engine(right);e.advance_day();store.commit(e,right.revision);right=store.load()
    left.revision=right.revision;assert json.loads(json.dumps(left.to_dict()))==right.to_dict();store.audit(right)


def test_contract_pages_expose_disclosure_and_preserve_read_only_state(game):
    before=copy.deepcopy(game.world)
    p=next(p for p in game.world.properties if p.id.startswith('covenant-'))
    with client_for(game) as client:
        response=client.get('/?page=commercial_contracts')
        assert response.status_code==200 and 'Disclosed property terms' in response.text
        text=client.get('/?page=property&property_id='+p.id).text
        assert 'Review disclosed contract terms' in text and 'Closing and consent costs' in text
    assert game.world.to_dict()==before.to_dict()


def test_commercial_upgrade_preserves_accounts_and_has_recovery_backup(tmp_path):
    from economic_simulation.persistence import Store
    e=new_game();e.world.systems.update(version=3);e.world.systems.pop('commercial_contracts_version')
    before=copy.deepcopy(e.world);path=tmp_path/'previous.sqlite3';Store(path,initial=e)
    after=Store(path).load()
    assert after.accounts==before.accounts and after.employments==before.employments and after.date==before.date
    assert after.systems['version']==5 and len(list(tmp_path.glob('previous.before-commercial-contracts-*.sqlite3')))==1
    assert Store(path).load().to_dict()==after.to_dict()


def test_overloaded_contracted_task_still_surfaces_its_missed_deadline(game):
    e,l,b,_,_=setup(game);office,c=agreement(e,b.id)
    for priority in (3,1):office.action('service_request',dict(recipient=b.id,department='accounting',mode='outside',provider='outside',priority=priority),'work-'+str(priority))
    first,second=e.world.systems['service_tasks'][-2:]
    first['due']=second['due']=(date.fromisoformat(e.world.date)-timedelta(days=1)).isoformat()
    office.tick()
    assert first['worked']==0 and first['overdue_notified'] and any(r['title']=='Service deadline missed' for r in e.pause_reasons)


def test_specialist_requirement_cannot_be_bypassed_with_mixed_delivery(game):
    e,l,b,_,_=setup(game);p=legal_property(e);p.full_value=100000000
    legal=TransactionLegal(e);office,t=request(e,'personal','transaction_review',target_id=p.id);deliver(e,office,3)
    office.action('department_configure',dict(provider=b.id,department='legal'),'configure')
    office.action('service_request',dict(recipient='personal',department='legal',product='transfer_consent',target_id=p.id,provider=b.id,mode='mixed'),'mixed-consent')
    t=e.world.systems['service_tasks'][-1];deliver(e,office,5)
    assert t['requires_specialist'] and 'personal' not in legal.terms(p)['approved_for']
    office,retry=request(e,'personal','transfer_consent',target_id=p.id);deliver(e,office,5)
    assert 'personal' in legal.terms(p)['approved_for']
    with pytest.raises(RuleError,match='already'):request(e,'personal','transfer_consent',target_id=p.id)
    e.validate()


def test_small_preventive_job_does_not_hide_covenant_commitment(game):
    from economic_simulation.authority import cash_forecast
    from economic_simulation.property_operations import PropertyOperations
    from economic_simulation.navigation import navigation_view
    e=Engine(copy.deepcopy(game.world));p=legal_property(e);clearance(e,p);e.action('buy',dict(property_id=p.id),'buy')
    PropertyOperations(e).action('property_work',dict(property_id=p.id,system='roof',kind='preventive',provider='outside'),'small-job')
    assert any('covenant' in r['detail'].lower() for r in cash_forecast(e.world,'personal')['rows'])
    assert all('page=commercial_contracts' in c['url'] for c in navigation_view(e.world,'commercial_contracts','personal')['choices'])
