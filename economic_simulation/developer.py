"""Explicit, audited testing edits; money and stock remain double-entry assets."""
from .campaign import Campaign, integer, flag
from .domain import RuleError

BUSINESS_FIELDS = {
    'daily_demand': ('Base daily demand', 0, 100000),
    'capacity_percent': ('Operating capacity (%)', 0, 150),
    'reputation': ('Reputation', 0, 100),
    'culture': ('Workplace culture', 0, 100),
    'equipment_condition': ('Equipment condition', 0, 100),
    'customer_relationships': ('Customer relationships', 0, 100),
}
PERSON_FIELDS = {'morale': 'Morale', 'engagement': 'Engagement', 'burnout': 'Burnout',
                 'loyalty': 'Loyalty', 'trust': 'Trust'}
ACTIONS = {'developer_toggle', 'developer_cash', 'developer_business',
           'developer_stock', 'developer_property', 'developer_employee'}


class Developer(Campaign):
    def action(self, action, args, source):
        settings = self.s['settings']
        if action == 'developer_toggle':
            enabled = flag(args.get('enabled', False))
            settings['developer_enabled'] = enabled
            self.e.event('Developer tools', 'Testing controls ' + ('enabled.' if enabled else 'disabled.'))
            return 'Developer tools ' + ('enabled. Edits will label this campaign as modified.' if enabled else 'disabled. Existing changes and the modified label remain.')
        if not settings.get('developer_enabled', False):
            raise RuleError('Enable developer tools before making a testing change.')
        if action == 'developer_cash':
            target = self.require(args.get('entity', 'personal'))
            amount = integer(args.get('amount'), 0, 100_000_000_000)
            mode = args.get('mode', 'add')
            before = self.w.cash(target)
            if mode not in ('add', 'remove', 'set'):raise RuleError('Choose add, remove or set cash.')
            after = before + amount if mode == 'add' else before - amount if mode == 'remove' else amount
            if after < 0:raise RuleError('Cash cannot be negative. Remove no more than the available balance.')
            delta = after - before
            if delta:self.e.post(target, source, 'Developer cash adjustment', {'asset:cash': delta, 'equity:developer': -delta})
            field = 'cash (cents)'
        elif action in ('developer_business', 'developer_stock'):
            target = self.require(args.get('business_id', ''))
            b = next((b for b in self.w.businesses if b.id == target), None)
            if b is None:raise RuleError('Choose an owned business.')
            from .industry_operations import IndustryOperations
            operations = IndustryOperations(self.e)
            if action == 'developer_stock':
                from .business_rules import SALES
                if b.industry not in SALES or b.unit_cost <= 0:raise RuleError('Choose a business with purchasable inventory.')
                before = b.inventory_units
                after = integer(args.get('value'), 0, 100000)
                delta = after - before
                if delta:
                    self.e.post(target, source, 'Developer inventory adjustment', {'asset:inventory': delta * b.unit_cost, 'equity:developer': -delta * b.unit_cost})
                    if delta > 0:operations.add_stock(b, delta)
                    else:operations.remove_stock(b, -delta)
                    b.inventory_units = after
                field = 'inventory_units'
            else:
                field = args.get('field', '')
                if field not in BUSINESS_FIELDS:raise RuleError('Choose a supported business field.')
                _, low, high = BUSINESS_FIELDS[field]
                after = integer(args.get('value'), low, high)
                if field in ('equipment_condition', 'customer_relationships'):
                    state = operations.state(b);before = state[field];state[field] = after
                else:before = getattr(b, field);setattr(b, field, after)
        elif action == 'developer_property':
            from .property_operations import PropertyOperations, SYSTEMS
            p = self.e.get_property(args.get('property_id', ''))
            self.require(p.owner)
            target = p.id;field = args.get('field', '')
            if field not in ('all_systems',) + SYSTEMS:raise RuleError('Choose a property system.')
            after = integer(args.get('value'), 0, 100)
            systems = PropertyOperations(self.e).ensure(p)
            keys = SYSTEMS if field == 'all_systems' else (field,)
            before = {key: systems[key]['condition'] for key in keys}
            for key in keys:systems[key]['condition'] = after
            p.condition = sum(s['condition'] for s in systems.values()) // len(SYSTEMS)
            self.s.setdefault('property_condition_baseline', {})[p.id] = p.condition
            after = {key: systems[key]['condition'] for key in keys}
        elif action == 'developer_employee':
            emp = next((x for x in self.w.employments if x.id == args.get('employment_id') and x.status in ('active', 'joining')), None)
            if emp is None:raise RuleError('Choose a current employee.')
            self.require(emp.employer)
            person = next(p for p in self.w.people if p.id == emp.person_id)
            target = person.id;field = args.get('field', '')
            after = integer(args.get('value'), 0, 100)
            if field in PERSON_FIELDS:before = getattr(person, field);setattr(person, field, after)
            elif field.startswith('skill:') and field[6:] in person.skills:
                before = person.skills[field[6:]];person.skills[field[6:]] = after
            else:raise RuleError('Choose an existing skill or employee condition.')
        else:raise RuleError('Unknown developer action.')
        if before == after:raise RuleError('Choose a value different from the current value.')
        settings['modified'] = True
        self.s.setdefault('developer_history', []).append(dict(id=source, date=self.w.date,
            action=action, target=target, field=field, before=before, after=after))
        detail = f'{target} · {field}: {before} → {after}. Campaign marked modified.'
        self.e.event('Developer change', detail)
        return detail
