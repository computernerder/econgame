"""Tenant repair requests arise from existing occupied-property systems."""
from datetime import date, timedelta
from .campaign import Campaign
from .domain import RuleError


class PropertyRequests(Campaign):
    def action(self, args, source):
        ticket = next((r for r in self.s.get('property_requests', []) if r['id'] == args.get('request_id')
                       and r['status'] in ('open', 'overdue')), None)
        if not ticket:
            raise RuleError('Select an unresolved tenant maintenance request.')
        p = self.e.get_property(args.get('property_id', ''))
        if ticket['property_id'] != p.id:
            raise RuleError('The request belongs to a different property.')
        self.require(p.owner)
        from .property_operations import PropertyOperations
        result = PropertyOperations(self.e).action('property_work', dict(property_id=p.id, system=ticket['system'],
            kind=args.get('kind', 'emergency' if ticket['severity'] == 'urgent' else 'repair'),
            provider=args.get('provider', 'outside'),assigned_staff=args.get('assigned_staff','')), source)
        ticket['work_id'] = self.s['property_work'][-1]['id']
        ticket['status'] = 'working'
        return result + ' Request resolution depends on actual completed work and condition.'

    def tick(self):
        from .property_operations import systems_for
        tickets = self.s.setdefault('property_requests', [])
        for ticket in tickets:
            if ticket['status'] == 'resolved':
                continue
            p = self.e.get_property(ticket['property_id'])
            condition = systems_for(self.w, p)[ticket['system']]['condition']
            ticket['current_condition'] = condition
            job = next((j for j in reversed(self.s.get('property_work', [])) if j['property_id'] == p.id
                        and j['system'] == ticket['system'] and j['created'] >= ticket['created']
                        and j['status'] in ('working', 'complete')), None)
            if condition >= 40:
                ticket.update(status='resolved', resolved=self.w.date, outcome='System condition recovered to '+str(condition)+'.')
                self.e.event('Tenant maintenance request resolved', p.name + ': ' + ticket['system'] + ' is serviceable after actual work.')
                continue
            if job and job['status'] == 'working':
                ticket.update(status='working', work_id=job['id'])
            elif ticket['due'] < self.w.date:
                ticket['status'] = 'overdue'
            else:
                ticket['status'] = 'open'
            if ticket['due'] < self.w.date and not ticket.get('notified') and self.controlled(p.owner):
                ticket['notified'] = True
                self.e.event('Tenant repair deadline missed', p.name + ': ' + ticket['system'] +
                             ' remains below serviceable condition. Unresolved overdue requests lower the tenant’s renewal ceiling by 10%.', True)
        for lease in self.s['leases']:
            if lease['status'] != 'active' or lease['tenant'] != 'external':
                continue
            p = self.e.get_property(lease['property_id'])
            if not self.controlled(p.owner):
                continue
            facts = systems_for(self.w, p)
            system = min(facts, key=lambda k: facts[k]['condition'])
            condition = facts[system]['condition']
            if condition >= 35 or any(t['lease_id'] == lease['id'] and t['status'] != 'resolved' for t in tickets):
                continue
            severity = 'urgent' if condition < 20 else 'routine'
            ticket = dict(id=self.uid('property-request'), property_id=p.id, lease_id=lease['id'], owner=p.owner,
                system=system, observed_condition=condition, current_condition=condition, severity=severity,
                created=self.w.date, due=(date.fromisoformat(self.w.date)+timedelta(days=2 if severity=='urgent' else 7)).isoformat(),
                status='open', work_id='', outcome='Tenant reported an existing system problem.')
            tickets.append(ticket)
            self.e.event('Tenant maintenance request', p.name + ': ' + system + f' condition {condition}/100; response due '+ticket['due']+'.', severity=='urgent',request_id=ticket['id'])

    def renewal_ceiling(self, lease, ceiling):
        if any(t['lease_id'] == lease['id'] and t['status'] != 'resolved' and t['due'] < self.w.date
               for t in self.s.get('property_requests', [])):
            return min(ceiling, lease['rent'] * 90 // 100)
        return ceiling
