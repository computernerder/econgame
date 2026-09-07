"""Read-only defaults for staffed daily management; saved choices take priority."""


def limits(b):
    # Larger inventory and materials orders are routine in these industries.
    # These remain fixed ceilings, not a fraction of the available bank balance.
    purchases={'boutique':500000,'restaurant':500000,'grocery':1000000,'gas_station':5000000,
               'car_dealership':10000000,'factory':2500000,'construction':2500000,
               'trades':1000000,'logistics':1000000}
    return {**dict(enabled=True,purchasing_limit=purchases.get(b.industry,250000),salary_limit=600000,training_budget=50000,
                overtime_cap=60,auto_raises=True),**b.authority}


def staffed(world,b):
    roles={p.id:p.role for p in world.positions}
    return any(e.employer==b.id and e.status=='active' and roles.get(e.position_id) in ('manager','property_manager')
               for e in world.employments)


def automation(world,b):
    from .director_scope import coverage
    director=coverage(world).get(b.id,(None,None))[0]
    services=sorted(set(world.systems.get('service_effects',{}).get(b.id,{})) |
                    ({'it'} if world.systems.get('deployed_systems',{}).get(b.id) else set()))
    return {**dict(pricing=True,scheduling=True,property_operations=True,prefer_internal_property=True,staff_reductions=True,
                   service_renewals=True,service_roles=services,locations=bool(director),location_limit=2,
                   financing=False,loan_limit=1000000,flipping=False,flip_limit=1,flip_capital=10000000,flip_downside=0),
                **world.systems.get('operating_automation',{}).get(b.id,{})}


def collection_limit(b):
    # Contingency fees come from recovered cash, not the operating account.
    # An explicitly chosen purchase ceiling still overrides the wider default.
    return b.authority.get('routine_management',{}).get('collection_limit',
               b.authority.get('purchasing_limit',2500000))


def action_limit(b,action,args):
    return collection_limit(b) if action=='recover_invoice' and args.get('method')=='agency' else limits(b)['purchasing_limit']


def director_limit(b):
    from .domain import GAME_RULES
    startup=GAME_RULES['startup'].get(b.industry,{})
    opening=sum(startup.get(key,0) for key in ('deposit','fitout','inventory','expense','reserve'))
    return max(10000000,limits(b)['purchasing_limit']*4,opening)


def owned_counties(world,business_ids):
    """Default geography follows the operations and assets actually owned.

    Saved authority contracts remain explicit; this only describes the implicit
    grant. Owning a building never adds its tenants to organizational scope.
    """
    scope=set(business_ids)
    return sorted({b.region for b in world.businesses if b.id in scope} |
                  {p.region for p in world.properties if p.owner in scope and p.status not in ('sold','expired')})


def director_contract(world,record,business):
    from .authority import GROUPS
    from .director_scope import assigned
    from .positions import open_positions
    businesses=[b for b in world.businesses if b.id in assigned(world,record)]
    actions={group:'allow' for group in GROUPS}
    for group in ('financing','property_acquisition','asset_sales'):actions[group]='approval'
    return dict(businesses=[b.id for b in businesses],regions=owned_counties(world,[b.id for b in businesses]),
        actions=actions,parent=None,transaction_limit=record['limit'],period_limit=record['limit']*4,
        salary_limit=max((limits(b)['salary_limit'] for b in businesses),default=600000),
        headcount_limit=sum(b.authority.get('staffing_target',len(open_positions(world,b.id))) for b in businesses),
        horizon=7,cash_reserve=business.authority.get('operating_policy',{}).get('cash_reserve',0),
        project_limit=max(10000000,record['limit']),objective='growth')


def contract(world,b):
    """A small-company grant, evaluated through the same checks as saved contracts."""
    from .authority import GROUPS
    from .positions import open_positions
    from .management import policy
    settings=limits(b);operating=policy(b,world)
    actions={group:'allow' for group in GROUPS}
    for group in ('growth','expansion','financing','property_acquisition','asset_sales'):actions[group]='approval'
    if b.authority.get('operating_policy',{}).get('growth')=='auto':actions['growth']='allow'
    # Full annual payroll commitments count alongside ordinary purchases.
    return dict(businesses=[b.id],regions=owned_counties(world,[b.id]),actions=actions,parent=None,
                transaction_limit=max(settings['purchasing_limit'],settings['salary_limit']*12+30000),
                period_limit=settings['purchasing_limit']*20+settings['salary_limit']*12+30000,
                salary_limit=settings['salary_limit'],headcount_limit=b.authority.get('staffing_target',len(open_positions(world,b.id))),
                horizon=7,cash_reserve=operating['cash_reserve'],project_limit=10000000,objective='balanced')
