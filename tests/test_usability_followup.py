"""Regression coverage for the second usability study, using disposable campaigns."""
import copy
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_campaign_product import client_for
from test_property_scale import funded,buy,employee
from economic_simulation.domain import Engine,World,RuleError
from economic_simulation.service_office import ServiceOffice
from economic_simulation.legal_recovery import claim_summary
from economic_simulation.expansion import Expansion,opening_staff
from economic_simulation.business_models import Position,Employment,OPENING_ROLES
from economic_simulation.business_rules import BusinessRules
from economic_simulation.decision_inbox import items,inbox_view
from economic_simulation.skip_controls import should_pause
from economic_simulation.property_development import Development
from economic_simulation.property_scale_views import detail


def claim_world(amount=39000):
    e=funded();p=buy(e)
    claim=dict(id='warranty-test',owner='personal',property_id=p.id,amount=amount,status='open',created=e.world.date,fact='Documented callback on completed roof work.')
    e.world.systems['legal_claims']=[claim]
    return e,claim


def request(e,claim,**extra):
    return ServiceOffice(e).action('service_request',dict(recipient=claim['owner'],department='legal',matter='dispute',target_id=claim['id'],**extra),'request')


def test_small_claim_rejects_uneconomic_reserve_without_spending():
    e,c=claim_world();cash=e.world.cash('personal')
    with pytest.raises(RuleError,match='at most'):request(e,c)
    assert e.world.cash('personal')==cash
    assert not e.world.systems.get('service_tasks')
    row=next(r for r in inbox_view(e.world)['inbox_items'] if r['kind']=='claim')
    assert row['forms'][0]['action']=='close_legal_claim'
    e.action('close_legal_claim',dict(claim_id=c['id']),'close-claim')
    assert e.world.cash('personal')==cash and c['status']=='closed'
    assert not any(r['kind']=='claim' for r in items(e.world))
    e.validate()


def test_duplicate_and_failed_claim_cannot_reroll(monkeypatch):
    e,c=claim_world(1000000);request(e,c)
    with pytest.raises(RuleError,match='already queued'):request(e,c)
    with pytest.raises(RuleError,match='Cancel unfinished'):e.action('close_legal_claim',dict(claim_id=c['id']),'close-working')
    monkeypatch.setattr('economic_simulation.service_office.stable_roll',lambda *args:99)
    for _ in range(5):ServiceOffice(e).tick()
    t=e.world.systems['service_tasks'][0]
    assert t['status']=='complete' and c['status']=='open' and t['recovered']==0
    cash=e.world.cash('personal')
    with pytest.raises(RuleError,match='already attempted'):request(e,c)
    assert e.world.cash('personal')==cash
    assert claim_summary(e.world,c)['spent']==180000
    e.validate()


def test_legacy_uneconomic_request_refunds_only_unused_capacity():
    e,c=claim_world(1000000);request(e,c);ServiceOffice(e).tick()
    t=e.world.systems['service_tasks'][0];spent=t['outside_cost'];reserved=t['prepaid'];cash=e.world.cash('personal')
    c['amount']=39000
    restored=Engine(World.from_dict(e.world.to_dict()));ServiceOffice(restored).tick()
    t=restored.world.systems['service_tasks'][0]
    assert t['status']=='cancelled' and t['outside_cost']==spent
    assert restored.world.cash('personal')==cash+reserved
    assert restored.world.accounts['personal']['expense:outside_services']==spent
    assert any(r['kind']=='claim' for r in items(restored.world))
    restored.validate()


def test_internal_claim_does_not_allow_expensive_outsource_switch():
    e,c=claim_world();b,emp,person,rules=employee(e,'legal')
    office=ServiceOffice(e);office.action('department_configure',dict(provider=b.id,department='legal',staff=emp.id,regions=b.region),'configure')
    request(e,c,mode='internal',provider=b.id);t=e.world.systems['service_tasks'][0]
    cash=e.world.cash('personal')
    with pytest.raises(RuleError,match='at most'):office.action('outsource_service',dict(task_id=t['id']),'switch')
    assert t['mode']=='internal' and e.world.cash('personal')==cash


def startup(e):
    e.action('start_business',dict(industry='retail',name='Pending Hire Shop'),'start')
    b=e.world.businesses[-1];plan=next(p for p in e.world.systems['plans'] if p['entity']==b.id and p['kind']=='opening')
    e.world.date=plan['due'];rules=BusinessRules(e)
    for i,role in enumerate(OPENING_ROLES[b.industry]):
        person=rules.make_person(role);pos=Position(id='pending-pos-'+str(i),business_id=b.id,role=role);e.world.positions.append(pos)
        e.world.employments.append(Employment(id='pending-emp-'+str(i),person_id=person.id,employer=b.id,position_id=pos.id,salary=300000,weekly_hours=40,status='joining',start_date=(date.fromisoformat(e.world.date)+timedelta(days=3)).isoformat()))
    return b,plan


def test_accepted_hires_clear_stale_opening_alert_and_wait_for_start():
    e=funded();b,plan=startup(e)
    e.pause_reasons=[];e.events=[]
    decision=Expansion(e).decision('opening-staff:'+b.id,'Opening needs staff','Old gap',b.id)
    before=copy.deepcopy(e.world.to_dict())
    assert not any(r['title']=='Opening needs staff' for r in items(e.world))
    assert e.world.to_dict()==before
    Expansion(e).start_day()
    assert b.status=='developing' and 'Accepted hires start' in plan['phase']
    assert decision['status']=='resolved' and not should_pause(e)
    restored=Engine(World.from_dict(copy.deepcopy(e.world.to_dict())))
    for day in range(3):
        e=Engine(copy.deepcopy(e.world));restored=Engine(World.from_dict(copy.deepcopy(restored.world.to_dict())))
        e.advance_day();restored.advance_day()
        current=next(company for company in e.world.businesses if company.id==b.id)
        assert current.status==('operating' if day==2 else 'developing')
        assert e.world.to_dict()==restored.world.to_dict()


def test_actual_missing_role_still_stops_and_is_actionable():
    e=funded();b,plan=startup(e);e.world.employments[-1].status='ended'
    assert opening_staff(e.world,b)['missing']
    Expansion(e).start_day()
    assert b.status=='developing' and should_pause(e)
    assert any(r['title']=='Opening needs staff' for r in items(e.world))


def test_construction_view_reconciles_installed_and_reserved(game):
    act(game,'buy',property_id=next(p.id for p in game.world.properties if p.category=='land'))
    p=next(p for p in game.world.properties if p.owner and p.category=='land')
    e=Engine(game.world);e.post('personal','extra-funds','Test capital',{'asset:cash':100000000,'equity:capital':-100000000})
    Development(e).action(dict(property_id=p.id,blueprint='homes'),'build')
    land=p.basis;Development(e).tick();care=detail(e.world,p.id);job=care['development']
    assert care['building'] and not care['designs']
    assert care['acquisition_basis']==land and p.basis==land+job['spent']
    assert care['committed_basis']==land+job['spent']+job['prepaid']
    with client_for(game) as client:
        html=client.get('/?page=property&property_id='+p.id).text
        assert 'Construction capital still reserved' in html
        assert 'Choose a building' not in html and 'Vacant serviced land.' not in html
    e.validate()


def test_startup_validation_and_visible_controls(game):
    from economic_simulation.recovery_navigation import recovery_links
    assert recovery_links(game.world,'Use a business name of 2–80 characters.',dict(name=''))==[]
    with client_for(game) as client:
        html=client.get('/?page=expansion&action_focus=start_business').text
        assert 'minlength="2"' in html and 'maxlength="80"' in html
        assert '/static/usability.js?' in html
        assert 'data-paginate="15"' in html


def test_internal_claim_budget_stops_before_consuming_unaffordable_hours():
    from economic_simulation.qualified_capacity import estimated_cost,consume
    e,c=claim_world(1000);b,emp,person,rules=employee(e,'legal');e.world.date='2026-01-12'
    office=ServiceOffice(e);office.action('department_configure',dict(provider=b.id,department='legal',staff=emp.id,regions=b.region),'configure')
    request(e,c,mode='internal',provider=b.id);task=e.world.systems['service_tasks'][0]
    buckets,_=rules.work(b,date.fromisoformat(e.world.date));before=copy.deepcopy(buckets)
    price=estimated_cost(rules,b,buckets,[emp],120)
    assert buckets==before and price>c['amount']
    office.deliver(rules,b,buckets)
    assert task['status']=='cancelled' and task['internal_cost']==0 and buckets==before
    actual=consume(rules,b,buckets,[emp],120)
    assert actual[1]==price


def test_actual_supplier_price_is_used_for_claim_affordability():
    from economic_simulation.supplier_contracts import SupplierContracts
    e,c=claim_world(150000)
    e.world.systems['supplier_offers']=[dict(id='test-offer',buyer='personal',department='legal',supplier='Test counsel',status='open',valid_until='2027-01-01',minutes=1200,rate=100,daily_capacity=240,credit_days=60)]
    SupplierContracts(e).action(dict(entity='personal',offer_id='test-offer'),'buy-credit')
    request(e,c);task=e.world.systems['service_tasks'][0]
    assert task['prepaid']==120000 and task['outside_rate']==100
    e.validate()


def test_legacy_duplicate_claims_only_allow_first_unfinished_request():
    e,c=claim_world(1000000);request(e,c)
    first=e.world.systems['service_tasks'][0];duplicate=copy.deepcopy(first);duplicate['id']='legacy-duplicate'
    e.post('personal','duplicate-reserve','Previously funded work',{'asset:cash':-duplicate['prepaid'],'asset:prepaid_services':duplicate['prepaid']})
    e.world.systems['service_tasks'].append(duplicate)
    ServiceOffice(e).tick()
    assert first['worked']==240 and duplicate['worked']==0 and duplicate['status']=='cancelled'
    assert e.world.accounts['personal']['asset:prepaid_services']==first['prepaid']
    e.validate()


def test_claim_close_command_preview_does_not_close_record(game):
    e=Engine(game.world);p=game.world.properties[0]
    game.world.systems['legal_claims']=[dict(id='claim-preview',owner='personal',property_id=p.id,amount=39000,status='open',created=game.world.date,fact='Existing callback')]
    with client_for(game) as client:
        html=client.get('/?page=inbox').text
        assert 'data-action="close_legal_claim"' in html
        assert 'Legal work to date:' in html
        response=client.post('/api/preview',json=dict(action='close_legal_claim',args=dict(claim_id='claim-preview'),revision=game.world.revision,command_id='preview-claim-test'))
        assert response.status_code==200
    assert game.world.systems['legal_claims'][0]['status']=='open'
