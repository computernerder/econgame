"""Invoice-specific recovery choices, derived without changing the campaign."""
from .customer_collections import METHODS, overdue, busy, status, active_legal
from .campaign_views import form, field, hidden, choices, table, money
from .business_views import entity_names


def populate(view, world, businesses, scope):
    selected = [b for b in businesses if b.id == scope] if any(b.id == scope for b in businesses) else businesses
    names = entity_names(world)
    view['collection_policy_links']=[dict(label=b.name+' · manager follow-up policy',url='/?page=management#routine-policy-'+b.id) for b in selected]
    cards = []
    waiting = []
    for b in selected:
        for invoice in b.receivables:
            if not overdue(world, invoice):
                waiting.append((b.name, invoice['id'], money(invoice['amount']), invoice['due']))
                continue
            pending = busy(world, b.id, invoice)
            card = dict(id=invoice['id'], business=b.name, amount=invoice['amount'],
                        due=invoice['due'], status=status(world, b.id, invoice),
                        pending=pending, forms=[], entity=b.id, history=[], legal_url='', approval_url='')
            from .routine_management import assigned_collection
            question=next((r for r in world.systems.get('management_requests',[]) if r['business_id']==b.id and r['status']=='open'
                           and r['args'].get('invoice_id',r['args'].get('target_id'))==invoice['id']),None)
            if not pending and question:
                card['status']='Waiting for your decision in Decision inbox'
                card['approval_url']='/?page=inbox&scope=personal#management:'+question['id']
            elif not pending and assigned_collection(world,b,invoice):
                card['status']='Assigned to the manager · next available daily review; exceptions go to Decision inbox'
            base = [hidden('entity', b.id), hidden('invoice_id', invoice['id'])]
            remaining = {key: value[0] for key, value in METHODS.items() if key not in invoice.get('recovery_attempts', [])}
            if not pending:
                if remaining:
                    card['forms'].append(form('recover_invoice', 'Choose a recovery option',
                        'Reminder: free, response in 3 days. Installments: free, response in 3 days, then three payments 10 days apart. Agency: response in 14 days, 25% fee only on cash collected (' + money(invoice['amount']-invoice['amount']//4) + ' net if fully recovered). Customers can refuse or miss installments. Each option can be attempted once per invoice.',
                        base + [field('method', 'Recovery option', next(iter(remaining)), 'select', choices(remaining))], button='Review recovery →'))
                completed_legal = any(t['recipient'] == b.id and t['target_id'] == invoice['id'] and t['department'] == 'legal'
                                      and t['matter'] in ('collection', 'dispute') and t['status'] == 'complete'
                                      for t in world.systems.get('service_tasks', []))
                if not completed_legal:
                    providers = {'outside': 'Outside counsel · $1,800 prepaid'}
                    providers.update({d['provider']: names[d['provider']] + ' · qualified legal department'
                                      for d in world.systems.get('departments', {}).values()
                                      if d['role'] == 'legal' and d['provider'] in names})
                    card['forms'].append(form('service_request', 'Request legal collection',
                        '20 qualified hours. Outside counsel reserves $1,800 now, even if collection fails. An internal legal team uses its real staff capacity and allocates payroll costs. Legal can recover part of the balance; the rest remains owed. One completed legal attempt per invoice.',
                        [hidden('recipient', b.id), hidden('department', 'legal'), hidden('matter', 'collection'), hidden('target_id', invoice['id']),
                         field('provider', 'Legal provider', 'outside', 'select', choices(providers))], button='Review legal work →'))
                card['forms'].append(form('write_off_invoice', 'Write off the remaining balance',
                    'Last resort: records ' + money(invoice['amount']) + ' as bad-debt expense. No cash is received. This ends collection of this invoice.', base, button='Review write-off →'))
            task = active_legal(world, b.id, invoice)
            if task:
                card['legal_url'] = '/?page=home_office&scope=' + b.id
            card['history'] = [h for h in reversed(world.systems.get('collection_history', [])) if h['entity'] == b.id and h['invoice_id'] == invoice['id']]
            cards.append(card)
    view['collection_cards'] = sorted(cards, key=lambda r: (r['pending'], r['due'], r['entity'], r['id']))
    view['collection_waiting'] = table('Invoices awaiting their due date', ['Business', 'Invoice', 'Balance', 'Due'], waiting)
    selected_ids = {b.id for b in selected}
    history = [h for h in reversed(world.systems.get('collection_history', [])) if h['entity'] in selected_ids][:100]
    view['collection_history'] = table('Customer recovery history', ['Date', 'Business / invoice', 'Action / outcome', 'Gross collected', 'Fee', 'Net cash', 'Written off', 'Balance after action'],
        [(h['date'], names.get(h['entity'], h['entity']) + ' / ' + h['invoice_id'], h['method'] + ' · ' + h['outcome'],
          money(h['gross']), money(h['fee']), money(h['cash']), money(h['loss']), money(h['remaining'])) for h in history],
        'Latest 100 actions and receipts in the selected business, or all businesses when viewing a portfolio. Collections reduce receivables; they do not earn the same revenue again. Older ledger entries remain in Finances.')
