"""A read-only digest of actual authority records and approval requests."""
from urllib.parse import urlencode


def actor_snapshot(world, employee, record=None):
    person = next((p for p in world.people if employee and p.id == employee.person_id), None)
    return dict(actor=employee.id if employee else None,
                actor_name=person.name if person else 'No leader recorded',
                actor_role=(record.get('role', 'director').replace('_', ' ').title() if record
                            else 'Manager' if employee else 'Unassigned'))


def notification(world):
    from .business_views import entity_names
    owned = entity_names(world)
    audit = world.systems.get('authority_audit', [])
    from .routine_management import ready_property_care
    manager_queue=ready_property_care(world)
    seen = world.systems.get('leadership_activity_seen', 0)
    new = sum(r['business_id'] in owned for r in audit[seen:])
    pending = sum(r['business_id'] in owned and r['status'] == 'open' and r['id'] not in manager_queue
                  for r in world.systems.get('management_requests', []))
    return dict(new=new, pending=pending, cursor=len(audit),
                label=f'Leadership activity · {new} unread action{"s" if new != 1 else ""} · {pending} awaiting approval')


def mark_reviewed(world, cursor):
    from .campaign import integer
    # A stale screen must never mark actions that arrived after it was rendered.
    cursor = integer(cursor, 0, len(world.systems.get('authority_audit', [])))
    world.systems['leadership_activity_seen'] = max(world.systems.get('leadership_activity_seen', 0), cursor)
    return 'Leadership actions through this review have been marked as read. Pending approvals remain open.'


def activity_view(world, business_id='', leader_id='', status='all', page=1, limit=25):
    from .business_views import entity_names
    from .routine_management import ready_property_care
    manager_queue=ready_property_care(world)
    names = entity_names(world)
    people = {p.id:p.name for p in world.people}
    employees = {e.id:e for e in world.employments}
    seen = world.systems.get('leadership_activity_seen', 0)
    rows = []

    def identity(record):
        emp = employees.get(record.get('actor'))
        return dict(actor=record.get('actor') or '',
                    actor_name=record.get('actor_name') or (people.get(emp.person_id, emp.id) if emp else 'No leader recorded'),
                    actor_role=record.get('actor_role', 'Delegated leader' if emp else 'Unassigned'),
                    employee_link=bool(emp and emp.status in ('active', 'joining') and emp.employer in names))

    for index, record in enumerate(world.systems.get('authority_audit', [])):
        if record['business_id'] not in names or (business_id and record['business_id'] != business_id):
            continue
        rows.append(dict(**identity(record), id=f'action-{index+1}', date=record['date'],
                         business_id=record['business_id'], business_name=names[record['business_id']],
                         action=record['action'].replace('_', ' ').title(), detail=record['detail'],
                         outcome=record.get('outcome', ''), cash=record['cash_cost'], commitment=record['commitment'],
                         status='completed', status_label='Completed', new=index >= seen, order=index))
    for index, record in enumerate(world.systems.get('management_requests', [])):
        if record['business_id'] not in names or (business_id and record['business_id'] != business_id):
            continue
        labels = dict(open='Awaiting approval', deferred='Deferred', cancelled='Cancelled', resolved='Resolved',manager_queue='With manager')
        state = 'manager_queue' if record['id'] in manager_queue else record['status']
        rows.append(dict(**identity(record), id=record['id'], date=record.get('resolved') or record['created'],
                         business_id=record['business_id'], business_name=names[record['business_id']],
                         action=record['action'].replace('_', ' ').title(), detail=('Routine property care fits current policy; the manager will recheck and book it when time advances.' if state=='manager_queue' else record['detail']),
                         outcome=record.get('outcome') or record.get('resolution', ''),
                         cash=record.get('cash_cost'), commitment=record['cost'],
                         status=state, status_label=labels.get(state, state.title()), new=False, order=index,
                         due=record.get('due'), recommendation=record.get('recommendation', ''),
                         risk=record.get('risk', ''), resolved_by=record.get('resolved_by', ''),
                         deferred_until=record.get('deferred_until')))
    leaders = sorted({r['actor']:r['actor_name'] for r in rows if r['actor']}.items(), key=lambda item:item[1].casefold())
    statuses = dict(all='All activity', completed='Completed actions', open='Awaiting approval',
                    deferred='Deferred', resolved='Resolved requests', cancelled='Cancelled requests',manager_queue='With manager')
    if status not in statuses:
        status = 'all'
    selected = [r for r in rows if (not business_id or r['business_id'] == business_id)
                and (not leader_id or r['actor'] == leader_id) and (status == 'all' or r['status'] == status)]
    selected.sort(key=lambda r:(r['date'], r['order'], r['id']), reverse=True)
    total = len(selected)
    pages = max(1, (total+limit-1)//limit)
    page = max(1, min(page, pages))
    def url(number):
        return '/?' + urlencode(dict(page='management', activity_business=business_id, leader_id=leader_id,
                                    activity_status=status, activity_page=number)) + '#leadership-activity'
    return dict(rows=selected[(page-1)*limit:page*limit], total=total, page=page, pages=pages,
                previous=url(page-1) if page>1 else '', next=url(page+1) if page<pages else '',
                business_id=business_id, leader_id=leader_id, status=status, statuses=statuses, leaders=leaders,
                businesses=sorted(((k,v) for k,v in names.items() if k not in ('personal','company')), key=lambda x:x[1]),
                notification=notification(world))
