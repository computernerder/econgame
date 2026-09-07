"""Named, licensed capacity for property work and office service queues."""
from datetime import date
from .domain import daily_share, GAME_RULES

TRADE_LICENSES={'electrical':'electrical','plumbing':'plumbing','heating_cooling':'hvac'}

def eligible(rules,emp,license_name=None):
    from .specialists import LICENSES
    from .workforce import Workforce
    p=rules.person(emp.person_id);pos=rules.position(emp.position_id)
    if emp.status!='active' or date.fromisoformat(rules.w.date).weekday() not in emp.days:return False
    if Workforce(rules.e).before_work(emp,p,date.fromisoformat(rules.w.date))[1]:return False
    for key in (license_name,pos.required_license or LICENSES.get(pos.role)):
        if key and p.licenses.get(key,'')<rules.w.date:return False
    return True

def capacities(rules,b,buckets,employees):
    pool=getattr(rules.e,'named_capacity',{}).get(b.id,{})
    # Test/legacy callers supplying their own buckets still get bounded named time.
    result={}
    for emp in employees:
        role=rules.position(emp.position_id).role
        personal=pool.get(emp.id,emp.weekly_hours*60//max(1,len(emp.days)))
        result[emp.id]=max(0,min(personal,sum(buckets.get(role,[]))))
    return result

def consume(rules,b,buckets,employees,minutes):
    if not hasattr(rules.e,'named_capacity'):rules.e.named_capacity={}
    pool=rules.e.named_capacity.setdefault(b.id,{})
    costs=0;used_staff=[];quality_minutes=0;used=0
    for emp in sorted(employees,key=lambda e:e.id):
        role=rules.position(emp.position_id).role;values=buckets.get(role,[])
        available=pool.get(emp.id,emp.weekly_hours*60//max(1,len(emp.days)))
        take=min(minutes,available,sum(values))
        if not take:continue
        pool[emp.id]=available-take;minutes-=take;used+=take;used_staff.append(emp.id)
        remaining=take
        for hour in range(len(values)):
            n=min(remaining,values[hour]);values[hour]-=n;remaining-=n
        costs+=labor_cost(rules,b,emp,take)
        quality_minutes+=take*rules.person(emp.person_id).skills.get('maintenance',30)
        if not minutes:break
    return used,costs,used_staff,quality_minutes//max(1,used)


def labor_cost(rules,b,emp,minutes):
    """The same real payroll allocation used by quotes and delivered service work."""
    from .workforce import Workforce
    policy=Workforce(rules.e).effective(b.id,emp)[0];today=date.fromisoformat(rules.w.date)
    overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
    wages=daily_share(emp.salary+overtime+emp.compensation.get('shift_premium',0),today)
    daily=wages+daily_share(Workforce(rules.e).benefit_cost(emp,policy),today)+wages*GAME_RULES['tax']['payroll_percent']//100
    initial=getattr(rules.e,'named_initial',{}).get(b.id,{}).get(emp.id,emp.weekly_hours*60//max(1,len(emp.days)))
    return daily*minutes//max(1,initial)


def estimated_cost(rules,b,buckets,employees,minutes):
    pool=getattr(rules.e,'named_capacity',{}).get(b.id,{})
    available={role:sum(values) for role,values in buckets.items()};cost=0
    for emp in sorted(employees,key=lambda e:e.id):
        role=rules.position(emp.position_id).role
        take=min(minutes,pool.get(emp.id,emp.weekly_hours*60//max(1,len(emp.days))),available.get(role,0))
        cost+=labor_cost(rules,b,emp,take);minutes-=take;available[role]=available.get(role,0)-take
        if not minutes:break
    return cost
