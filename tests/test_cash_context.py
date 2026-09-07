import copy
from html import unescape
from test_game import game,act,step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.application import Game
from economic_simulation.persistence import Store
from economic_simulation.navigation import navigation_view


def test_starting_capital_is_opening_balance_and_later_funding_is_movement(game):
    report=game.store.report('personal','2026-01-01')
    assert report['cash_opening']==report['cash_closing']==35000000
    assert report['cash_flow']==0
    act(game,'buy',property_id='p1')
    report=game.store.report('personal','2026-01-01')
    assert report['cash_flow']==game.world.cash('personal')-35000000
    assert report['cash_opening']+report['cash_flow']==report['cash_closing']
    before=game.world.cash('personal')
    e=Engine(copy.deepcopy(game.world));e.world.date='2026-02-01'
    e.post('personal','later-capital','Capital contributed after start',{'asset:cash':123400,'equity:capital':-123400})
    game.store.commit(e,game.world.revision);game.world=e.world
    report=game.store.report('personal','2026-02-01')
    assert report['cash_opening']==before and report['cash_flow']==123400
    assert report['cash_closing']==game.world.cash('personal')
    restored=Game(game.store.path)
    try:assert restored.store.report('personal','2026-02-01')==report
    finally:restored.close()


def test_skip_cash_uses_selected_account_and_remains_frozen_after_transactions(game):
    bid=acquire(game);start={e:game.world.cash(e) for e in game.world.accounts}
    act(game,'advance',period='day');game.worker.join(20)
    assert not game.worker.is_alive()
    end={e:game.world.cash(e) for e in game.world.accounts}
    with client_for(game) as client:
        for entity in ('personal',bid):
            data=client.get('/api/progress',params={'scope':entity}).json()
            assert data['cash_change']==end[entity]-start[entity]
            assert data['cash_before']==start[entity] and data['cash_after']==end[entity]
            assert data['change_scope']==data['cash_scope']==entity
            assert data['message']==game.view(entity)['progress']['message']
            assert 'Group cash change across owned accounts' in data['message']
    old=game.progress_view(bid)
    act(game,'fund_business',business_id=bid,amount=100000)
    assert game.progress_view(bid)==old
    assert game.world.cash(bid)==old['cash_after']+100000


def test_stopped_skip_reports_zero_change(game):
    game.progress=dict(running=True,completed=0,total=9,message='Starting')
    game.cancel.set();game._run(9)
    data=game.progress_view('personal')
    assert data['cash_change']==0 and data['cash_before']==data['cash_after']
    assert data['completed']==0 and 'Paused' in data['message']


def test_company_tabs_keep_sidebar_and_shared_workspaces_are_explicit(game):
    bid=acquire(game)
    for page in ('business','people','portfolio','finance'):
        nav=navigation_view(game.world,page,bid,bid)
        assert nav['primary']=='businesses'
        assert [t['label'] for t in nav['tabs']]==['Operations','Team','Properties','Finances']
    with client_for(game) as client:
        for page in ('organization','home_office'):
            html=client.get('/',params=dict(page=page,scope=bid)).text
            assert 'shared workspace. Selected account:' in html
            assert 'aria-label="Business sections"' not in html
            assert navigation_view(game.world,page,bid)['primary']==page
        operations=client.get('/',params=dict(page='business',scope=bid,business_id=bid)).text
        team=client.get('/',params=dict(page='people',scope=bid)).text
        properties=client.get('/',params=dict(page='portfolio',scope=bid)).text
        finance=client.get('/',params=dict(page='finance',scope=bid)).text
        assert 'id="hire-employee"' not in operations and 'id="hire-employee"' in team
        assert 'aria-label="Financial trends"' not in properties
        assert 'aria-label="Financial trends"' in finance
        assert 'Organization · ownership chart' in operations and 'Home Office · shared services' in operations


def test_benefits_hide_irrelevant_share_and_show_real_coverage(game):
    bid=acquire(game);emp=next(e for e in game.world.employments if e.employer==bid and e.status=='active')
    with client_for(game) as client:
        html=client.get('/',params=dict(page='employee',employment_id=emp.id)).text
        assert 'NONE medical' not in html and '80% employer share' not in html
        assert 'Medical coverage</dt><dd>Not provided' in html
        act(game,'employee_benefits',employment_id=emp.id,medical='ppo',employer_share=75,retirement_percent=4)
        html=client.get('/',params=dict(page='employee',employment_id=emp.id)).text
        assert 'PPO · employer pays 75% of the premium' in html
        assert '4% employer contribution' in html


def test_sandbox_opening_and_group_internal_transfers_reconcile(tmp_path):
    from economic_simulation.campaign_options import prepare_campaign
    from economic_simulation.business_views import entity_names
    engine=prepare_campaign(dict(mode='sandbox',capital=80000000,starting_date='2028-06-13'))
    store=Store(tmp_path/'sandbox.sqlite3',initial=engine)
    report=store.report('personal','2028-06-01')
    assert report['cash_opening']==80000000 and report['cash_flow']==0
    g=Game(store.path)
    try:
        bid=acquire(g);entities=list(entity_names(g.world))
        before=g.store.report('personal','2028-06-01',entities)
        act(g,'fund_business',business_id=bid,amount=120000)
        after=g.store.report('personal','2028-06-01',entities)
        assert before['cash_flow']==after['cash_flow']
        assert after['cash_opening']+after['cash_flow']==sum(g.world.cash(e) for e in entities)
        account=g.store.report(bid,'2028-06-01')
        assert account['cash_opening']+account['cash_flow']==g.world.cash(bid)
    finally:g.close()
