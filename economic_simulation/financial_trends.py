"""Daily charts reconstructed from persisted journal entries, never forecasts."""
from collections import defaultdict, deque
from datetime import date, timedelta

from .business_views import eliminated


def trend_view(world, store, entities, consolidated=False, days=90):
    end = date.fromisoformat(world.date)
    slots = ','.join('?' for _ in entities)
    with store.connection() as db:
        first = db.execute(f'SELECT MIN(date) FROM journal WHERE entity IN ({slots}) AND date<=?',
                           (*entities, world.date)).fetchone()[0]
        start = max(date.fromisoformat(first or world.date), end - timedelta(days=days-1))
        warmup = start - timedelta(days=29)
        rows = db.execute(f'''SELECT j.date,l.account,SUM(l.amount) amount
            FROM journal j JOIN lines l ON l.journal_id=j.id
            WHERE j.entity IN ({slots}) AND j.date>=? AND j.date<=?
            GROUP BY j.date,l.account''', (*entities, warmup.isoformat(), world.date)).fetchall()
    changes = defaultdict(lambda: dict(cash=0, wealth=0, income=0, profit=0))
    for row in rows:
        key, amount = row['account'], row['amount']
        item = changes[row['date']]
        if key == 'asset:cash':
            item['cash'] += amount
        if consolidated and eliminated(key, entities):
            continue
        if key.startswith(('asset:', 'liability:')) and not (consolidated and key.startswith('asset:investment')):
            item['wealth'] += amount
        if key.startswith('income:'):
            item['income'] -= amount
            item['profit'] -= amount
        elif key.startswith('expense:'):
            item['profit'] -= amount
    cash = sum(world.cash(e) for e in entities)
    wealth = sum(v for e in entities for k,v in world.accounts[e].items()
                 if k.startswith(('asset:', 'liability:')) and not (consolidated and
                     (k.startswith('asset:investment') or eliminated(k, entities))))
    # Work back from the reconciled balance, then forward to each day's close.
    for day, item in changes.items():
        if day >= start.isoformat():
            cash -= item['cash']; wealth -= item['wealth']
    window = deque(maxlen=30)
    points = []
    current = warmup
    while current <= end:
        item = changes[current.isoformat()]
        window.append(item)
        if current >= start:
            cash += item['cash']; wealth += item['wealth']
            points.append(dict(date=current.isoformat(), cash=cash, wealth=wealth,
                               income=sum(x['income'] for x in window),
                               profit=sum(x['profit'] for x in window)))
        current += timedelta(days=1)
    specs = [('cash','Cash on hand','Closing cash; includes borrowing, purchases and capital transfers.'),
             ('wealth','Net worth · book value','Recorded assets less depreciation and liabilities. Market appreciation is not included.'),
             ('income','Income · trailing 30 days','Earned income, including rent and realized gains. Collection can occur later.'),
             ('profit','Profit · trailing 30 days','Earned income less recorded expenses, including accrued tax.')]
    charts = []
    for key, title, note in specs:
        series = [dict(date=p['date'], value=p[key]) for p in points]
        low = min(0, min(p['value'] for p in series))
        high = max(0, max(p['value'] for p in series))
        spread = high-low or 100
        coords = [dict(**p, x=round(60+i*560/max(1,len(series)-1),2),
                       y=round(150-(p['value']-low)*130/spread,2)) for i,p in enumerate(series)]
        charts.append(dict(key=key,title=title,note=note,points=coords,
                           path=' '.join(f"{p['x']},{p['y']}" for p in coords),
                           low=low,high=high,current=series[-1]['value'],
                           change=series[-1]['value']-series[0]['value']))
    return dict(charts=charts, first=points[0]['date'], last=world.date,
                count=len(points), consolidated=consolidated)
