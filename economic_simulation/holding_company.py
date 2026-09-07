"""An empty legacy ledger is not an owned company until the player creates it."""
def exists(world):
    if world.systems.get('holding_company') or world.accounts.get('company'):
        return True
    if any(p.owner=='company' for p in world.properties):return True
    if any(b.owner=='company' or b.reserved_by=='company' for b in world.businesses):return True
    # Preserve old company relationships even when its current balances are zero.
    def referenced(value):
        if isinstance(value,dict):return any(k=='company' or referenced(v) for k,v in value.items())
        if isinstance(value,(list,tuple)):return any(referenced(v) for v in value)
        return value=='company'
    return referenced({k:v for k,v in world.systems.items() if k not in ("period_bases", "tax_carry", "annual")})


def name(world):
    return world.systems.get('holding_company',{}).get('name','Your property company')
