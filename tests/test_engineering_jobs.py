import copy
from datetime import date

from test_game import game,act,step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.domain import Engine,World
from economic_simulation.business_rules import BusinessRules
from economic_simulation.engineering import next_offer


def company(game,bid):
    return next(b for b in game.world.businesses if b.id==bid)


def test_auto_jobs_continue_and_invoice_each_completed_fee_once(game):
    bid=acquire(game,2)
    step(game,100)
    b=company(game,bid)
    assert b.auto_projects and b.project_number>=3
    assert len(b.project_history)>=2
    assert len({(h['fee'],h['minutes']) for h in b.project_history})>1
    assert -game.world.accounts[bid]['income:project_work']==sum(h['fee'] for h in b.project_history)+(b.project_earned if b.project_active else 0)
    with game.store.connection() as db:
        invoices=db.execute("SELECT source FROM journal WHERE entity=? AND memo='Completed project invoiced'",(bid,)).fetchall()
    assert len(invoices)==len(b.project_history)
    completions=[e for e in game.world.events if e['title']=='Engineering project completed']
    assert completions and all(not e['important'] for e in completions)
    game.store.audit(game.world)


def test_fee_and_required_hours_change_earned_value_for_same_work(game):
    bid=acquire(game,2)
    def operate(fee_factor=1,hours_factor=1):
        engine=Engine(copy.deepcopy(game.world));engine.world.date='2026-01-05'
        b=next(b for b in engine.world.businesses if b.id==bid)
        b.contract_fee*=fee_factor;b.contract_minutes*=hours_factor
        BusinessRules(engine).operate(b,date(2026,1,5));engine.validate()
        return b
    base=operate();higher_fee=operate(fee_factor=2);more_work=operate(hours_factor=2)
    assert base.project_progress>0
    assert base.project_progress==higher_fee.project_progress==more_work.project_progress
    assert abs(higher_fee.project_earned-base.project_earned*2)<=1
    assert abs(more_work.project_earned*2-base.project_earned)<=1
    assert more_work.project_progress/more_work.contract_minutes<base.project_progress/base.contract_minutes


def test_manual_mode_waits_and_accepts_displayed_quote_without_repricing(game):
    bid=acquire(game,2)
    original=(company(game,bid).contract_fee,company(game,bid).contract_minutes)
    act(game,'engineering_policy',business_id=bid,auto_projects=False)
    assert (company(game,bid).contract_fee,company(game,bid).contract_minutes)==original
    step(game,80)
    b=company(game,bid)
    assert not b.project_active and b.project_number==1
    offer=next_offer(game.world,b)
    with client_for(game) as client:
        page=client.get('/',params={'page':'business','business_id':bid,'scope':bid})
        assert page.status_code==200
        assert 'Recent completed jobs and payments' in page.text
        assert 'Contract value per work hour' in page.text
        before=copy.deepcopy(game.world.to_dict())
        preview=client.post('/api/preview',json=dict(action='new_project',args={'business_id':bid},revision=game.world.revision,command_id='review-engineering-job'))
        assert preview.status_code==200,preview.text
        assert game.world.to_dict()==before
    act(game,'new_project',business_id=bid)
    b=company(game,bid)
    assert (b.contract_fee,b.contract_minutes,b.project_number)==(offer['fee'],offer['minutes'],offer['number'])
    assert b.project_progress==b.project_earned==0 and b.project_active
    game.store.audit(game.world)


def test_quotes_and_policy_survive_save_reload_without_rng_changes(game):
    bid=acquire(game,2)
    before=copy.deepcopy(game.world.to_dict())
    offer=next_offer(game.world,company(game,bid))
    for _ in range(3):
        assert next_offer(game.world,company(game,bid))==offer
        game.view()
    assert game.world.to_dict()==before
    act(game,'engineering_policy',business_id=bid,auto_projects=False)
    loaded=game.store.load()
    b=next(b for b in loaded.businesses if b.id==bid)
    assert not b.auto_projects and next_offer(loaded,b)==offer
    legacy=loaded.to_dict()
    for row in legacy['businesses']:
        for key in ('auto_projects','contract_base_fee','contract_base_minutes','project_history'):
            row.pop(key,None)
    restored=World.from_dict(legacy)
    old=next(b for b in restored.businesses if b.id==bid)
    assert old.auto_projects
    assert (old.contract_fee,old.contract_minutes,old.project_progress)==(b.contract_fee,b.contract_minutes,b.project_progress)
