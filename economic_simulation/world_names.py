"""Seeded fictional display names. No economic RNG draws or saved-name rewrites."""
import hashlib
from collections import Counter

PLACES=tuple("Alder|Amber Brook|Applewood|Aspen|Autumn Hill|Balsam|Barton Hill|Bear Hollow|Beechwood|Bellwether|Birch Hollow|Blackberry|Blue Heron|Boulder Brook|Bracken|Briarwood|Brookstone|Buttonwood|Cairn|Carriage Hill|Cattail|Clover Hill|Copperleaf|Cricket|Deerfield|Deepwater|Driftwood|Eagle Hollow|East Ridge|Elm Grove|Evergreen|Fairhaven|Fern Hollow|Fieldstone|Firefly|Fox Hollow|Foxglove|Goldenrod|Granite Ridge|Greenstone|Grey Birch|Hawthorn|Hazelwood|Hemlock|Heron Point|High Meadow|Hillside|Honeycomb|Huckleberry|Ironwood|Juniper Ridge|Kestrel|Kingfisher|Larchwood|Laurel Hill|Ledgewood|Linden|Little Otter|Long Meadow|Loon Lake|Maplecrest|Meadowlark|Millstone|Mossy Brook|Mountain Ash|Nightingale|Old Mill|Orchard Hill|Otter Creek|Peregrine|Pine Hollow|Pinecone|Poplar Grove|Quail Run|Quarry Hill|Red Clover|Red Lantern|Ridgecrest|Riverbend|Rock Maple|Round Meadow|Saffron|Sawmill|Silver Birch|Slatebrook|Snowberry|Sparrow|Spruce Hill|Stillwater|Stonebridge|Sugarbush|Summit Grove|Sunflower|Tamarack|Thistle|Timberline|Trillium|Twin Pines|Valley Oak|Walnut Grove|Waterstone|West Ridge|Wheatfield|Whispering Brook|White Pine|Wildflower|Windward|Winterberry|Woodfern|Woodland|Wren Hollow".split('|'))
STREETS=('Lane','Road','Street','Way','Drive','Avenue','Court','Terrace','Circle','Place')
BUSINESSES={
 'retail':('General Store','Mercantile','Corner Market','Trading Post'),
 'boutique':('Cloth & Thread','Boutique','Wardrobe','Apparel','Style House'),
 'grocery':('Fresh Foods','Grocers','Food Market','Provisions','Farm & Pantry'),
 'restaurant':('Kitchen','Bistro','Table','Cafe','Diner','Supper House'),
 'gas_station':('Fuel & Market','Service Station','Fuel Stop','Travel Stop'),
 'car_dealership':('Motors','Auto Sales','Motor Company','Auto Gallery'),
 'trades':('Plumbing & Electrical','Trade Services','Mechanical Services','Home Trades'),
 'construction':('Builders','Construction','Building Company','Contracting'),
 'engineering':('Engineering','Design Engineering','Technical Design','Engineering Partners'),
 'factory':('Manufacturing','Fabrication','Precision Works','Industrial Products'),
 'rental':('Properties','Property Partners','Residential Holdings','Rental Company'),
 'property_management':('Property Management','Property Care','Building Management'),
 'bank':('Community Bank','Savings Bank','Bank & Trust','Banking Company'),
 'office':('Shared Services','Business Services','Corporate Services','Administrative Services'),
 'holding':('Enterprise Group','Holdings','Investment Group','Group'),
 'self_storage':('Self Storage','Storage Center','Storage Park','Secure Storage'),
 'logistics':('Freight','Logistics','Transport','Distribution'),
 'cleaning':('Cleaning Services','Clean Team','Janitorial Services','Building Care'),
 'landscaping':('Landscaping','Grounds Care','Garden Services','Landworks'),
 'security':('Security Services','Protective Services','Security Group'),
 'legal':('Legal Partners','Counsel','Law Practice','Legal Services'),
 'hr':('Talent Partners','Recruiting','People Services'),
 'it':('Technology Services','Systems Support','Digital Services'),
 'accounting':('Accounting','Bookkeeping','Accountants'),
 'finance':('Financial Advisory','Finance Partners','Financial Services'),
 'maintenance':('Maintenance Services','Building Maintenance','Repair Services'),
 'purchasing':('Supply Partners','Procurement','Supply Company'),
 'marketing':('Creative Studio','Marketing','Brand Partners'),
 'training':('Training Partners','Professional Development','Learning Services'),
}


def number(world,identity,part):
    return int.from_bytes(hashlib.sha256(f'{world.seed}:{identity}:{part}:names-v1'.encode()).digest()[:8],'big')


def pick(world,identity,candidate,used):
    used={str(name).casefold() for name in used}
    prefixes=Counter(name.split()[0] for name in used if name.split())
    best=None
    for attempt in range(10000):
        name=candidate(attempt)
        if name.casefold() in used:continue
        # Scan several independent alternatives so one familiar stem doesn't dominate.
        stem=name.split()[0].casefold()
        score=prefixes[stem]
        if best is None or score<best[0]:best=(score,name)
        if score==0 or (attempt>=31 and best):return best[1]
    if best:return best[1]
    raise ValueError('The fictional name catalog is exhausted.')


def business_name(world,identity,industry,used=None):
    from .employee_names import LAST
    if used is None:used=[b.name for b in world.businesses]+[r['name'] for r in world.systems.get('competitors',[])]
    endings=BUSINESSES.get(industry,('Company','Partners','Enterprises','Services'))
    def candidate(attempt):
        n=number(world,identity,attempt)
        place=PLACES[n % len(PLACES)]
        style=(n//len(PLACES)) % 4
        if style==1:place=LAST[(n//101) % len(LAST)]+"'s"
        elif style==2:
            other=(n//337) % len(PLACES)
            if PLACES[other]==place:other=(other+1) % len(PLACES)
            place=place+' & '+PLACES[other]
        ending=endings[(n//1009) % len(endings)]
        return place+' '+ending
    return pick(world,identity,candidate,used)


def property_name(world,identity,category='residential',kind=''):
    used=[p.name for p in world.properties]
    suffix={'commercial':'Shops','industrial':'Works','office':'Office Center','mixed_use':'Market Square'}
    def candidate(attempt):
        n=number(world,identity,attempt);place=PLACES[n % len(PLACES)]
        if category=='land':return place+(' Development Lot' if 'development' in kind.lower() else ' Lot')
        if category in suffix and n % 2:return place+' '+suffix[category]
        return str(10+n % 980)+' '+place+' '+STREETS[(n//997) % len(STREETS)]
    return pick(world,identity,candidate,used)


def tenant_name(world,identity,use='residential'):
    used=[r['name'] for r in world.systems.get('tenant_offers',[])]+[r.get('tenant_name','') for r in world.systems.get('leases',[])]+[p.tenant for p in world.properties if p.tenant]
    if use=='residential':
        from .employee_names import unique_name
        return unique_name(world,'tenant:'+identity,{str(n).casefold() for n in used}|{p.name.casefold() for p in world.people})
    industry={'commercial':'retail','office':'office','industrial':'factory'}.get(use,'retail')
    return business_name(world,'tenant:'+identity,industry,used+[b.name for b in world.businesses])


def supplier_name(world,identity,department):
    used=[o['supplier'] for o in world.systems.get('supplier_offers',[])]
    return business_name(world,'supplier:'+identity,department,used)
