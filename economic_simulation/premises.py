"""Operating premises and rent counterparties, separate from property ownership."""
from .domain import daily_share, RuleError


def arrangement(world, business):
    leases = [l for l in world.systems.get('leases', []) if l['tenant'] == business.id and l['status'] == 'active' and l['end_date'] > world.date]
    buildings = [p for p in world.properties if p.owner == business.id and p.occupant == business.id and p.status == 'occupied']
    from .holding_company import name
    names = {'personal': 'Personal portfolio', 'company': name(world), **{b.id: b.name for b in world.businesses}}
    rows = [dict(property=p.name, owner=business.name, rent=0, kind='Company owned') for p in buildings]
    for lease in leases:
        prop = next(p for p in world.properties if p.id == lease['property_id'])
        rows.append(dict(property=prop.name, owner=names.get(lease['owner'], lease['owner']), owner_id=lease['owner'], rent=lease['rent'], kind='Leased', lease_id=lease['id'], arrears=lease['arrears']))
    external = business.monthly_lease if not buildings and not leases else 0
    if external:
        rows.append(dict(property='External premises in ' + business.region, owner=business.region + ' Commercial Landlord', rent=external, kind='External lease'))
    return dict(rows=rows, monthly_rent=sum(l['rent'] for l in leases) + external, external_rent=external)


def require_available(world, business):
    if any(p.occupant == business.id and p.status == 'occupied' for p in world.properties) or any(l['tenant'] == business.id and l['status'] == 'active' and l['end_date'] > world.date for l in world.systems.get('leases', [])):
        raise RuleError('Release the current owned premises or end the existing premises lease before relocating.')


def external_rent(engine, business, today):
    """Each external landlord has its own balanced ledger outside player wealth."""
    world = engine.world
    rent = daily_share(arrangement(world, business)['external_rent'], today)
    landlord = 'external-landlord-' + business.id
    owed_account = 'liability:rent:' + landlord
    old_due = -world.accounts[business.id].get(owed_account, 0)
    if not rent and not old_due:
        return
    world.accounts.setdefault(landlord, {})
    world.systems.setdefault('external_landlords', {})[landlord] = dict(name=business.region + ' Commercial Landlord', tenant=business.id)
    paid = min(rent + old_due, world.cash(business.id))
    outstanding = rent - paid
    source = 'external-premises:' + business.id + ':' + world.date
    engine.post(business.id, source, 'Premises rent paid to ' + business.region + ' Commercial Landlord', {'expense:premises_rent': rent, 'asset:cash': -paid, owed_account: -outstanding})
    engine.post(landlord, source, 'Premises rent from ' + business.name, {'income:rent': -rent, 'asset:cash': paid, 'asset:rent_receivable:' + business.id: outstanding})
