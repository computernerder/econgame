import copy
import json
from datetime import date, timedelta

import pytest
from test_game import game, act, step
from test_campaign_product import client_for
from test_recovery_navigation import pending
from economic_simulation.application import Game
from economic_simulation.campaign import Campaign
from economic_simulation.domain import Engine, RuleError
from economic_simulation.skip_controls import DEFAULTS, REQUIRED, allowed, preferences, resume_target, should_pause


@pytest.mark.parametrize('title', ['Property work completed','Training completed','New employee started',
    'Renovation complete','Recruitment applicants arrived','Restaurant expansion completed','Fixed-fee project completed'])
def test_routine_updates_default_to_log_but_explicit_preference_still_stops(title):
    event=dict(title=title,financial_amount=None)
    assert not allowed({},event)
    assert allowed(dict(pause_routine=True),event)


@pytest.mark.parametrize('title',sorted(REQUIRED))
def test_quiet_mode_never_suppresses_required_approval_or_guardrail(title):
    assert allowed(dict(pause_routine=False,financial_pause_threshold=1000000000),dict(title=title,financial_amount=1))


def test_effective_defaults_preserve_explicit_old_save_choices():
    original={}
    assert preferences(original)==DEFAULTS and original=={}
    assert preferences(dict(pause_routine=True,financial_pause_threshold=0))==dict(pause_routine=True,financial_pause_threshold=0)
    assert not allowed({},dict(title='Funds needed',financial_amount=99999))
    assert allowed({},dict(title='Funds needed',financial_amount=100000))
    assert allowed({},dict(title='Employee departure'))


def test_handled_issues_do_not_leave_an_anonymous_pause(game):
    e=Engine(copy.deepcopy(game.world))
    e.event('Customer non-payment','Manager collected the invoice.',True)
    e.events[-1].update(handled_by='Store manager',pause_suppressed=True)
    e.pause_reasons.clear()
    assert not should_pause(e,True)


def test_prior_day_event_is_not_replayed_as_a_current_blocker(game):
    e=Engine(copy.deepcopy(game.world))
    e.event('Employee departure','Yesterday’s event',True)
    assert should_pause(e,True)
    e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat()
    e.pause_reasons.clear()
    assert not should_pause(e,True)
    assert not e.events[-1]['pause_suppressed']
    assert e.pause_details==[] and e.pause_reason_text==''
    e.events.clear()
    assert not should_pause(e,True)


def test_closed_decision_is_not_reannounced_and_unrelated_issues_still_stop(game):
    e=Engine(copy.deepcopy(game.world));c=Campaign(e)
    decision=c.decision('known-issue','Operating warning','Needs attention')
    c.choose(dict(decision_id=decision['id'],choice='acknowledge'))
    assert not should_pause(e,True)
    e.pause_reasons.clear()
    assert c.decision('known-issue','Operating warning','Already handled') is decision
    assert not e.pause_reasons and not should_pause(e,True)
    c.decision('separate-issue','Operating warning','Different issue')
    assert should_pause(e,True)


def test_approval_resolved_same_day_does_not_interrupt_and_required_reason_leads(game):
    _,request=pending(game)
    e=Engine(copy.deepcopy(game.world))
    saved=next(r for r in e.world.systems['management_requests'] if r['id']==request['id'])
    e.event('Owner approval needed','Stock approval',True,financial_amount=10)
    e.events[-1]['management_id']=saved['id']
    saved['status']='completed'
    assert not should_pause(e,True)
    assert e.events[-1]['pause_suppressed']
    e.world.systems['settings']['pause_routine']=True
    e.event('Training completed','Finished',True)
    saved['status']='open'
    assert should_pause(e,True) and e.pause_reason_text=='Owner approval needed'
    assert e.pause_details[0]['detail']=='Stock approval'


def test_real_completion_skip_has_digest_and_matches_daily_simulation(game,tmp_path):
    act(game,'buy',property_id=game.world.properties[0].id)
    act(game,'refresh',property_id=game.world.properties[0].id)
    daily=Engine(copy.deepcopy(game.world))
    due=game.world.properties[0].due
    target=(date.fromisoformat(due)+timedelta(days=2)).isoformat()
    days=(date.fromisoformat(target)-date.fromisoformat(game.world.date)).days
    for _ in range(days):daily.advance_day()
    act(game,'advance',target=target)
    game.worker.join(30)
    assert not game.progress['running'] and game.world.date==target,game.progress
    assert dict(title='Renovation complete',count=1) in game.progress['digest']
    actual,expected=game.world.to_dict(),daily.world.to_dict()
    for state in (actual,expected):
        state.pop('revision');state['systems'].pop('time_skip',None)
    assert json.loads(json.dumps(actual))==json.loads(json.dumps(expected))
    assert not resume_target(game.world)
    page=client_for(game).get('/').text
    assert 'Updates recorded without stopping' in page
    game.store.audit(game.world)


def test_blocked_resume_survives_reload_and_cannot_bypass_approval(game):
    _,request=pending(game)
    accounts=copy.deepcopy(game.world.accounts)
    act(game,'advance',period='month',pause_routine=False,financial_pause_threshold=100000)
    game.worker.join(10)
    target=game.progress['target']
    assert game.progress['completed']==0 and resume_target(game.world)==target
    with client_for(game) as client:
        text=client.get('/').text
        assert 'data-resume-target="'+target+'"' in text
        assert '#management:'+request['id'] in text
    restored=Game(game.store.path)
    try:
        assert resume_target(restored.world)==target
        assert 'Resume to '+target in client_for(restored).get('/').text
        act(restored,'advance',target=target)
        restored.worker.join(10)
        assert restored.progress['completed']==0 and restored.world.accounts==accounts
        assert restored.world.systems['management_requests'][-1]['status']=='open'
    finally:restored.close()


def test_recovery_day_keeps_original_target_and_new_plan_replaces_it(game):
    e=Engine(copy.deepcopy(game.world))
    e.world.systems['time_skip']=dict(target='2026-03-01',started=e.world.date)
    game.store.commit(e,game.world.revision);game.world=e.world
    act(game,'advance',period='day');game.worker.join(10)
    assert resume_target(game.world)=='2026-03-01'
    act(game,'advance',period='week');game.worker.join(10)
    assert game.world.date=='2026-01-09' and 'time_skip' not in game.world.systems
    assert not resume_target(game.world)


def test_advance_preferences_are_atomic_and_web_controls_use_whole_dollars(game):
    before=game.world.to_dict()
    for args in [dict(target=game.world.date,pause_routine=True),dict(period='week',financial_pause_threshold=-1)]:
        with pytest.raises(RuleError):act(game,'advance',**args)
        assert game.world.to_dict()==before and game.store.load().to_dict()==json.loads(json.dumps(before))
    with client_for(game) as client:
        text=client.get('/').text
        assert 'id="skip-quiet"' in text and 'id="skip-minimum"' in text
        assert 'Financial pause minimum: $1,000' in text
        payload=dict(action='advance',args=dict(period='day',pause_routine=True,financial_pause_threshold_dollars='2000'),revision=game.world.revision,command_id='advance-with-preferences')
        response=client.post('/api/command',json=payload)
        assert response.status_code==200
        game.worker.join(10)
        after=game.world.to_dict()
        assert client.post('/api/command',json=payload).status_code==200
        assert game.world.to_dict()==after
    assert game.world.systems['settings']['pause_routine']
    assert game.world.systems['settings']['financial_pause_threshold']==200000
    game.store.audit(game.world)
