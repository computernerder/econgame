"""Funded land development and transaction-specific representation; fictional costs."""
from datetime import date, timedelta
from .campaign import Campaign, integer
from .domain import Property, RuleError
from .simulation_support import stable_roll

# Area, construction cost per square meter, comparable value, monthly rent per m2.
BLUEPRINTS = {
    'homes': ('Residential homes', 'residential', (), 120, 120000, 135000, 1100),
    'boutique': ('Boutique storefront', 'commercial', ('boutique','retail'), 180, 150000, 155000, 1500),
    'grocery': ('Grocery store', 'commercial', ('grocery',), 400, 170000, 165000, 1500),
    'restaurant': ('Restaurant premises', 'commercial', ('restaurant',), 200, 180000, 170000, 1800),
    'office': ('Office suites', 'office', ('office','engineering','bank','property_management'), 240, 150000, 160000, 1400),
    'factory': ('Factory building', 'industrial', ('factory',), 600, 190000, 180000, 1300),
    'workshop': ('Trade workshop', 'industrial', ('trades','construction'), 300, 110000, 120000, 900),
    'warehouse': ('Warehouse / storage', 'industrial', ('logistics','self_storage'), 600, 90000, 100000, 800),
    'gas_station': ('Fuel station premises', 'commercial', ('gas_station',), 400, 220000, 200000, 1700),
    'dealership': ('Dealership showroom', 'commercial', ('car_dealership',), 500, 160000, 155000, 1300),
}
LEVELS = {1: ('Starter',1,45), 2: ('Established',2,75), 3: ('Large',4,120)}

def representation(world,p,entity):
    return next((t for t in reversed(world.systems.get('service_tasks',[]))
        if t.get('product')=='property_representation' and t['target_id']==p.id
        and t['recipient']==entity and t['status']=='complete' and not t.get('used')
        and t.get('expires','')>=world.date),None)

def brokerage(world,p,entity,price,percent):
    ordinary=price*percent//100
    return ordinary*30//100 if representation(world,p,entity) else ordinary

def use_representation(world,p,entity,ordinary,paid):
    task=representation(world,p,entity)
    if task:task.update(used=world.date,fee_avoided=ordinary-paid,outcome=task['outcome']+f' Used at closing: ${ (ordinary-paid)/100:,.2f} lower brokerage fee.')

class Development(Campaign):
    def ensure(self, added_counties=None):
        if self.s.get('land_market_version') and not added_counties:return
        for index,region in enumerate(self.s['regions']):
            if added_counties is not None and region['id'] not in added_counties:continue
            for level in (1,3):
                size=1800 if level==1 else 6000
                p=Property(id=f'land-{index}-{level}',name=region['id']+(' Starter Lot' if level==1 else ' Development Lot'),
                    kind='Empty lot',region=region['id'],description='Vacant serviced land. Fund a suitable building before occupation or rent.',
                    full_value=size*(4000+(index%3)*500),full_rent=0,upkeep=size*20,condition=100,asking=size*(4000+(index%3)*500),category='land',usable_area=size)
                self.w.properties.append(p)
        self.s['land_market_version']=22

    def quote(self,p,blueprint,level):
        if p.category!='land':raise RuleError('Choose an empty lot.')
        if blueprint not in BLUEPRINTS:raise RuleError('Choose a building design.')
        level=integer(level,1,3);spec=BLUEPRINTS[blueprint];label,mult,days=LEVELS[level]
        area=spec[3]*mult
        if area*2>p.usable_area:raise RuleError('This lot is too small for the building, access and required setbacks.')
        construction=area*spec[4];permits=construction//20;contingency=construction//10
        return dict(blueprint=blueprint,level=level,area=area,days=days,construction=construction,permits=permits,
            contingency=contingency,total=construction+permits+contingency,
            estimated_value=p.value+area*spec[5]*self.s.get('cycle',100)//100,
            rent=area*spec[6],label=label+' '+spec[0])

    def action(self,args,source):
        p=self.e.get_property(args.get('property_id',''));self.require(p.owner)
        if p.status!='vacant':raise RuleError('Development requires an owned vacant lot with no other project.')
        q=self.quote(p,args.get('blueprint','homes'),args.get('level',1))
        self.e.post(p.owner,source,'Reserve construction, approvals and contingency',{'asset:cash':-q['total'],'asset:development_reserve':q['total']})
        record=dict(q,id=self.uid('development'),property_id=p.id,owner=p.owner,created=self.w.date,
            due=(date.fromisoformat(self.w.date)+timedelta(days=q['days'])).isoformat(),elapsed=0,
            prepaid=q['total'],spent=0,status='building',land_value=p.value,land_area=p.usable_area)
        self.s.setdefault('developments',[]).append(record);p.status='building'
        return f"{q['label']} funded: ${q['total']/100:,.2f} reserved, {q['days']} days. No tenant, business or operating equipment is purchased."

    def tick(self):
        self.ensure()
        for job in self.s.get('developments',[]):
            if job['status']!='building':continue
            p=self.e.get_property(job['property_id'])
            if p.owner!=job['owner']:raise RuleError('Development ownership changed during funded work.')
            job['elapsed']+=1
            # Existing site and weather uncertainty, bounded by the funded contingency.
            overrun=job['contingency']*stable_roll(self.w,job['id']+':site-cost',101)//100
            final=job['construction']+job['permits']+overrun
            target=final*min(job['elapsed'],job['days'])//job['days'];cost=target-job['spent']
            self.e.post(p.owner,job['id']+':'+self.w.date,'Completed permitted construction',{'asset:development_reserve':-cost,'asset:property':cost})
            job['prepaid']-=cost;job['spent']+=cost;p.basis+=cost
            if job['elapsed']<job['days']:continue
            refund=job['prepaid']
            if refund:self.e.post(p.owner,job['id']+':refund','Unused construction contingency returned',{'asset:development_reserve':-refund,'asset:cash':refund})
            spec=BLUEPRINTS[job['blueprint']];quality=75+stable_roll(self.w,job['id']+':quality',21)
            p.category=spec[1];p.kind=job['label'];p.specialization=list(spec[2]);p.usable_area=job['area']
            p.full_value=job['land_value']+job['area']*spec[5]*self.s.get('cycle',100)//100
            p.full_rent=job['rent'];p.upkeep=job['area']*150;p.condition=quality;p.status='vacant'
            from .property_operations import SYSTEMS
            self.s.setdefault('property_systems',{})[p.id]={key:dict(condition=quality,age=0,maintained_until='',wear=0) for key in SYSTEMS}
            self.s.setdefault('property_condition_baseline',{})[p.id]=quality
            job.update(status='complete',completed=self.w.date,prepaid=0,refunded=refund,quality=quality)
            self.e.event('Building ready for occupancy',p.name+': '+p.kind+f' completed at ${job["spent"]/100:,.2f}; estimated value ${p.value/100:,.2f}. Lease it or move in a compatible business.',True)

def owner_busy(world):
    return any(j['provider']=='owner' and j['status']=='working' for j in world.systems.get('property_work',[]))

# Recovery, mandated approvals and reading remain available while doing owner repairs.
RECOVERY={'advance','settings','profile','time_off_decide','management_approve','management_defer','decide',
          'outsource_property_work','fund_business','invest','withdraw','borrow','repay_loan','settle_obligations',
          'negotiate_terms','close_operation','new_campaign','leadership_activity_read','time_off_cancel'}
