import copy
from datetime import date,timedelta
import pytest
from test_game import game,step
from test_leadership import setup
from test_authority import contract
from test_property_services import property_for,request
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError
from economic_simulation.leadership import Leadership
from economic_simulation.authority import Authority
from economic_simulation.routine_management import RoutineManagement,policy
from economic_simulation.customer_collections import CustomerCollections
from economic_simulation.property_services import PropertyServices,care
from economic_simulation.business_rules import BusinessRules
from economic_simulation.decision_inbox import items
from economic_simulation.skip_controls import should_pause


def team(game):
    e,l,b,manager,second=setup(game,True)
    director=next(emp for emp in l.rules.staff(second) if l.rules.position(emp.position_id).role=='manager')
    l.action('director_assign',dict(employment_id=director.id,business_id=b.id,limit=10000000),'director')
    b.authority.update(enabled=True,purchasing_limit=2000000)
    return e,l,b,manager,director


def owned_property(e,b):
    e.action('fund_business',dict(business_id=b.id,amount=15000000),'property-funding')
    p=property_for(e,b.id);p.region=b.region
    PropertyServices(e).initialize()
    return p


def invoice(e,b,name='routine-invoice',amount=100000):
    BusinessRules(e).invoice(b,amount,'routine_customer',name,14)
    r=b.receivables[-1];r.update(defaulted=True,overdue_since=e.world.date)
    return r


def test_manager_runs_daily_work_director_handles_growth(game):
    e,l,b,manager,director=team(game)
    assert l.actor(b)==(None,manager)
    assert l.actor(b,'upgrade_business')[1].id==director.id
    assert l.actor(b,'annual_raise',{'employment_id':manager.id})[1].id==director.id
    assert l.perform(b,'routine-stock','restock',dict(business_id=b.id,units=1),b.unit_cost,True,'Routine stock')
    row=e.world.systems['authority_audit'][-1]
    assert row['actor']==manager.id and row['actor_role']=='Manager'
    assert row['charged_to']==['manager:'+b.id] and l.director(b.id)[0]['spent']==0
    assert l.perform(b,'equipment-growth','upgrade_business',dict(business_id=b.id),max(500000,b.equipment//4),True,'Equipment growth')
    assert e.world.systems['authority_audit'][-1]['actor']==director.id


def test_director_only_covers_missing_or_absent_manager(game):
    e,l,b,manager,director=team(game)
    manager.leave_until=e.world.date
    assert l.actor(b)[1].id==director.id
    assert l.perform(b,'cover-stock','restock',dict(business_id=b.id,units=1),b.unit_cost,True,'Cover stock')
    assert e.world.systems['authority_audit'][-1]['actor_role']=='Director'
    manager.leave_until=None
    assert l.actor(b)==(None,manager)
    manager.status='ended'
    assert l.actor(b)[1].id==director.id


def test_manager_limit_is_not_bypassed_by_available_director(game):
    e,l,b,manager,director=team(game);b.authority['purchasing_limit']=1
    r=invoice(e,b);r['recovery_attempts']=['reminder','plan'];before=e.world.cash(b.id)
    RoutineManagement(e).tick()
    assert not r.get('recovery') and e.world.cash(b.id)==before
    req=next(r for r in e.world.systems['management_requests'] if r['action']=='recover_invoice')
    assert req['actor']==manager.id and req['actor_role']=='Manager'
    assert l.director(b.id)[0]['spent']==0
    assert should_pause(e)


def test_disabled_manager_does_not_turn_director_into_a_policy_bypass(game):
    e,l,b,manager,director=team(game);b.authority['enabled']=False
    assert l.actor(b)[1] is None
    assert l.actor(b,'upgrade_business')[1].id==director.id


def test_free_collection_runs_without_headquarters_and_is_audited(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=0)
    r=invoice(e,b);before=e.world.cash(b.id)
    RoutineManagement(e).tick()
    assert r['recovery']['method']=='reminder' and e.world.cash(b.id)==before
    assert e.world.systems['authority_audit'][-1]['actor']==manager.id
    assert not any(i['kind']=='invoice' for i in items(e.world))


def test_same_day_manager_handling_suppresses_only_its_payment_pause(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=0)
    r=invoice(e,b)
    e.event('Customer default',b.name+' · '+r['id'],True,financial_amount=r['amount'],invoice_id=r['id'])
    e.event('Safety inspection','A separate problem',True)
    RoutineManagement(e).tick()
    assert should_pause(e) and e.pause_reason_text=='Safety inspection'
    assert next(x for x in e.events if x['title']=='Customer default')['handled_by']==l.rules.person(manager.person_id).name


def test_collection_progresses_to_plan_then_agency_and_accounts_for_fee_commitment(game,monkeypatch):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=1000000)
    r=invoice(e,b,amount=1000003)
    monkeypatch.setattr('economic_simulation.customer_collections.stable_roll',lambda *a:99)
    routines=RoutineManagement(e);routines.tick()
    for day,expected in [('2026-01-15','plan'),('2026-01-19','agency')]:
        e.world.date=day;CustomerCollections(e).collect(b);routines.tick()
        assert r['recovery']['method']==expected
    audit=e.world.systems['authority_audit'][-1]
    assert audit['commitment']==250000 and audit['cash_cost']==0
    e.validate()


def test_whole_agency_commitment_cannot_be_understated(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=1000)
    r=invoice(e,b,amount=100000)
    assert not l.perform(b,'lie','recover_invoice',dict(entity=b.id,invoice_id=r['id'],method='agency'),0,True,'Agency')
    assert not r.get('recovery')
    assert e.world.systems['management_requests'][-1]['cost']==25000


def test_full_plans_respect_monthly_budget_and_do_not_split(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=1000000)
    p=owned_property(e,b);facts=e.world.systems['property_care'][p.id];facts.update(cleanliness=20,grounds=20)
    full=PropertyServices(e).quote(p,'cleaning',4)['total']
    RoutineManagement(e).action(dict(business_id=b.id,period_limit=full))
    RoutineManagement(e).tick()
    jobs=e.world.systems['property_service_jobs'];assert len(jobs)==1 and jobs[0]['visits']==4 and jobs[0]['paid']==full
    assert any(r['action']=='property_service' and 'monthly budget' in r['detail'] for r in e.world.systems['management_requests'])
    before=copy.deepcopy(e.world.accounts);RoutineManagement(e).tick();assert e.world.accounts==before
    e.validate()


def test_security_renews_on_schedule_and_cancellation_stops_renewal(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=1000000)
    p=owned_property(e,b);p.usable_area=100
    job=request(e,p,kind='security',visits=1,interval=7)
    PropertyServices(e).tick();assert job['status']=='complete'
    RoutineManagement(e).tick();assert len(e.world.systems['property_service_jobs'])==1
    e.world.date='2026-01-19';RoutineManagement(e).tick()
    new=e.world.systems['property_service_jobs'][-1]
    assert new['id']!=job['id'] and new['kind']=='security' and new['interval']==7 and new['visits']==1
    e.action('cancel_property_service',dict(job_id=new['id']),'cancel')
    e.world.date='2026-01-26';RoutineManagement(e).tick()
    assert len(e.world.systems['property_service_jobs'])==2
    e.validate()


def test_manager_never_spends_from_players_personal_property_account(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=1000000)
    p=property_for(e);PropertyServices(e).initialize();e.world.systems['property_care'][p.id]['cleanliness']=0
    before=e.world.cash('personal');RoutineManagement(e).tick()
    assert not e.world.systems.get('property_service_jobs') and e.world.cash('personal')==before


def test_care_opt_out_is_not_overridden_by_old_property_automation(game):
    from economic_simulation.operating_automation import OperatingAutomation
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=1000000)
    p=owned_property(e,b);e.world.systems['property_care'][p.id].update(cleanliness=10,grounds=10)
    OperatingAutomation(e).action(dict(business_id=b.id,property_operations=True))
    RoutineManagement(e).action(dict(business_id=b.id,property_care=False))
    OperatingAutomation(e).tick()
    assert not e.world.systems.get('property_service_jobs')


def test_explicit_parent_permissions_still_apply_to_routine_manager(game):
    e,l,b,manager,director=team(game);r=invoice(e,b)
    parent=contract(e,b,target='director:'+director.id,contracts='prohibit')
    contract(e,b,parent=parent,contracts='prohibit')
    RoutineManagement(e).tick()
    assert not r.get('recovery') and l.director(b.id)[0]['spent']==0
    assert 'prohibits' in e.world.systems['management_requests'][-1]['detail']


def test_routine_capacity_is_finite_for_one_manager(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=0)
    for n in range(15):invoice(e,b,'invoice-'+str(n))
    RoutineManagement(e).tick();RoutineManagement(e).tick()
    assert sum(bool(r.get('recovery')) for r in b.receivables)==12
    assert len([r for r in e.world.systems['authority_audit'] if r['action']=='recover_invoice'])==12


def test_manager_policies_and_both_authority_levels_are_visible_and_read_only(game):
    e,l,b,manager,director=team(game);game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as c:
        html=c.get('/?page=management').text
        assert 'Routine care and collections' in html and 'Director oversight' in html
        assert 'name="target" value="manager:'+b.id+'"' in html
        assert 'name="target" value="director:'+director.id+'"' in html
        assert 'Managers handle daily operations' in html
        assert 'Manager policies and action log' in c.get('/?page=property_services').text
    assert game.world.to_dict()==before


def test_daily_batch_and_save_load_preserve_manager_actions(game):
    e,l,b,manager,_=setup(game);b.authority.update(enabled=True,purchasing_limit=1000000)
    invoice(e,b);game.store.commit(e,game.world.revision);game.world=e.world
    batched=Engine(copy.deepcopy(game.store.load()))
    for _ in range(8):batched.advance_day()
    step(game,8);batched.world.revision=game.world.revision
    assert batched.world.to_dict()==game.world.to_dict()
    assert any(r.get('actor')==manager.id and r['action']=='recover_invoice' for r in game.world.systems['authority_audit'])
    game.store.audit(game.world)


@pytest.mark.parametrize('industry',['cleaning','security'])
def test_owned_provider_selection_requires_available_qualified_capacity(game,industry):
    from test_new_industries import purchase
    bid=purchase(game,industry);e=Engine(copy.deepcopy(game.world));e.world.date='2026-01-19'
    b=BusinessRules(e).company(bid);p=property_for(e);p.region=b.region;p.usable_area=100
    routines=RoutineManagement(e)
    assert routines.provider(p,industry,True)==bid
    assert routines.provider(p,industry,False)=='outside'
    staff=BusinessRules(e).staff(bid)
    if industry=='security':
        for emp in staff:BusinessRules(e).person(emp.person_id).licenses['security_guard']='2025-01-01'
    else:
        for emp in staff:emp.leave_until=e.world.date
    assert routines.provider(p,industry,True)=='outside'


def test_owned_provider_is_not_preferred_when_its_queue_is_full(game):
    from test_new_industries import purchase
    bid=purchase(game,'cleaning');e=Engine(copy.deepcopy(game.world));e.world.date='2026-01-19'
    b=BusinessRules(e).company(bid);p=property_for(e);p.region=b.region;p.usable_area=100
    request(e,p,provider=bid)
    assert RoutineManagement(e).provider(p,'cleaning',True)=='outside'
