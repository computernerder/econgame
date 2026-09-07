import copy
import json

from test_game import game,act,step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine
from economic_simulation.financial_detail import detail_view,PAYROLL_ACCOUNTS
from economic_simulation.business_views import descendants


def detail(game,entity,consolidated=False):
    entities=descendants(game.world,entity) if consolidated else [entity]
    balances={}
    for owner in entities:
        for key,value in game.world.accounts[owner].items():
            if key.startswith(('asset:','liability:')) and not (consolidated and key.startswith('asset:investment')):
                balances[key]=balances.get(key,0)+value
    return detail_view(game.world,game.store,entities,balances,game.world.date[:7]+'-01')


def section(view,account):
    return next(s for s in view['sections'] if s['account']==account)


def test_every_detail_reconciles_and_view_is_read_only(game):
    bid=acquire(game,2);act(game,'fund_business',business_id=bid,amount=10000000);act(game,'buy',property_id=game.world.properties[0].id,entity=bid)
    step(game,8)
    before=copy.deepcopy(game.world.to_dict())
    for entity,group in [(bid,False),('personal',True),('personal',False)]:
        view=detail(game,entity,group)
        for s in view['sections']:assert sum(r['amount'] for r in s['rows'])==s['total'],s['account']
        expected=sum(-game.world.accounts[e].get('liability:payroll',0) for e in (descendants(game.world,entity) if group else [entity]))
        assert view['payroll_totals']['owed']==expected
    assert game.world.to_dict()==before
    assert game.store.load().to_dict()==json.loads(json.dumps(before))


def test_cash_and_properties_identify_actual_owner_and_link_to_records(game):
    bid=acquire(game,2);act(game,'fund_business',business_id=bid,amount=10000000);prop=game.world.properties[0];act(game,'buy',property_id=prop.id,entity=bid)
    view=detail(game,'personal',True)
    cash=section(view,'asset:cash')
    assert {r['entity'] for r in cash['rows']}==set(descendants(game.world,'personal'))
    assert sum(r['amount'] for r in cash['rows'])==sum(game.world.cash(e) for e in descendants(game.world,'personal'))
    properties=section(view,'asset:property')['rows']
    row=next(r for r in properties if 'property_id='+prop.id in r['url'])
    current=next(p for p in game.world.properties if p.id==prop.id)
    assert row['entity']==bid and row['amount']==current.basis and row['market_value']==current.value
    assert prop.name in row['name'] and current.region in row['description']


def test_equipment_lists_all_additions_and_disposals_beyond_journal_page(game):
    bid=acquire(game,2);opening=game.world.accounts[bid]['asset:equipment']
    e=Engine(copy.deepcopy(game.world))
    e.post(bid,'equipment-extra','Design workstation expansion',{'asset:equipment':100000,'asset:cash':-100000})
    e.post(bid,'equipment-sale','Equipment disposal',{'asset:equipment':-50000,'asset:cash':50000})
    e.post(bid,'test-depreciation','Equipment depreciation',{'asset:equipment_accumulated':-20000,'expense:depreciation':20000})
    for i in range(110):e.post(bid,'page-filler-'+str(i),'Other journal activity',{'asset:cash':1,'equity:test':-1})
    game.store.commit(e,game.world.revision);game.world=e.world
    view=detail(game,bid);equipment=section(view,'asset:equipment')
    assert equipment['total']==opening+50000
    assert any(r['name']=='Design workstation expansion' and r['amount']==100000 for r in equipment['rows'])
    assert any(r['name']=='Equipment disposal' and r['amount']==-50000 for r in equipment['rows'])
    assert 'not individual machines' in equipment['notes'][0]
    dep=section(view,'asset:equipment_accumulated')['rows'][0]
    assert dep['net']==equipment['total']+dep['amount']
    assert dep['history'][-1]['source']=='test-depreciation'


def test_partial_payday_uses_saved_employee_obligations(game):
    bid=acquire(game);e=Engine(copy.deepcopy(game.world))
    employees=[x for x in e.world.employments if x.employer==bid and x.status=='active']
    old=-e.world.accounts[bid].get('liability:payroll',0)
    if old:e.post(bid,'clear-fixture-payroll','Clear prior test payroll',{'liability:payroll':old,'asset:cash':-old})
    first,second=employees[:2]
    e.post(bid,'payroll:'+first.id+':test','First employee earned pay',{'expense:wages':10000,'expense:benefits':2000,'liability:payroll':-12000})
    e.post(bid,'payroll:'+second.id+':test','Second employee earned pay',{'expense:wages':20000,'expense:benefits':3000,'liability:payroll':-23000})
    e.post(bid,'partial-payday','Partial payroll payment',{'asset:cash':-15000,'liability:payroll':15000})
    game.store.commit(e,game.world.revision);game.world=e.world
    view=detail(game,bid);owed=section(view,'liability:payroll')
    assert len(owed['rows'])==1 and 'employment_id='+second.id in owed['rows'][0]['url']
    assert owed['rows'][0]['amount']==-20000 and view['payroll_totals']['owed']==20000
    row=next(x for x in view['payroll'] if x['employment_id']==second.id)
    assert row['owed']==20000 and row['wages']>=20000 and row['benefits']>=3000


def test_payroll_expenses_match_journal_and_bonus_without_employee_is_not_guessed(game):
    bid=acquire(game);step(game,9)
    e=Engine(copy.deepcopy(game.world))
    e.post(bid,'old-bonus-command','One-time employee bonus',{'asset:cash':-10000,'expense:bonus':10000})
    game.store.commit(e,game.world.revision);game.world=e.world
    view=detail(game,bid)
    with game.store.connection() as db:
        total=db.execute("SELECT SUM(l.amount) FROM lines l JOIN journal j ON j.id=l.journal_id WHERE j.entity=? AND j.date>=? AND l.account IN ("+','.join('?' for _ in PAYROLL_ACCOUNTS)+")",(bid,game.world.date[:7]+'-01',*PAYROLL_ACCOUNTS)).fetchone()[0]
    assert view['payroll_totals']['total']==total
    unknown=next(x for x in view['payroll'] if not x['employment_id'])
    assert unknown['bonus']==10000 and unknown['name']=='Unassigned historical payroll'
    assert all(x['bonus']==0 for x in view['payroll'] if x['employment_id'])


def test_group_does_not_count_employee_twice_and_current_pay_is_separate(game):
    a=acquire(game,0);b=acquire(game,2)
    emp=next(e for e in game.world.employments if e.employer==a and e.status=='active')
    act(game,'director_assign',employment_id=emp.id,business_id=b,limit=10000000)
    view=detail(game,'personal',True)
    rows=[x for x in view['contracts'] if x['employment_id']==emp.id]
    assert len(rows)==1 and rows[0]['entity']==a
    for row in view['contracts']:
        assert row['total']==sum(row[k] for k in ('base','overtime','premium','benefits','tax'))
    assert view['contract_total']==sum(x['total'] for x in view['contracts'] if x['status']=='active')


def test_missing_legacy_obligation_attribution_is_visible_without_new_writes(game):
    bid=acquire(game);e=Engine(copy.deepcopy(game.world))
    e.post(bid,'legacy-payroll','Historical payroll',{'expense:wages':10000,'liability:payroll':-10000})
    e.world.systems.get('obligation_lots',{}).get(bid,{}).pop('liability:payroll',None)
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict());view=detail(game,bid)
    payroll=section(view,'liability:payroll')
    assert payroll['rows'][0]['name']=='Unassigned historical balance'
    assert payroll['total']==game.world.accounts[bid]['liability:payroll']
    assert game.world.to_dict()==before


def test_finance_page_renders_all_breakdowns_and_correct_links(game):
    bid=acquire(game,2);step(game,8)
    before=copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        for scope,group in [(bid,False),('personal',True),('personal',False)]:
            page=client.get('/',params=dict(page='finance',scope=scope,consolidated=group))
            assert page.status_code==200,page.text
            for text in ('Cash by account','Payroll breakdown','Current monthly pay structure','Reconciled balance'):
                assert text in page.text
            assert 'planned for later milestones' not in page.text
        employee=next(e for e in game.world.employments if e.employer==bid)
        assert 'employment_id='+employee.id in client.get('/?page=finance&scope='+bid).text
    assert game.world.to_dict()==before
