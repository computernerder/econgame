import copy
from datetime import date, timedelta
import pytest
from test_game import game, act, step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine, RuleError, World
from economic_simulation.business_rules import BusinessRules
from economic_simulation.customer_collections import CustomerCollections, busy
from economic_simulation.industry_operations import IndustryOperations
from economic_simulation.service_office import ServiceOffice
from economic_simulation.decision_inbox import items
from economic_simulation.simulation_support import stable_roll


def setup(game, defaulted=True, identifier='existing-customer', amount=100003):
    bid = acquire(game)
    e = Engine(copy.deepcopy(game.world))
    b = next(b for b in e.world.businesses if b.id == bid)
    # This suite exercises the player's explicit manual-collection workflow.
    b.authority['routine_management']={'collections':False}
    BusinessRules(e).invoice(b, amount, 'test_customer', identifier, 14)
    invoice = b.receivables[-1]
    invoice.update(defaulted=defaulted, overdue_since=e.world.date)
    game.store.commit(e, game.world.revision)
    game.world = e.world
    return e, b, invoice


def tomorrow(e, days=1):
    e.world.date = (date.fromisoformat(e.world.date)+timedelta(days=days)).isoformat()


def request(e, b, invoice, method):
    return e.action('recover_invoice', dict(entity=b.id, invoice_id=invoice['id'], method=method), 'recovery-'+method)


def test_risk_is_one_percent_default_eight_percent_late_not_five_percent(game, monkeypatch):
    e,b,_=setup(game);b.industry='trades';counts={'default':0,'late':0,'paid':0}
    for value in range(100):
        monkeypatch.setattr('economic_simulation.industry_operations.stable_roll',lambda *a,v=value:v)
        invoice=dict(id='risk-'+str(value),amount=100,due=e.world.date)
        paid=IndustryOperations(e).collection(b,invoice)
        counts['paid' if paid else 'default' if invoice.get('defaulted') else 'late']+=1
    assert counts=={'default':1,'late':8,'paid':91}


def test_legacy_default_not_erased_and_late_invoice_retries_once(game,monkeypatch):
    e,b,invoice=setup(game);b.industry='trades'
    monkeypatch.setattr('economic_simulation.industry_operations.stable_roll',lambda *a:99)
    assert not IndustryOperations(e).collection(b,invoice)
    invoice.update(defaulted=False,collection_attempted=True,due=e.world.date)
    before=e.world.cash(b.id);income=e.world.accounts[b.id]['income:test_customer']
    CustomerCollections(e).collect(b);CustomerCollections(e).collect(b)
    assert not b.receivables and e.world.cash(b.id)==before+100003
    assert e.world.accounts[b.id]['income:test_customer']==income
    e.validate()


@pytest.mark.parametrize('method,days,fee',[('reminder',3,0),('agency',14,25000)])
def test_recovery_waits_then_receives_cash_once_without_new_revenue(game,monkeypatch,method,days,fee):
    e,b,invoice=setup(game)
    monkeypatch.setattr('economic_simulation.customer_collections.stable_roll',lambda *a:0)
    before=e.world.cash(b.id);income=e.world.accounts[b.id]['income:test_customer']
    request(e,b,invoice,method);CustomerCollections(e).collect(b)
    assert e.world.cash(b.id)==before and invoice in b.receivables
    tomorrow(e,days);CustomerCollections(e).collect(b);CustomerCollections(e).collect(b)
    assert not b.receivables and e.world.cash(b.id)==before+100003-fee
    assert e.world.accounts[b.id].get('expense:collection_fees',0)==fee
    assert e.world.accounts[b.id]['income:test_customer']==income
    assert sum(h['gross'] for h in e.world.systems['collection_history'])==100003
    e.validate()


def test_three_installments_reconcile_odd_cents_and_survive_serialization(game,monkeypatch):
    e,b,invoice=setup(game,defaulted=False)
    monkeypatch.setattr('economic_simulation.customer_collections.stable_roll',lambda *a:0)
    before=e.world.cash(b.id);request(e,b,invoice,'plan');tomorrow(e,3);CustomerCollections(e).collect(b)
    assert invoice['recovery']['status']=='installments' and e.world.cash(b.id)==before
    amounts=[]
    for day in range(3):
        e=Engine(World.from_dict(e.world.to_dict()));b=next(x for x in e.world.businesses if x.id==b.id)
        tomorrow(e,10);CustomerCollections(e).collect(b);e.validate()
        amounts.append(e.world.accounts[b.id]['asset:receivable'])
    assert amounts==[66668,33333,0] and e.world.cash(b.id)==before+100003


def test_missed_installment_keeps_prior_payment_and_returns_to_inbox(game,monkeypatch):
    e,b,invoice=setup(game)
    monkeypatch.setattr('economic_simulation.customer_collections.stable_roll',lambda w,key:0 if key.endswith('installment:2') else 20)
    request(e,b,invoice,'plan');tomorrow(e,3);CustomerCollections(e).collect(b)
    assert not any(r['kind']=='invoice' for r in items(e.world))
    tomorrow(e,10);CustomerCollections(e).collect(b);assert invoice['amount']==66668
    tomorrow(e,10);CustomerCollections(e).collect(b)
    assert invoice['amount']==66668 and invoice['recovery']['status']=='failed'
    assert any(r['kind']=='invoice' and r['amount']==66668 for r in items(e.world))
    assert any(r['title']=='Customer recovery needs review' for r in e.events)
    assert any(r['title']=='Customer recovery needs review' for r in e.pause_reasons)
    e.validate()


def test_failed_agency_costs_nothing_and_repeat_cannot_reroll(game,monkeypatch):
    e,b,invoice=setup(game)
    monkeypatch.setattr('economic_simulation.customer_collections.stable_roll',lambda *a:99)
    before=e.world.cash(b.id);request(e,b,invoice,'agency');tomorrow(e,14);CustomerCollections(e).collect(b)
    assert invoice['amount']==100003 and e.world.cash(b.id)==before
    with pytest.raises(RuleError,match='already been attempted'):request(e,b,invoice,'agency')
    request(e,b,invoice,'plan')
    e.validate()


@pytest.mark.parametrize('action',['recover_invoice','write_off_invoice','service_request'])
def test_concurrent_actions_cannot_double_collect_or_write_off(game,action):
    e,b,invoice=setup(game);request(e,b,invoice,'agency')
    args=dict(entity=b.id,invoice_id=invoice['id'],method='plan',recipient=b.id,provider='outside',department='legal',matter='collection',target_id=invoice['id'])
    with pytest.raises(RuleError,match='in progress'):e.action(action,args,'duplicate')
    assert not e.world.systems.get('service_tasks') and invoice['amount']==100003


def test_writeoff_records_only_remaining_loss_after_partial_payment(game,monkeypatch):
    e,b,invoice=setup(game)
    monkeypatch.setattr('economic_simulation.customer_collections.stable_roll',lambda w,key:0 if key.endswith('installment:2') else 20)
    request(e,b,invoice,'plan');tomorrow(e,3);CustomerCollections(e).collect(b)
    tomorrow(e,10);CustomerCollections(e).collect(b);tomorrow(e,10);CustomerCollections(e).collect(b)
    before=e.world.cash(b.id)
    e.action('write_off_invoice',dict(entity=b.id,invoice_id=invoice['id']),'loss')
    assert not b.receivables and e.world.cash(b.id)==before
    assert e.world.accounts[b.id]['expense:bad_debt']==66668
    assert e.world.systems['collection_history'][-1]['loss']==66668
    e.validate()


def test_legal_is_preconfigured_blocks_parallel_work_and_collects_early_default(game):
    e,b,invoice=setup(game);invoice.pop('overdue_since')
    args=dict(recipient=b.id,provider='outside',department='legal',matter='collection',target_id=invoice['id'])
    before=e.world.cash(b.id);e.action('service_request',args,'legal')
    assert e.world.cash(b.id)==before-180000 and busy(e.world,b.id,invoice)
    with pytest.raises(RuleError,match='in progress'):request(e,b,invoice,'reminder')
    with pytest.raises(RuleError,match='in progress'):e.action('service_request',args,'legal-duplicate')
    task=e.world.systems['service_tasks'][-1]
    ServiceOffice(e).legal_result(task,100)
    assert not b.receivables and task['recovered']==100003
    e.validate()


def test_inbox_opens_options_for_exact_invoice_not_writeoff(game):
    e,b,invoice=setup(game);before=copy.deepcopy(game.world.to_dict())
    row=next(r for r in items(game.world) if r['kind']=='invoice')
    assert row['action']=='recover_invoice'
    with client_for(game) as client:
        html=client.get(row['url']).text
        assert 'open id="inbox-target"' in html
        assert 'Send a free reminder' in html and 'Propose three installments' in html and 'Use a collection agency' in html
        assert html.index('Choose a recovery option')<html.index('Write off the remaining balance')
        assert 'value="'+invoice['id']+'"' in html and '$1,800' in html and '25%' in html
        assert 'Customer invoices outstanding · manage collections' in client.get('/?page=business&business_id='+b.id).text
    assert game.world.to_dict()==before


def test_saved_recovery_keeps_its_focused_card_and_next_date_visible(game):
    _,b,invoice=setup(game)
    url=next(r['url'] for r in items(game.world) if r['kind']=='invoice')
    act(game,'recover_invoice',entity=b.id,invoice_id=invoice['id'],method='agency')
    assert not any(r['kind']=='invoice' for r in items(game.world))
    with client_for(game) as client:
        html=client.get(url).text
        assert 'open id="inbox-target"' in html and 'No further decision is required' in html
        assert 'Use a collection agency · response ' in html


def test_legal_rejects_other_accounts_invoice_without_charging(game):
    _,b,invoice=setup(game);before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError,match='belonging to the receiving account'):
        act(game,'service_request',recipient='personal',provider='outside',department='legal',matter='collection',target_id=invoice['id'])
    assert game.world.to_dict()==before


def test_legal_partial_recovery_has_a_remaining_decision_and_no_repeated_attempt(game,monkeypatch):
    e,b,invoice=setup(game)
    args=dict(recipient=b.id,provider='outside',department='legal',matter='collection',target_id=invoice['id'])
    e.action('service_request',args,'legal')
    task=e.world.systems['service_tasks'][-1]
    monkeypatch.setattr('economic_simulation.service_office.stable_roll',lambda *a:0)
    ServiceOffice(e).progress(task,task['remaining'],75)
    assert invoice['amount']==25001 and task['recovered']==75002
    assert any(r['title']=='Customer recovery needs review' for r in e.pause_reasons)
    assert any(r['kind']=='invoice' for r in items(e.world))
    with pytest.raises(RuleError,match='already completed'):e.action('service_request',args,'again')
    request(e,b,invoice,'agency')


def test_invalid_entity_future_invoice_and_unknown_method_are_atomic(game):
    e,b,invoice=setup(game);before=copy.deepcopy(game.world.to_dict())
    for args in [dict(entity='personal',invoice_id=invoice['id'],method='agency'),dict(entity=b.id,invoice_id='missing',method='agency'),dict(entity=b.id,invoice_id=invoice['id'],method='instant_cash')]:
        with pytest.raises(RuleError):act(game,'recover_invoice',**args)
        assert game.world.to_dict()==before
    invoice.pop('overdue_since');invoice.pop('defaulted')
    with pytest.raises(RuleError,match='overdue'):request(e,b,invoice,'reminder')


def test_live_command_save_load_idempotence_and_daily_batch_equivalence(game):
    # Use an actual seeded successful agency outcome, without mocking the time loop.
    identifier=next('persist-'+str(n) for n in range(100) if stable_roll(game.world,'invoice-recovery:persist-'+str(n)+':agency')<65)
    _,b,invoice=setup(game,identifier=identifier)
    command='persist-agency';args=dict(entity=b.id,invoice_id=invoice['id'],method='agency')
    revision=game.world.revision
    first=game.execute('recover_invoice',args,revision,command)
    assert game.execute('recover_invoice',args,revision,command)==first
    saved=game.store.load();assert saved.to_dict()==game.world.to_dict()
    grouped=Engine(copy.deepcopy(saved))
    for _ in range(14):grouped.advance_day()
    step(game,14)
    # Revisions count store commits, not simulated events.
    grouped.world.revision=game.world.revision
    assert grouped.world.to_dict()==game.world.to_dict()
    assert not any(r['id']==identifier for r in next(x for x in game.world.businesses if x.id==b.id).receivables)
    game.store.audit(game.world)


def test_closed_business_recovery_uses_same_dated_pipeline(game,monkeypatch):
    e,b,invoice=setup(game)
    monkeypatch.setattr('economic_simulation.customer_collections.stable_roll',lambda *a:0)
    from economic_simulation.distress import Distress
    Distress(e).close(b,'Test closure')
    request(e,b,invoice,'agency');tomorrow(e,14);Distress(e).tick()
    assert invoice not in b.receivables and e.world.accounts[b.id]['expense:collection_fees']==25000
    e.validate()
