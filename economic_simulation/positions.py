"""Open positions exclude archived vacancies; employment history keeps stable IDs."""


def position_open(world, position):
    return position.id not in world.systems.get('closed_positions', {})


def open_positions(world, business_id):
    return [p for p in world.positions if p.business_id == business_id and position_open(world, p)]


def remove_vacancy(rules, position_id):
    from .domain import RuleError

    world = rules.w
    position = rules.position(position_id)
    business = rules.company(position.business_id)
    if not position_open(world, position):
        raise RuleError('This vacancy has already been removed.')
    occupied = {e.position_id for e in world.employments
                if e.employer == business.id and e.status in ('active', 'joining', 'seller')}
    if position.id in occupied:
        raise RuleError('Only vacant positions can be removed. This position has an employee or an accepted offer.')

    # Keep the position for former employees and historical payroll attribution.
    reports = [p for p in world.positions if p.reports_to == position.id]
    for child in reports:
        child.reports_to = position.reports_to
    cancelled = 0
    for request in world.systems.get('management_requests', []):
        if (request['business_id'] == business.id and request['status'] in ('open', 'deferred')
                and request['action'] in ('hire', 'hire_for_role')
                and request.get('args', {}).get('position_id') == position.id):
            request.update(status='cancelled', resolved=world.date,
                           resolution='The player removed this vacancy.')
            cancelled += 1
    old_target = business.authority.get('staffing_target')
    if old_target is not None:
        business.authority['staffing_target'] = max(min(old_target, len(occupied)), old_target - 1)
    world.systems.setdefault('closed_positions', {})[position.id] = dict(
        date=world.date, business_id=business.id, actor='Player', reports_to=position.reports_to,
        reassigned_positions=[p.id for p in reports], cancelled_requests=cancelled,
        previous_staffing_target=old_target, staffing_target=business.authority.get('staffing_target'))
    detail = (f'{position.role.replace("_", " ").title()} vacancy removed from {business.name}. '
              f'{len(reports)} reporting position(s) moved to its supervisor or company leadership; '
              f'{cancelled} pending hiring request(s) cancelled. Employee history is retained. No charge.')
    if old_target is not None and business.authority['staffing_target'] != old_target:
        detail += f' Manager staffing target reduced from {old_target} to {business.authority["staffing_target"]}.'
    rules.e.event('Vacancy removed', detail)
    return detail
