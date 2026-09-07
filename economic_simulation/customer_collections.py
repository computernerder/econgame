"""Dated customer recovery, with finite attempts and reconciled cash receipts."""
from datetime import date, timedelta
from .campaign import Campaign
from .domain import RuleError
from .simulation_support import stable_roll

METHODS = {'reminder': ('Send a free reminder', 3),
           'plan': ('Propose three installments', 3),
           'agency': ('Use a collection agency', 14)}
ACTIVE = ('queued', 'installments')
RISK_INDUSTRIES = ('construction', 'trades', 'factory', 'cleaning', 'landscaping', 'security')


def overdue(world, invoice):
    return bool(invoice.get('defaulted') or invoice.get('overdue_since') or invoice['due'] < world.date)


def active_legal(world, business, invoice):
    return next((t for t in world.systems.get('service_tasks', [])
                 if t['recipient'] == business and t['target_id'] == invoice['id']
                 and t['department'] == 'legal' and t['matter'] in ('collection', 'dispute')
                 and t['status'] in ('queued', 'working')), None)


def busy(world, business, invoice):
    return invoice.get('recovery', {}).get('status') in ACTIVE or bool(active_legal(world, business, invoice))


def status(world, business, invoice):
    recovery = invoice.get('recovery', {})
    if recovery.get('status') in ACTIVE:
        return ('Installment due ' if recovery['status'] == 'installments' else METHODS[recovery['method']][0] + ' · response ') + recovery['next_date']
    task = active_legal(world, business, invoice)
    if task:
        return 'Legal collection in progress · ' + task['id']
    if invoice.get('defaulted'):
        return 'Defaulted · recovery needed'
    if invoice.get('overdue_since'):
        return 'Late · customer promised payment ' + invoice['due']
    return 'Overdue · recovery needed' if overdue(world, invoice) else 'Awaiting payment'


class CustomerCollections(Campaign):
    def record(self, b, invoice, method, outcome, gross=0, fee=0, loss=0):
        self.s.setdefault('collection_history', []).append(dict(
            date=self.w.date, entity=b.id, invoice_id=invoice['id'], method=method,
            outcome=outcome, gross=gross, fee=fee, cash=gross-fee, loss=loss,
            remaining=invoice['amount']))

    def receive(self, b, invoice, amount, source, method, fee=0):
        amount = min(amount, invoice['amount'])
        fee = min(fee, amount)
        if amount:
            lines = {'asset:cash': amount-fee, 'asset:receivable': -amount}
            if fee: lines['expense:collection_fees'] = fee
            memo = 'Customer invoice collected' if method == 'scheduled payment' else 'Customer invoice recovery: ' + method
            self.e.post(b.id, source, memo, lines)
            invoice['amount'] -= amount
            if method != 'scheduled payment' or overdue(self.w, invoice):
                self.record(b, invoice, method, 'Payment received', amount, fee)
        if not invoice['amount'] and invoice in b.receivables:
            b.receivables.remove(invoice)

    def action(self, args, source):
        entity = self.require(args.get('entity', ''))
        b = next((b for b in self.w.businesses if b.id == entity), None)
        invoice = next((r for r in b.receivables if r['id'] == args.get('invoice_id')), None) if b else None
        if not invoice or not overdue(self.w, invoice):
            raise RuleError('Choose an overdue customer invoice in this business.')
        method = args.get('method', '')
        if method not in METHODS:
            raise RuleError('Choose a reminder, installment proposal or collection agency.')
        if busy(self.w, b.id, invoice):
            raise RuleError('This invoice already has recovery in progress. Its next date and status are shown in Customer collections.')
        if method in invoice.get('recovery_attempts', []):
            raise RuleError('This recovery option has already been attempted for this invoice. Choose another option; repeat requests do not reroll the customer.')
        invoice.setdefault('recovery_attempts', []).append(method)
        invoice['recovery'] = dict(method=method, status='queued', created=self.w.date,
                                   next_date=(date.fromisoformat(self.w.date)+timedelta(days=METHODS[method][1])).isoformat(),
                                   source=source, installment=0)
        self.record(b, invoice, method, 'Queued; no cash received or fee charged')
        return METHODS[method][0] + ' queued for ' + invoice['recovery']['next_date'] + '. No money received yet. Agency fees are 25% of actual collections; reminders and installment proposals have no cash fee.'

    def fail(self, b, invoice, recovery, message):
        recovery['status'] = 'failed'
        self.record(b, invoice, recovery['method'], message)
        self.e.event('Customer recovery needs review', b.name + ' · ' + invoice['id'] + ': ' + message,
                     True, financial_amount=invoice['amount'], invoice_id=invoice['id'])

    def recovery_day(self, b, invoice):
        r = invoice['recovery']
        if r['next_date'] > self.w.date:
            return
        method = r['method']
        roll = lambda stage: stable_roll(self.w, 'invoice-recovery:' + invoice['id'] + ':' + stage)
        if r['status'] == 'queued':
            chance = {'reminder': 25 if invoice.get('defaulted') else 85,
                      'plan': 60 if invoice.get('defaulted') else 90,
                      'agency': 65 if invoice.get('defaulted') else 95}[method]
            if roll(method) >= chance:
                self.fail(b, invoice, r, 'Customer did not agree or pay. The balance remains due; another recovery option is available.')
                return
            if method == 'plan':
                r.update(status='installments', installment_amount=(invoice['amount']+2)//3,
                         next_date=(date.fromisoformat(self.w.date)+timedelta(days=10)).isoformat())
                self.record(b, invoice, method, 'Three installments agreed, ten days apart; payments are not guaranteed')
                self.e.event('Customer payment plan agreed', b.name + ' · ' + invoice['id'] + ': first installment ' + r['next_date'] + '.')
                return
            amount = invoice['amount']
            self.receive(b, invoice, amount, r['source'] + ':receipt', method, amount//4 if method == 'agency' else 0)
            r['status'] = 'complete'
        else:
            number = r['installment'] + 1
            # Defaulted customers can break a plan. Earlier installments remain collected.
            if invoice.get('defaulted') and roll('installment:' + str(number)) < 15:
                self.fail(b, invoice, r, 'Customer missed an agreed installment. Prior payments are retained; recover or write off the remaining balance.')
                return
            self.receive(b, invoice, min(invoice['amount'], r['installment_amount']),
                         r['source'] + ':installment:' + str(number), method)
            r.update(installment=number, status='complete' if not invoice['amount'] else 'installments',
                     next_date=(date.fromisoformat(self.w.date)+timedelta(days=10)).isoformat())
        self.e.event('Customer payment received', b.name + ' · ' + invoice['id'] + ': ' +
                     ('invoice settled.' if not invoice['amount'] else 'installment collected; next payment ' + r['next_date'] + '.'))

    def collect(self, b):
        for invoice in list(b.receivables):
            if invoice.get('recovery', {}).get('status') in ACTIVE:
                self.recovery_day(b, invoice)
                continue
            if active_legal(self.w, b.id, invoice):
                continue
            if invoice['due'] > self.w.date:
                continue
            from .industry_operations import IndustryOperations
            if not IndustryOperations(self.e).collection(b, invoice):
                continue
            self.receive(b, invoice, invoice['amount'], 'collect:' + invoice['id'], 'scheduled payment')
