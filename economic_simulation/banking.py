"""A simplified outside-customer bank with reconciled deposits and loan assets."""
import calendar
import random

from .domain import RuleError, calendar_target


def bank_view(world, b):
    accounts = world.accounts.get(b.id, {})
    deposits = -accounts.get('liability:customer_deposits', 0)
    payroll = sum(e.salary for e in world.employments if e.employer == b.id and e.status in ('active', 'joining'))
    reserve = payroll + deposits * b.bank_reserve_percent // 100
    group_loans=[l for l in world.systems.get('loans',[]) if l.get('lender')==b.id and l['status']=='active']
    capital=max(0,sum(v for k,v in accounts.items() if k.startswith(('asset:','liability:')))-sum(v for k,v in accounts.items() if k.startswith(('asset:investment','asset:goodwill'))))
    exposures=accounts.get('asset:customer_loans',0)+sum(l['principal'] for l in group_loans)
    return dict(group_loans=group_loans, group_principal=sum(l['principal'] for l in group_loans), group_interest=sum(l['interest_due'] for l in group_loans), deposits=deposits, principal=accounts.get('asset:customer_loans', 0),
                interest=accounts.get('asset:loan_interest', 0), reserve=reserve,
                lendable=min(max(0,world.cash(b.id)-reserve),max(0,capital*10-exposures)) if b.id in world.accounts else 0,
                capital=capital,capital_headroom=max(0,capital*10-exposures),
                loans=[loan for loan in b.bank_loans if loan['status'] == 'active'],
                losses=accounts.get('expense:credit_losses', 0))


def validate_bank(b, accounts):
    if accounts.get('asset:customer_loans', 0) != sum(loan['principal'] for loan in b.bank_loans):
        raise RuleError('Bank loan principal does not reconcile.')
    if accounts.get('asset:loan_interest', 0) != sum(loan['interest'] for loan in b.bank_loans):
        raise RuleError('Bank interest does not reconcile.')
    if accounts.get('liability:customer_deposits', 0) > 0:
        raise RuleError('Customer deposits cannot be negative.')


def operate_bank(rules, b, today, minutes, management, open_day):
    e, w = rules.e, rules.w
    management = management * b.capacity_percent // 100
    def post(kind, memo, lines):
        e.post(b.id, f'bank:{kind}:{b.id}:{w.date}', memo, lines)

    deposits = -w.accounts[b.id].get('liability:customer_deposits', 0)
    interest = deposits * b.deposit_rate_bps // (10000 * (366 if calendar.isleap(today.year) else 365))
    if interest:
        post('deposit-interest', 'Interest credited to customer deposits',
             {'expense:deposit_interest': interest, 'liability:customer_deposits': -interest})
    # Existing contracts settle even when the branch is closed or lending is paused.
    for loan in b.bank_loans:
        if loan['status'] != 'active':
            continue
        earned = loan['principal'] * loan['rate_bps'] // (10000 * (366 if calendar.isleap(today.year) else 365))
        if earned:
            post('interest:' + loan['id'], 'Customer loan interest earned',
                 {'asset:loan_interest': earned, 'income:loan_interest': -earned})
            loan['interest'] += earned
        if loan['due'] > w.date:
            continue
        if loan['payments'] == 0 and random.Random(f'credit:{w.seed}:{loan["id"]}').randrange(100) < 3:
            post('loss:' + loan['id'], 'Defaulted customer loan written off',
                 {'asset:customer_loans': -loan['principal'], 'asset:loan_interest': -loan['interest'],
                  'expense:credit_losses': loan['principal'] + loan['interest']})
            loan.update(principal=0, interest=0, status='defaulted')
            continue
        principal = min(loan['principal'], (loan['original'] + 11) // 12)
        post('payment:' + loan['id'], 'Customer loan installment collected',
             {'asset:cash': principal + loan['interest'], 'asset:customer_loans': -principal,
              'asset:loan_interest': -loan['interest']})
        loan['principal'] -= principal
        loan['interest'] = 0
        loan['payments'] += 1
        loan['due'] = calendar_target(today, 'month').isoformat()
        if not loan['principal']:
            loan['status'] = 'repaid'
    # Retain all live contracts and a bounded recent closed history.
    b.bank_loans = [l for l in b.bank_loans if l['status'] == 'active'] + [l for l in b.bank_loans if l['status'] != 'active'][-30:]
    deposits = -w.accounts[b.id].get('liability:customer_deposits', 0)
    withdrawal = deposits // 100 if today.weekday() < 5 else 0
    paid = min(withdrawal, w.cash(b.id))
    if paid:
        post('withdrawals', 'Outside customers withdraw deposits',
             {'asset:cash': -paid, 'liability:customer_deposits': paid})
    shortage = withdrawal - paid
    if shortage and w.systems:
        from .campaign import Campaign
        Campaign(e).decision('bank-liquidity:' + b.id + ':' + w.date[:7], 'Bank needs withdrawal liquidity',
                             b.name + ' has unfulfilled withdrawals. Add capital or pause new lending. Unpaid deposits remain customer liabilities.', b.id, financial_amount=shortage)
    from .economy import Economy
    demand = b.daily_demand * Economy(e).demand_factor(b) // 100 if w.systems else b.daily_demand
    capacity = minutes['teller'] * 12 * management // 6000 if open_day else 0
    services = min(demand, capacity)
    if services:
        deposit = services * 50000
        post('deposits', 'Outside customers place deposits',
             {'asset:cash': deposit, 'liability:customer_deposits': -deposit})
        fees = services * 1000
        post('fees', 'Branch customer service fees', {'asset:cash': fees, 'income:bank_fees': -fees})
    originated = 0
    if open_day and b.auto_lending and services and not shortage:
        capacity = min(2, minutes['loan_officer'] * management // 12000)
        for _ in range(capacity):
            amount = 2000000
            if bank_view(w, b)['lendable'] < amount:
                break
            lid = f'{b.id}-loan-{b.next_loan_id}'
            b.next_loan_id += 1
            post('originate:' + lid, 'Customer loan principal advanced',
                 {'asset:cash': -amount, 'asset:customer_loans': amount})
            b.bank_loans.append(dict(id=lid, original=amount, principal=amount, interest=0,
                                     rate_bps=b.loan_rate_bps, due=calendar_target(today, 'month').isoformat(),
                                     payments=0, status='active'))
            originated += 1
    return dict(output=services, unit='customers served', demand=demand, loans_originated=originated,
                withdrawals_unpaid=shortage,
                bottleneck='Withdrawal liquidity: add capital' if shortage else
                'Closed today' if not open_day else 'Teller coverage' if services < demand else
                'Lending paused' if not b.auto_lending else 'Credit staff, demand and lending cash reserve')
