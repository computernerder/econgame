"""Vermont geography, versioned separately from the historical economic catalogs.

County names are geographic; populations and economic indices are game tuning.
Legacy catalog files remain intact so older save content fingerprints still work.
"""
import copy

VERSION = 24
LEGACY_COUNTIES = {'Willow Creek': 'Rutland County', 'Northbank': 'Chittenden County',
                   'Parkside': 'Washington County'}
# Keep the first three in legacy order: stable lot identities and existing markets.
COUNTIES = ('Rutland County', 'Chittenden County', 'Washington County',
            'Addison County', 'Bennington County', 'Caledonia County', 'Essex County',
            'Franklin County', 'Grand Isle County', 'Lamoille County', 'Orange County',
            'Orleans County', 'Windham County', 'Windsor County')


def county(value):
    return LEGACY_COUNTIES.get(value, value)


def remap_locations(value):
    """Map structured geography, including pending action arguments, not names/memos."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('region', 'home_region') and isinstance(item, str):
                value[key] = county(item)
            elif key == 'regions' and isinstance(item, str):
                value[key] = ','.join(county(part.strip()) for part in item.split(','))
            elif key == 'regions' and isinstance(item, (list, tuple)) and all(isinstance(x, str) for x in item):
                value[key] = [county(x) for x in item]
            else:
                remap_locations(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            remap_locations(item)


def configure_catalogs(content, businesses, rules):
    remap_locations(content)
    remap_locations(businesses)
    originals = copy.deepcopy(rules['regions'])
    for record in rules['regions']:
        record['id'] = county(record['id'])
    for index, name in enumerate(COUNTIES[3:]):
        record = copy.deepcopy(originals[index % len(originals)])
        record.update(id=name, population=25000 + index * 2500)
        rules['regions'].append(record)
    # Real opportunities in every county, not merely extra filter labels.
    templates = [copy.deepcopy(next(p for p in content['properties'] if p.get('category', 'residential') == kind))
                 for kind in ('residential', 'commercial', 'industrial')]
    templates.extend([dict(templates[1], category='office', kind='Office building'),
                      dict(templates[1], category='mixed_use', kind='Shops and apartments')])
    for name in COUNTIES[3:]:
        for template, suffix in zip(templates, ('Maple Lane', 'Business Center', 'Workshop', 'Office Court', 'Market House')):
            content['properties'].append(dict(template, region=name, name=name + ' ' + suffix))


def migrate(engine):
    world = engine.world
    if world.systems.get('geography_version', 0) >= VERSION:
        return
    for prop in world.properties:
        prop.region = county(prop.region)
    for business in world.businesses:
        business.region = county(business.region)
    for person in world.people:
        person.home_region = county(person.home_region)
    remap_locations(world.systems)
    for record in world.systems['regions']:
        record['id'] = county(record['id'])
    from .domain import GAME_RULES, CONTENT, Property
    present = {r['id'] for r in world.systems['regions']}
    added = set()
    for spec in GAME_RULES['regions']:
        if spec['id'] in present:
            continue
        record = copy.deepcopy(spec)
        record.update(history=[], graduates=0,
                      unemployed=record['population'] * (100-record['employment']) // 100,
                      underemployed=record['population'] // 20)
        world.systems['regions'].append(record)
        added.add(record['id'])
    # Fixed identities and no random draws: importing geography does not consume
    # the saved RNG streams or change the value/condition of existing property.
    for index, spec in enumerate(CONTENT['properties']):
        if spec['region'] in added:
            prop = Property(**spec, id='vermont-property-' + str(index), asking=0)
            prop.asking = prop.value * 94 // 100
            world.properties.append(prop)
    from .property_development import Development
    Development(engine).ensure(added)
    world.systems.update(geography_version=VERSION, setting='Vermont')
