"""One player residence, separate from a property's legal ownership."""
from .domain import RuleError


def is_residence(prop):
    return prop.occupancy_use == 'personal_residence'


def current(world):
    return next((p for p in world.properties if is_residence(p)), None)


def blocker(world, prop):
    if prop.owner != 'personal':
        return 'Your residence must be owned by your personal portfolio.'
    if prop.category != 'residential':
        return 'Choose a residential home.'
    if is_residence(prop):
        return 'This is already your personal residence.'
    if prop.status != 'vacant':
        return 'The home must be vacant. Resolve its tenant search, lease, sale or construction first.'
    if prop.spaces:
        return 'Choose an undivided home. Separately managed units are not supported as a personal residence yet.'
    if prop.occupant or prop.tenant or any(l['property_id']==prop.id and l['status']=='active' for l in world.systems.get('leases', [])):
        return 'Resolve existing occupancy and leases before moving in.'
    listing = world.systems.get('property_listings', {}).get(prop.id, {})
    if listing.get('status') in ('marketing', 'closing'):
        return 'Withdraw the property sale before moving in.'
    if prop.id in world.systems.get('flip_progress', {}) and world.systems['flip_progress'][prop.id]['phase'] != 'sold':
        return 'Resolve the funded flip before using this property as your home.'
    if prop.condition < 40:
        return 'Repair the home to at least 40 condition before moving in.'
    if any(j['property_id']==prop.id and j['status']=='working' for j in world.systems.get('property_work', [])):
        return 'Finish the committed property work before moving in.'
    return ''


def action(engine, action, args):
    world = engine.world
    prop = engine.get_property(args.get('property_id', ''))
    previous = current(world)
    if action == 'set_residence':
        reason = blocker(world, prop)
        if reason:
            raise RuleError(reason)
        # Validate the destination first so an unsuccessful move keeps the old home.
        if previous:
            previous.status='vacant';previous.occupant=None;previous.occupancy_use='rental'
        prop.status='occupied';prop.occupant='personal';prop.occupancy_use='personal_residence'
        prop.rent=0;prop.tenant=None;prop.lease_end=None;prop.due=None
        message = prop.name + ' is now your personal residence. No rent is earned; holding costs and loan payments continue.'
        if previous:
            message += ' ' + previous.name + ' is now vacant and available for another use.'
    else:
        if prop is not previous:
            raise RuleError('Choose your current personal residence.')
        prop.status='vacant';prop.occupant=None;prop.occupancy_use='rental'
        message = 'You moved out of ' + prop.name + '. It is now vacant; choose whether to rent, improve or sell it.'
    world.systems.setdefault('residence_history', []).append(dict(
        date=world.date, action=action, property_id=prop.id,
        previous_property_id=previous.id if previous else None, actor=world.owner_name))
    engine.event('Personal residence updated', message)
    return message


def validate(world):
    homes = [p for p in world.properties if is_residence(p)]
    if len(homes) > 1:
        raise RuleError('The player can have only one personal residence.')
    for prop in homes:
        if prop.owner!='personal' or prop.category!='residential' or prop.status!='occupied' or prop.occupant!='personal':
            raise RuleError('Personal residence ownership or occupancy is inconsistent.')
        if prop.spaces or prop.rent or prop.tenant or prop.lease_end:
            raise RuleError('A personal residence cannot also be tenant housing.')
        if any(l['property_id']==prop.id and l['status']=='active' for l in world.systems.get('leases', [])):
            raise RuleError('Move out of your personal residence before leasing it.')


def view(world):
    home = current(world)
    def summary(prop):
        return dict(id=prop.id, name=prop.name, county=prop.region, upkeep=prop.upkeep,
                    url='/?page=property&scope=personal&property_id='+prop.id)
    return dict(current=summary(home) if home else None,
                choices=[summary(p) for p in world.properties if not blocker(world,p)])
