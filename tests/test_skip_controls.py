import copy
from datetime import date,timedelta
from pathlib import Path
import pytest
from test_game import game,act
from test_campaign_product import client_for
from economic_simulation.application import Game
from economic_simulation.domain import Engine
from economic_simulation.campaign import Campaign
from economic_simulation.skip_controls import should_pause


@pytest.mark.parametrize('amount,expected',[(0,False),(99999,False),(100000,True),(100001,True),(-100000,True)])
def test_financial_threshold_boundary_and_event_retention(game,amount,expected):
    e=Engine(copy.deepcopy(game.world));e.world.systems['settings']['financial_pause_threshold']=100000
    e.event('Financial test','Recorded event',True,financial_amount=amount)
    assert should_pause(e,True)==expected
    assert e.world.events[-1]['financial_amount']==amount
    assert e.world.events[-1]['pause_suppressed']==(not expected)


def test_general_events_and_explicit_cash_alert_still_pause(game):
    e=Engine(copy.deepcopy(game.world));e.world.systems['settings'].update(financial_pause_threshold=100000,pause_routine=False)
    e.event('Funds needed','Small bill',True,financial_amount=2000)
    e.event('Employee departure','Recruit a replacement',True)
    assert should_pause(e,True) and e.pause_reason_text=='Employee departure'
    e.pause_reasons=[]
    e.event('Renovation complete','Finished',True)
    assert not should_pause(e,True)
    e.event('Personal cash threshold reached','Explicit cash alert',True)
    assert should_pause(e,True)


def test_repeated_decision_uses_current_amount_without_duplicate_inbox(game):
    e=Engine(copy.deepcopy(game.world));e.world.systems['settings']['financial_pause_threshold']=100000
    c=Campaign(e);c.decision('shortfall','Bank liquidity','Shortfall',financial_amount=50000)
    assert not should_pause(e,True)
    e.pause_reasons=[]
    c.decision('shortfall','Bank liquidity','Still short',financial_amount=150000)
    assert should_pause(e,True)
    assert len([d for d in e.world.systems['decisions'] if d['source']=='shortfall'])==1


def setup_unpaid_property(game,threshold):
    act(game,'buy',property_id=game.world.properties[0].id)
    act(game,'settings',financial_pause_threshold=threshold,pause_routine=False)
    e=Engine(copy.deepcopy(game.world));cash=e.world.cash('personal')
    e.post('personal','test-spend-cash','Test cash shortfall',{'asset:cash':-cash,'expense:test':cash})
    game.store.commit(e,game.world.revision);game.world=e.world


def test_worker_continues_small_shortfalls_and_preserves_debt(game):
    setup_unpaid_property(game,100000)
    act(game,'advance',target=(date.fromisoformat(game.world.date)+timedelta(days=3)).isoformat())
    game.worker.join(timeout=10)
    assert not game.progress['running'] and game.progress['completed']==3
    assert -game.world.accounts['personal']['liability:payable']>0
    assert any(e['title']=='Funds needed' and e.get('pause_suppressed') for e in game.world.events)
    game.store.audit(game.world)


def test_zero_threshold_retains_financial_stops(game):
    setup_unpaid_property(game,0)
    act(game,'advance',target=(date.fromisoformat(game.world.date)+timedelta(days=3)).isoformat())
    game.worker.join(timeout=10)
    assert game.progress['completed']==1 and not game.progress['running']
    assert 'Funds needed' in game.progress['message']


def test_settings_form_dollars_and_partial_updates_persist(game):
    act(game,'settings',stop_cash=200000,succession=True)
    with client_for(game) as c:
        response=c.post('/api/command',headers={'Origin':'http://testserver','X-Game-Token':'test-token'},json=dict(action='settings',args=dict(financial_pause_threshold_dollars='1000.00',pause_routine=False),revision=game.world.revision,command_id='test-skip-settings'))
        assert response.status_code==200
        page=c.get('/?page=settings');assert 'Time-skip interruptions' in page.text
        page=c.get('/');assert 'Financial pause minimum: $1,000' in page.text
    settings=game.world.systems['settings']
    assert settings['financial_pause_threshold']==100000 and not settings['pause_routine']
    assert settings['stop_cash']==200000 and settings['succession']
    restored=Game(game.store.path);assert restored.world.systems['settings']==settings;restored.close()
