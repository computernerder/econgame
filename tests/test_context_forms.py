import copy
import json
import re

import pytest

from test_game import game, act
from test_leadership import setup
from test_campaign_product import client_for
from economic_simulation.campaign_views import campaign_view
from economic_simulation.form_context import initial_state
from economic_simulation.ui_workflows import prepare
from economic_simulation.service_office import ServiceOffice
from economic_simulation.domain import RuleError


def request_form(world,scope,product='',page='home_office'):
    view=campaign_view(world,page,scope);prepare(view,world,scope)
    return next(f for f in view['forms'] if f['action']=='service_request'
                and next((x['value'] for x in f['fields'] if x['name']=='product'),'')==product)


def choose(form,**values):
    for field in form['fields']:
        if field['name'] in values:field['value']=values[field['name']]
    initial_state(form)
    return {f['name']:f for f in form['fields']}


def invoice(e,b,uid):
    b.receivables.append(dict(id=uid,amount=50000,due='2026-01-01',defaulted=True))
    e.post(b.id,'fixture-'+uid,'Customer work invoiced',{'asset:receivable':50000,'income:project':-50000})


def test_accounting_and_templates_do_not_ask_for_irrelevant_targets(game):
    e,l,b,_,_=setup(game);before=copy.deepcopy(e.world.to_dict())
    form=request_form(e.world,b.id)
    fields=choose(form)
    assert fields['matter']['hidden'] and fields['target_id']['hidden'] and fields['provider']['hidden']
    assert not form['context_errors']
    fields=choose(form,department='legal',matter='template')
    assert not fields['matter']['hidden'] and fields['target_id']['hidden']
    assert not fields['target_id']['required']
    assert e.world.to_dict()==before


def test_collection_targets_follow_receiving_account_and_exclude_busy_work(game):
    e,l,b,_,other=setup(game,True);second=l.rules.company(other)
    invoice(e,b,'own-invoice');invoice(e,second,'other-invoice')
    form=request_form(e.world,b.id)
    fields=choose(form,department='legal',matter='collection',recipient=b.id)
    assert [o['value'] for o in fields['target_id']['options']]==['own-invoice']
    fields=choose(form,recipient=other)
    assert [o['value'] for o in fields['target_id']['options']]==['other-invoice']
    e.action('service_request',dict(recipient=other,department='legal',matter='collection',target_id='other-invoice',mode='outside'),'queued-collection')
    form=request_form(e.world,other);fields=choose(form,department='legal',matter='collection')
    assert not fields['target_id']['options'] and form['context_errors']


def test_training_and_onboarding_only_offer_active_recipient_employees(game):
    e,l,b,_,other=setup(game,True)
    expected={emp.id for emp in e.world.employments if emp.employer==b.id and emp.status=='active'}
    for product in ('','onboarding'):
        form=request_form(e.world,b.id,product)
        fields=choose(form,**({'department':'training'} if not product else {}))
        assert {o['value'] for o in fields['target_id']['options']}==expected
        assert fields['target_id']['required']
        fields=choose(form,recipient=other)
        assert all(o['value'] not in expected for o in fields['target_id']['options'])


def test_internal_provider_needs_matching_department_and_county(game):
    e,l,b,_,other=setup(game,True)
    office=ServiceOffice(e)
    office.action('department_configure',dict(provider=b.id,department='hr',regions=b.region+','+l.rules.company(other).region),'hr-dept')
    form=request_form(e.world,other)
    fields=choose(form,mode='internal')
    assert not fields['provider']['hidden'] and not fields['provider']['options'] and form['context_errors']
    fields=choose(form,department='hr')
    assert [o['value'] for o in fields['provider']['options']]==[b.id]
    assert not form['context_errors']
    e.world.systems['departments'][b.id+':hr']['regions']=['Not covered']
    form=request_form(e.world,other);fields=choose(form,department='hr',mode='mixed')
    assert not fields['provider']['options'] and form['context_errors']
    fields=choose(form,mode='outside')
    assert fields['provider']['hidden'] and not form['context_errors']


def test_roles_and_it_services_follow_industry_and_existing_installations(game):
    e,l,b,_,other=setup(game,True)
    form=request_form(e.world,b.id,'role_search')
    fields=choose(form)
    assert 'cashier' in {o['value'] for o in fields['role']['options']}
    assert 'server' not in {o['value'] for o in fields['role']['options']}
    fields=choose(form,recipient=other)
    assert 'server' in {o['value'] for o in fields['role']['options']}
    assert 'cashier' not in {o['value'] for o in fields['role']['options']}
    form=request_form(e.world,b.id,'system_support')
    assert form['context_errors']
    e.action('service_request',dict(recipient=b.id,department='it',product='pos_deployment',mode='outside'),'pos-request')
    office=ServiceOffice(e)
    for _ in range(6):office.tick()
    form=request_form(e.world,b.id,'pos_deployment')
    assert b.id not in {o['value'] for o in choose(form)['recipient']['options']}


def test_form_html_hides_and_disables_irrelevant_controls_before_javascript(game):
    e,l,b,_,_=setup(game);game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html=client.get('/?page=home_office&scope='+b.id+'&action_focus=service_request').text
        focused=re.search(r'<section id="task-focus".*?</section>',html,re.S).group(0)
        for name in ('provider','matter','target_id'):
            assert re.search(r'<select name="'+name+r'"\s+disabled',focused)
        assert 'data-field-context' in focused and 'No transaction or employee target is needed' in focused
        from economic_simulation import __version__
        assert '/static/context_forms.js?v='+__version__ in html
    assert game.world.to_dict()==before


def test_service_backend_discards_stale_hidden_values_and_keeps_actual_accounting(game):
    e,l,b,_,_=setup(game)
    e.action('service_request',dict(recipient=b.id,department='accounting',mode='outside',provider='stale-company',matter='negotiation',target_id='stale-employee'),'clean-service')
    task=e.world.systems['service_tasks'][-1]
    assert task['provider']=='outside' and task['matter']=='routine' and task['target_id']==''
    assert task['prepaid']==480*150
    ServiceOffice(e).tick();ServiceOffice(e).tick()
    assert task['status']=='complete' and task['outside_cost']==480*150
    assert e.world.systems['management_reports'][-1]['business_id']==b.id
    e.validate()


def test_invalid_training_target_is_rejected_before_spending(game):
    e,l,b,_,other=setup(game,True)
    emp=next(emp for emp in e.world.employments if emp.employer==other and emp.status=='active')
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError,match='active employee at the receiving business'):
        act(game,'service_request',recipient=b.id,department='training',target_id=emp.id,mode='outside')
    assert game.world.to_dict()==before


def test_property_conversion_and_tenant_request_fields_follow_selected_work(game):
    e,l,b,_,_=setup(game)
    from test_service_projects import tenant
    from economic_simulation.property_requests import PropertyRequests
    p,_,_=tenant(e);PropertyRequests(e).tick()
    view=campaign_view(e.world,'property_workbench','personal');prepare(view,e.world,'personal')
    repair=next(f for f in view['forms'] if f['action']=='property_work')
    assert choose(repair)['use']['hidden']
    assert not choose(repair,kind='conversion')['use']['hidden']
    response=next(f for f in view['forms'] if f['action']=='respond_property_request')
    fields=choose(response,property_id=p.id)
    assert fields['request_id']['options']
    assert all(next(r for r in e.world.systems['property_requests'] if r['id']==o['value'])['property_id']==p.id for o in fields['request_id']['options'])
