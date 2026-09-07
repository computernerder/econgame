import copy
from datetime import date, timedelta

from test_game import game, act, step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.business_views import descendants, eliminated
from economic_simulation.financial_trends import trend_view
from economic_simulation.readable_names import text_label, account_label


def chart(view, key):
    return next(c for c in view['charts'] if c['key']==key)


def test_trends_reconcile_with_cash_assets_and_trailing_report(game):
    bid=acquire(game,2)
    act(game,'fund_business',business_id=bid,amount=10000000)
    step(game,35)
    before=copy.deepcopy(game.world.to_dict())
    for entities, group in [([bid],False),(descendants(game.world,'personal'),True)]:
        result=trend_view(game.world,game.store,entities,group)
        assert chart(result,'cash')['current']==sum(game.world.cash(e) for e in entities)
        expected=sum(v for e in entities for k,v in game.world.accounts[e].items()
                     if k.startswith(('asset:', 'liability:')) and not(group and (k.startswith('asset:investment') or eliminated(k,entities))))
        assert chart(result,'wealth')['current']==expected
        since=(date.fromisoformat(game.world.date)-timedelta(days=29)).isoformat()
        report=game.store.report(entities[0],since,entities if group else None)
        assert chart(result,'income')['current']==report['income']
        assert chart(result,'profit')['current']==report['profit']
        assert result==trend_view(game.store.load(),game.store,entities,group)
    assert game.world.to_dict()==before


def test_every_daily_point_matches_actual_cash_not_interpolation(game):
    values={game.world.date:game.world.cash('personal')}
    for i in range(4):
        step(game)
        if i==1:act(game,'buy',property_id=game.world.properties[0].id)
        values[game.world.date]=game.world.cash('personal')
    result=trend_view(game.world,game.store,['personal'])
    assert {p['date']:p['value'] for p in chart(result,'cash')['points']}==values


def test_capital_is_not_income_and_expenses_can_make_negative_profit(game):
    engine=Engine(copy.deepcopy(game.world))
    engine.post('personal','chart-capital','Testing capital',{'asset:cash':100000,'equity:capital':-100000})
    engine.post('personal','chart-expense','Testing expense',{'asset:cash':-30000,'expense:maintenance':30000})
    game.store.commit(engine,game.world.revision);game.world=engine.world
    result=trend_view(game.world,game.store,['personal'])
    assert chart(result,'income')['current']==0
    assert chart(result,'profit')['current']==-30000
    assert chart(result,'profit')['low']==-30000
    assert all(20<=p['y']<=150 for c in result['charts'] for p in c['points'])


def test_internal_revenue_does_not_inflate_group_charts(game):
    bid=acquire(game,2)
    engine=Engine(copy.deepcopy(game.world))
    before=trend_view(game.world,game.store,descendants(game.world,'personal'),True)
    engine.post('personal','chart-internal-pay','Internal service',{'expense:internal_service:'+bid:2000,'asset:cash':-2000})
    engine.post(bid,'chart-internal-receipt','Internal service',{'income:internal_service:personal':-2000,'asset:cash':2000})
    game.store.commit(engine,game.world.revision);game.world=engine.world
    after=trend_view(game.world,game.store,descendants(game.world,'personal'),True)
    assert before==after


def test_borrowing_changes_cash_but_not_net_worth(game):
    before=trend_view(game.world,game.store,['personal'])
    engine=Engine(copy.deepcopy(game.world))
    engine.post('personal','chart-loan','Financing',{'asset:cash':100000,'liability:loan':-100000})
    game.store.commit(engine,game.world.revision);game.world=engine.world
    after=trend_view(game.world,game.store,['personal'])
    assert chart(after,'cash')['current']==chart(before,'cash')['current']+100000
    assert chart(after,'wealth')['current']==chart(before,'wealth')['current']
    assert chart(after,'income')['current']==chart(before,'income')['current']


def test_display_names_do_not_mutate_stored_ids_or_escape_html(game):
    bid=acquire(game,2)
    business=next(b for b in game.world.businesses if b.id==bid)
    business.name='North & South <Design>'
    assert account_label(game.world,'asset:investment:'+bid)=='Asset / Investment / '+business.name
    assert 'property care invoice for North & South' in text_label(game.world,'care-invoice:'+bid+':2026-05-14')
    assert text_label(game.world,'warranty-21')=='Warranty claim #21'
    with client_for(game) as client:
        html=client.get('/?page=finance').text
        assert 'North &amp; South &lt;Design&gt;' in html
        assert 'Asset / Investment / Business-' not in html
        assert 'data-chart-value=' in html and 'View daily values' in html
        assert 'North & South <Design>' not in html
        assert 'Daily closing balances' in html


def test_chart_scope_and_compact_overview(game):
    bid=acquire(game,2)
    with client_for(game) as client:
        for page,extra,count in [('overview','',2),('finance','',4),('portfolio','',0),('business','&business_id='+bid+'&scope='+bid,2)]:
            html=client.get('/?page='+page+extra).text
            assert html.count('class="panel trend-card"')==count
            assert 'aria-label="Cash trend over' in html
        html=client.get('/?page=finance&consolidated=true').text
        assert "Uses today's ownership scope" in html
        assert 'class="panel balance-detail" open' not in html


def test_fresh_campaign_shows_one_point_without_fake_history(game):
    result=trend_view(game.world,game.store,["personal"])
    assert result["count"]==1
    with client_for(game) as client:
        assert "One recorded day so far" in client.get("/?page=finance").text
