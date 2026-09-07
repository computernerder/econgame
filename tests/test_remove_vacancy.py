import copy

import pytest

from test_game import game, act, step
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.business_rules import BusinessRules
from economic_simulation.business_views import company_view, employee_view
from economic_simulation.domain import Engine, RuleError, World
from economic_simulation.organization import employee_tree
from economic_simulation.positions import open_positions
from economic_simulation.staffing import vacancies


def create(game, bid, role='cashier'):
    act(game, 'create_position', business_id=bid, role=role)
    return game.world.positions[-1].id


def test_remove_persists_without_money_or_employee_changes(game):
    bid = acquire(game)
    pid = create(game, bid)
    before = copy.deepcopy(game.world.to_dict())
    args = dict(position_id=pid)
    revision = game.world.revision
    result = game.execute('remove_vacancy', args, revision, 'remove-once-command')
    assert 'No charge' in result
    assert game.execute('remove_vacancy', args, revision, 'remove-once-command') == result
    after = game.world.to_dict()
    for key in ('accounts', 'employments', 'people', 'positions', 'business_rng_state'):
        assert after[key] == before[key]
    assert game.store.load().to_dict() == after
    assert pid not in {p.id for p in open_positions(game.world, bid)}
    assert pid not in {p.id for p in vacancies(game.world, bid, 'cashier')}
    rules = BusinessRules(Engine(game.world))
    assert pid not in {p['id'] for p in company_view(rules, rules.company(bid))['vacancies']}
    assert employee_tree(game.world, bid)['vacancies'] == 0
    game.store.audit(game.world)
    with pytest.raises(RuleError, match='already been removed'):
        act(game, 'remove_vacancy', position_id=pid)


@pytest.mark.parametrize('status', ['active', 'joining', 'seller'])
def test_occupied_positions_cannot_be_removed(game, status):
    bid = acquire(game)
    emp = next(e for e in game.world.employments if e.employer == bid)
    emp.status = status
    before = copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError, match='Only vacant'):
        act(game, 'remove_vacancy', position_id=emp.position_id)
    assert game.world.to_dict() == before


def test_unowned_position_cannot_be_removed(game):
    pid = game.world.positions[0].id
    with pytest.raises(RuleError, match='business you own'):
        act(game, 'remove_vacancy', position_id=pid)
    assert not game.world.systems.get('closed_positions')


def test_former_employee_and_reporting_lines_survive(game):
    bid = acquire(game)
    rules = BusinessRules(Engine(game.world))
    emp = next(e for e in rules.staff(bid) if rules.position(e.position_id).role == 'manager')
    pid = emp.position_id
    children = [p.id for p in game.world.positions if p.reports_to == pid]
    assert children
    act(game, 'end_employment', employment_id=emp.id)
    ended = next(e for e in game.world.employments if e.id == emp.id)
    before = copy.deepcopy(ended)
    act(game, 'remove_vacancy', position_id=pid)
    rules = BusinessRules(Engine(game.world))
    assert next(e for e in game.world.employments if e.id == emp.id) == before
    assert employee_view(rules, before)['role'] == 'manager'
    assert all(rules.position(child).reports_to is None for child in children)
    assert not employee_tree(game.world, bid)['warnings']
    assert game.store.load().to_dict() == game.world.to_dict()
    game.store.audit(game.world)


@pytest.mark.parametrize('action', ['hire', 'hire_for_role', 'promote', 'reporting'])
def test_removed_position_rejects_stale_actions(game, action):
    bid = acquire(game)
    pid = create(game, bid)
    act(game, 'remove_vacancy', position_id=pid)
    emp = next(e for e in game.world.employments if e.employer == bid)
    person = next(p for p in game.world.people if p.candidate)
    before = copy.deepcopy(game.world.to_dict())
    with pytest.raises(RuleError):
        act(game, action, business_id=bid, role='cashier', employment_id=emp.id,
            position_id=pid, reports_to=pid, person_id=person.id, amount=400000, weekly_hours=40)
    assert game.world.to_dict() == before


@pytest.mark.parametrize('mode', ['vacancies', 'grow'])
@pytest.mark.parametrize('status', ['open', 'deferred'])
def test_manager_does_not_refill_removed_vacancy(game, mode, status):
    from economic_simulation.leadership import Leadership

    bid = acquire(game)
    pid = create(game, bid)
    b = next(b for b in game.world.businesses if b.id == bid)
    target = len(open_positions(game.world, bid))
    b.authority.update(enabled=True, staffing_target=target, operating_policy=dict(hiring=mode))
    # Use the same request shape as an actual authority exception.
    leadership = Leadership(Engine(game.world))
    leadership.request(b, 'hire:' + pid, 'hire', dict(position_id=pid), 300000, 'Fill the vacancy')
    game.world.systems['management_requests'][-1].update(status=status, deferred_until='2030-01-01')
    request_id = game.world.systems['management_requests'][-1]['id']
    act(game, 'remove_vacancy', position_id=pid)
    b = next(b for b in game.world.businesses if b.id == bid)
    assert b.authority['staffing_target'] == target - 1
    assert next(r for r in game.world.systems['management_requests'] if r['id'] == request_id)['status'] == 'cancelled'
    count = len(game.world.employments)
    step(game, 8)
    assert len(game.world.employments) == count
    assert len(open_positions(game.world, bid)) == target - 1
    assert not any(r['status'] == 'open' and r.get('args', {}).get('position_id') == pid
                   for r in game.world.systems['management_requests'])
    game.store.audit(game.world)


def test_preview_and_business_form(game):
    bid = acquire(game)
    pid = create(game, bid)
    before = copy.deepcopy(game.world.to_dict())
    with client_for(game) as client:
        html = client.get('/', params=dict(page='business', business_id=bid)).text
        assert 'data-action="remove_vacancy"' in html
        assert 'Vacancy to remove' in html
        payload = dict(action='remove_vacancy', args=dict(position_id=pid),
                       revision=game.world.revision, command_id='remove-vacancy-web')
        response = client.post('/api/preview', json=payload)
        assert response.status_code == 200, response.text
        assert 'No charge' in response.json()['message']
        assert game.world.to_dict() == before
        response = client.post('/api/command', json=payload)
        assert response.status_code == 200, response.text
        html = client.get('/', params=dict(page='business', business_id=bid)).text
        assert 'data-action="remove_vacancy"' not in html
        assert 'No vacant positions' in html


def test_archive_is_optional_for_old_saves_and_does_not_consume_position_limit(game):
    bid = acquire(game)
    data = game.world.to_dict()
    data['systems'].pop('closed_positions', None)
    world = World.from_dict(data)
    engine = Engine(world)
    for i in range(101):
        engine.action('create_position', dict(business_id=bid, role='cashier'), f'vacancy-{i}')
        pid = world.positions[-1].id
        engine.action('remove_vacancy', dict(position_id=pid), f'close-{i}')
    engine.validate()
    assert len(world.systems['closed_positions']) == 101
    assert len(open_positions(world, bid)) < 100
    assert len({p.id for p in world.positions}) == len(world.positions)
