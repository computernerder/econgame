"""Testing controls and their persisted before/after record."""
from .campaign_views import field, hidden, choices, form, table, money
from .campaign import Campaign
from .domain import Engine
from .developer import BUSINESS_FIELDS, PERSON_FIELDS


def developer_view(world, scope):
    from .business_views import entity_names
    from .business_rules import SALES
    from .property_operations import systems_for, SYSTEMS
    names = entity_names(world)
    controlled = Campaign(Engine(world)).controlled
    settings = world.systems['settings']
    enabled = settings.get('developer_enabled', False)
    history = world.systems.get('developer_history', [])
    view = dict(page='developer', title='Developer tools',
        intro='Set up test scenarios in this saved campaign. Use the account selector above to focus on a business.',
        metrics=[('Testing controls', 'Enabled' if enabled else 'Disabled'),
                 ('Campaign', 'Modified' if settings.get('modified') else 'Unmodified'),
                 ('Recorded edits', len(history))], forms=[], tables=[], notes=[], links=[])
    view['forms'].append(form('developer_toggle', 'Disable developer tools' if enabled else 'Enable developer tools',
        'Enabling exposes testing controls. The first edit creates a backup and permanently labels this campaign as modified.',
        [hidden('enabled', 'false' if enabled else 'true')], button='Disable tools' if enabled else 'Enable tools'))
    if enabled:
        view['notes'] = ['Testing edits autosave. Cash and inventory adjustments are recorded as testing capital, not operating profit. A backup is created before the first edit.',
            'Existing debts, approvals, contracts and qualifications still apply. These tools do not reopen closed businesses or reverse campaign insolvency. Advance time normally to test daily behavior.']
        view['forms'].append(form('developer_cash', 'Adjust cash',
            'Add testing funds, remove funds to test distress, or set an exact balance. Amounts are dollars.',
            [field('entity', 'Account', scope, 'select', choices({k: f'{v} · {money(world.cash(k))}' for k,v in names.items()})),
             field('mode', 'Operation', 'add', 'select', choices({'add':'Add money','remove':'Remove money','set':'Set exact balance'})),
             field('amount_dollars', 'Amount ($)', 100000, 'number', minimum=0, maximum=1000000000)]))
        businesses = [b for b in world.businesses if controlled(b.id) and (scope == 'personal' or b.id == scope)]
        for b in businesses:
            state = world.systems.get('industry_state', {}).get(b.id, {})
            current = {k: state.get(k, 100 if k == 'equipment_condition' else 50) if k in ('equipment_condition','customer_relationships') else getattr(b, k) for k in BUSINESS_FIELDS}
            view['forms'].append(form('developer_business', 'Business conditions · ' + b.name,
                'Set one parameter. Customer demand still depends on the industry model, competition, staffing and opening days.',
                [hidden('business_id', b.id), field('field', 'Parameter (current value)', 'daily_demand', 'select',
                    choices({k:f'{label} · {current[k]} (range {low}–{high})' for k,(label,low,high) in BUSINESS_FIELDS.items()})),
                 field('value', 'New whole-number value', b.daily_demand, 'number', minimum=0, maximum=100000)]))
            if b.industry in SALES and b.unit_cost > 0:
                view['forms'].append(form('developer_stock', 'Set inventory · ' + b.name,
                    f'Current stock: {b.inventory_units} units. Added stock arrives today; removed stock uses the oldest lots first. Unit cost: {money(b.unit_cost)}.',
                    [hidden('business_id', b.id), field('value', 'Inventory units', b.inventory_units, 'number', minimum=0, maximum=100000)]))
        properties = [p for p in world.properties if controlled(p.owner) and (scope == 'personal' or p.owner == scope)]
        for p in properties:
            systems = systems_for(world,p)
            view['forms'].append(form('developer_property', 'Property condition · ' + p.name,
                'Change actual system condition for repair and disruption tests. Existing work, inspections, property basis and market obligations remain in place.',
                [hidden('property_id',p.id), field('field','System (current condition)','all_systems','select',
                    choices({'all_systems':'All systems', **{k:k.replace('_',' ').title()+f' · {systems[k]["condition"]}/100' for k in SYSTEMS}})),
                 field('value','New condition',p.condition,'number',minimum=0,maximum=100)]))
        employees = [x for x in world.employments if controlled(x.employer) and x.status in ('active','joining') and (scope == 'personal' or x.employer == scope)]
        for emp in employees:
            person = next(p for p in world.people if p.id == emp.person_id)
            options = {k:f'{v} · {getattr(person,k)}/100' for k,v in PERSON_FIELDS.items()}
            options.update({'skill:'+k:f'{k.title()} skill · {v}/100' for k,v in person.skills.items()})
            view['forms'].append(form('developer_employee', 'Employee · ' + person.name + ' · ' + names[emp.employer],
                'Edit the existing person. Reporting lines, salary, qualifications and license expiry remain in place.',
                [hidden('employment_id',emp.id), field('field','Parameter (current value)','morale','select',choices(options)),
                 field('value','New rating',person.morale,'number',minimum=0,maximum=100)]))
    view['tables'].append(table('Developer change history', ['Date','Target','Field','Before','After'],
        [(x['date'],names.get(x['target'],x['target']),x['field'],str(x['before']),str(x['after'])) for x in reversed(history[-100:])],
        'Most recent 100 edits. The complete record remains in the save; each edit also appears in Activity. Cash values in this audit are cents.'))
    return view
