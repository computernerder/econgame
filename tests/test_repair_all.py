import copy,json,re
from datetime import date,timedelta
import pytest
from test_game import game,act,step
from test_property_scale import funded,buy,employee
from test_property_services import property_for
from test_campaign_product import client_for
from economic_simulation.domain import Engine,RuleError,World
from economic_simulation.property_operations import PropertyOperations,SYSTEMS,systems_for


def request(e,p,**kwargs):
    args=dict(property_id=p.id,system='all',kind='repair',provider='outside');args.update(kwargs)
    return e.action('property_work',args,'repair-all-test')


def test_bulk_books_real_jobs_skips_active_and_full_systems_and_reconciles():
    e=funded();p=buy(e);ops=PropertyOperations(e);facts=ops.ensure(p)
    for row in facts.values():row['condition']=60
    facts['exterior']['condition']=100
    e.action('property_work',dict(property_id=p.id,system='roof',kind='repair'),'existing-roof')
    existing=copy.deepcopy(e.world.systems['property_work'][0]);before=copy.deepcopy(facts);cash=e.world.cash(p.owner)
    result=request(e,p);jobs=e.world.systems['property_work'][1:]
    assert len(jobs)==6 and {j['system'] for j in jobs}==set(SYSTEMS)-{'roof','exterior'}
    assert 'Skipped: Roof (work underway), Exterior (100/100)' in result
    assert e.world.systems['property_work'][0]==existing and facts==before
    assert cash-e.world.cash(p.owner)==sum(j['total'] for j in jobs)
    assert len({j['id'] for j in e.world.systems['property_work']})==7
    for day in range(3):
        e.world.date=(date.fromisoformat(e.world.date)+timedelta(days=1)).isoformat();ops.tick()
        assert all(j['remaining']==max(0,720-240*(day+1)) for j in jobs)
    assert all(j['status']=='complete' and j['prepaid']==0 and j['actual_cost']==j['total'] for j in jobs)
    assert all(facts[j['system']]['condition']>before[j['system']]['condition'] for j in jobs if not j['callback'])
    assert any(facts[j['system']]['condition']>before[j['system']]['condition'] for j in jobs)
    assert e.world.accounts[p.owner]['asset:prepaid_works']==0
    e.validate()


def test_insufficient_combined_cash_does_not_partially_book_or_advance_ids():
    e=funded();p=buy(e);ops=PropertyOperations(e)
    cost=ops.quote(p,'structure','repair')['total'];cash=e.world.cash(p.owner)
    e.post(p.owner,'withdraw','Test withdrawal',{'asset:cash':cost-cash,'equity:distributions':cash-cost})
    before=copy.deepcopy(e.world.to_dict());postings=copy.deepcopy(e.postings)
    with pytest.raises(RuleError,match='Repair all needs'):request(e,p)
    assert e.world.to_dict()==before and e.postings==postings


@pytest.mark.parametrize('problem',['missing_license','expired_license','unqualified','owner','wrong_kind','land','building','unowned','full','active'])
def test_rejected_batch_is_atomic(problem):
    e=funded();p=buy(e,problem=='land');kwargs={}
    if problem in ('missing_license','expired_license','unqualified'):
        b,emp,person,rules=employee(e);person.skills['maintenance']=90
        person.licenses.update(electrical='2030-01-01',plumbing='2030-01-01',hvac='2030-01-01')
        if problem=='missing_license':person.licenses.pop('hvac')
        elif problem=='expired_license':person.licenses['hvac']='2020-01-01'
        else:person.skills['maintenance']=30
        kwargs['provider']=b.id
    if problem=='owner':kwargs['provider']='owner'
    if problem=='wrong_kind':kwargs['kind']='replacement'
    if problem=='building':p.status='building'
    if problem=='unowned':p=next(p for p in e.world.properties if p.status=='market')
    if problem=='full':
        for row in PropertyOperations(e).ensure(p).values():row['condition']=100
    if problem=='active':request(e,p)
    before=copy.deepcopy(e.world.to_dict());postings=copy.deepcopy(e.postings)
    with pytest.raises(RuleError):request(e,p,**kwargs)
    assert e.world.to_dict()==before and e.postings==postings


def test_internal_bulk_uses_one_employees_finite_hours_and_real_charges():
    e=funded();p=buy(e);b,emp,person,rules=employee(e)
    person.skills['maintenance']=90;person.licenses.update(electrical='2030-01-01',plumbing='2030-01-01',hvac='2030-01-01')
    e.world.date='2026-01-12';cash=e.world.cash(p.owner);request(e,p,provider=b.id)
    jobs=e.world.systems['property_work'];assert cash-e.world.cash(p.owner)==sum(j['materials'] for j in jobs)
    buckets,_=rules.work(b,date.fromisoformat(e.world.date));capacity=sum(buckets['electrician'])
    PropertyOperations(e).deliver(rules,b,buckets)
    assert 0<sum(j['labor_used'] for j in jobs)<=capacity
    assert sum(j['labor_used'] for j in jobs)<sum(j['effort'] for j in jobs)
    assert all(set(j['staff'])<={emp.id} for j in jobs)
    assert sum(j['actual_cost'] for j in jobs)>0
    assert e.world.accounts[p.owner]['expense:internal_services:'+b.id]==-e.world.accounts[b.id]['income:internal_services:'+p.owner]
    e.validate()


def test_preview_confirmation_duplicate_and_reload(game):
    e=Engine(copy.deepcopy(game.world));p=property_for(e)
    game.store.commit(e,game.world.revision);game.world=e.world
    before=copy.deepcopy(game.world.to_dict())
    args=dict(property_id=p.id,system='all',kind='repair',provider='outside')
    payload=dict(action='property_work',args=args,revision=game.world.revision,command_id='bulk-repair-confirm',campaign_session=game.session_id)
    with client_for(game) as c:
        html=c.get('/?page=property_workbench&property_id='+p.id+'&action_focus=property_work').text
        assert 'data-repair-all' in html and 'All systems needing repair' in html
        data=json.loads(re.search(r'data-work-properties>(.*?)</script>',html,re.S).group(1))
        assert data[p.id]['repair_count']==8 and 'paid now' in data[p.id]['repair_summary']['outside']
        preview=c.post('/api/preview',json=payload)
        assert preview.status_code==200,preview.text
        assert '8 systems' in preview.json()['message'] and 'remaining' in preview.json()['description']
        assert not re.search(r'\$[\d,]+\.\d',preview.text)
        assert game.world.to_dict()==before
        confirmed=c.post('/api/command',json=payload);assert confirmed.status_code==200,confirmed.text
        committed=copy.deepcopy(game.world.to_dict())
        assert c.post('/api/command',json=payload).status_code==200
        assert game.world.to_dict()==committed
    assert game.store.load().to_dict()==game.world.to_dict()
    step(game,1);game.store.audit(game.world)


def test_batch_matches_individual_repairs_and_save_roundtrip_each_day():
    bulk=funded();p=buy(bulk);individual=Engine(copy.deepcopy(bulk.world));request(bulk,p)
    for key in SYSTEMS:individual.action('property_work',dict(property_id=p.id,system=key,kind='repair',provider='outside'),'repair-all-test:'+key)
    assert bulk.world.to_dict()==individual.world.to_dict()
    for _ in range(4):
        bulk.advance_day()
        individual=Engine(World.from_dict(json.loads(json.dumps(individual.world.to_dict()))));individual.advance_day()
        assert json.dumps(bulk.world.to_dict(),sort_keys=True)==json.dumps(individual.world.to_dict(),sort_keys=True)


def test_delegation_checks_full_batch_instead_of_each_repair(game):
    from test_leadership import setup
    from test_authority import contract
    e,leader,b,_,_=setup(game)
    e.action('fund_business',dict(business_id=b.id,amount=10000000),'fund-repairs')
    p=property_for(e,b.id);ops=PropertyOperations(e)
    largest=max(ops.quote(p,key,'repair')['total'] for key in SYSTEMS)
    total=sum(ops.quote(p,key,'repair')['total'] for key in SYSTEMS)
    contract(e,b,transaction_limit=largest,maintenance='allow');b.authority['training_budget']=total
    cash=e.world.cash(b.id)
    assert not leader.perform(b,'bulk-work','property_work',dict(property_id=p.id,system='all',kind='repair'),0,True,'Repair all property systems')
    assert e.world.cash(b.id)==cash and not e.world.systems.get('property_work')
    assert e.world.systems['management_requests'][-1]['status']=='open'
    assert e.world.systems['management_requests'][-1]['cost']==total
