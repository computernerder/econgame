"""One-location restaurant growth, meal-time coverage and finite operations."""
import copy
import math
from datetime import date,timedelta
from .campaign import Campaign,integer,flag
from .domain import RuleError,daily_share
from .simulation_support import stable_roll

SCALES={
    1:dict(name='Neighborhood restaurant',seats=40,kitchen=35,cost=0,days=0,overhead=0),
    2:dict(name='Busy local restaurant',seats=80,kitchen=75,cost=6500000,days=14,overhead=180000),
    3:dict(name='Destination restaurant',seats=140,kitchen=125,cost=14000000,days=21,overhead=360000),
    4:dict(name='Large restaurant',seats=220,kitchen=200,cost=24000000,days=28,overhead=600000)}
ROLES=('manager','chef','prep_cook','server','dishwasher','host')
DAY_NAMES=('Mon','Tue','Wed','Thu','Fri','Sat','Sun')
PURPOSES={'manager':'Covers each service hour; one manager can supervise eight other staff on that shift.',
    'chef':'Cooks meals. Uncovered preparation also uses chef time.',
    'prep_cook':'Prepares ingredients, freeing chefs to cook during busy service.',
    'server':'Serves guests. Uncovered hosting and dishwashing consume server time.',
    'dishwasher':'Washes and resets tableware, freeing servers for guests.',
    'host':'Seats guests and handles pickup orders, freeing servers for service.'}
MINUTES={'chef':5,'prep_cook':2,'server':4,'dishwasher':1.5,'host':0.75}


def active(world,b):return b.industry=='restaurant' and b.id in world.systems.get('restaurants',{})


def settings(world,b):
    return dict(dict(level=1,days=[0,1,2,3,4],opens=8,closes=16,takeaway=10,stock_days=2,
        marketing_monthly=0,planning_covers=0,auto_schedule=True,manual_staff=[]),
        **world.systems.get('restaurants',{}).get(b.id,{}))


def parse_days(value):
    values=value if isinstance(value,list) else str(value).split(',')
    try:days=sorted(set(integer(d,0,6) for d in values))
    except (ValueError,TypeError):raise RuleError('Choose working days from Monday through Sunday.')
    if not days:raise RuleError('Choose at least one working day.')
    return days


def weights(plan):
    return {hour:(6 if hour<10 else 15 if 11<=hour<=13 else 20 if 17<=hour<=20 else 5)
            for hour in range(plan['opens'],plan['closes'])}


def expected(world,b,day=None):
    from .economy import Economy
    from .domain import Engine
    plan=settings(world,b);day=day or date.fromisoformat(world.date)
    if day.weekday() not in plan['days']:return 0
    audience=plan.get('audience',b.daily_demand)
    demand=audience*(85,90,95,100,120,140,115)[day.weekday()]//100
    demand=demand*max(25,200-b.price_percent)//100
    demand=demand*Economy(Engine(world)).demand_factor(b)//100
    # Read the saved relationship rather than initializing industry state in a view.
    state=world.systems.get('industry_state',{}).get(b.id,{})
    demand=demand*(90+state.get('customer_relationships',50)//5+state.get('improvements',{}).get('loyalty',0)*3)//100
    return demand


def hour_demands(plan,demand):
    shares=weights(plan);total=sum(shares.values());result={};used=0
    for hour,weight in shares.items():
        amount=demand*weight//total;result[hour]=amount;used+=amount
    for hour in sorted(shares,key=lambda h:(-shares[h],h))[:demand-used]:result[hour]+=1
    return result


def targets(world,b):
    plan=settings(world,b);planned=plan['planning_covers'] or max(expected(world,b,date.fromisoformat(world.date)+timedelta(days=i)) for i in range(7))
    days=len(plan['days']);hours=plan['closes']-plan['opens'];volume=min(planned,SCALES[plan['level']]['kitchen']*hours)
    # Include a 15% allowance for breaks, ordinary skill and handoffs.
    result={role:math.ceil(volume*minutes*days/60/0.85) for role,minutes in MINUTES.items()}
    other=sum(result.values())
    result['manager']=max(hours*days,math.ceil(other/8))
    return result


def capacity(world,b,buckets,demand,stock=None):
    """Hourly resources cannot be carried from an empty morning into dinner."""
    plan=settings(world,b);scale=SCALES[plan['level']];hourly=[];served=potential=0
    stock=b.inventory_units if stock is None else stock
    equipment=world.systems.get('industry_state',{}).get(b.id,{}).get('equipment_condition',100)
    factor=min(150,max(0,b.capacity_percent))*max(20,equipment)//100
    if plan.get('expansion'):factor=factor*75//100
    for hour,wanted in hour_demands(plan,demand).items():
        minutes={r:buckets.get(r,[0]*24)[hour] for r in ROLES}
        active_staff=sum(minutes[r] for r in ROLES if r!='manager')/60
        management=min(100,minutes['manager']*800//max(60,int(active_staff*60))) if minutes['manager'] else 75
        management=max(40,management)
        kitchen=scale['kitchen']*factor//100
        tables=scale['seats']*60*100//(75*max(10,100-plan['takeaway']))
        ceiling=min(kitchen,tables)
        low,high=0,ceiling
        while low<high:
            units=(low+high+1)//2
            cooking=units*5+max(0,units*2-minutes['prep_cook'])
            service=units*4+max(0,units*1.5-minutes['dishwasher'])+max(0,units*0.75-minutes['host'])
            if cooking<=minutes['chef'] and service<=minutes['server']:low=units
            else:high=units-1
        cap=low*management//100
        quantity=min(wanted,cap,stock);stock-=quantity;served+=quantity;potential+=cap
        bottleneck=('Ingredients' if stock==0 and quantity<min(wanted,cap) else
            'Kitchen equipment' if kitchen<=tables and cap>=kitchen and wanted>cap else
            'Dining space' if tables<kitchen and cap>=tables and wanted>cap else
            'Manager coverage' if management<100 and wanted>cap else
            'Kitchen / service shift coverage' if cap<wanted else 'Customer demand')
        hourly.append(dict(hour=hour,demand=wanted,capacity=cap,served=quantity,lost=max(0,wanted-quantity),constraint=bottleneck,
                           chefs=minutes['chef']//60,servers=minutes['server']//60))
    worst=max(hourly,key=lambda row:row['lost'],default={})
    return dict(output=served,demand=demand,capacity=potential,unit='meals served',hourly=hourly,
        lost_customers=max(0,demand-served),bottleneck=worst.get('constraint','Closed today'))


class Restaurant(Campaign):
    def company(self,bid):
        from .business_rules import BusinessRules
        b=BusinessRules(self.e).company(bid)
        if b.industry!='restaurant':raise RuleError('Choose a restaurant for this operating plan.')
        return b

    def ensure(self,b):
        if not active(self.w,b):self.s.setdefault('restaurants',{})[b.id]=settings(self.w,b)
        return self.s['restaurants'][b.id]

    def action(self,action,args,source):
        from .business_rules import BusinessRules
        rules=BusinessRules(self.e)
        if action=='restaurant_rota':
            emp=rules.contract(args.get('employment_id',''));b=self.company(emp.employer)
            trial=copy.deepcopy(emp);trial.days=parse_days(args.get('days',emp.days))
            trial.shift_start=integer(args.get('shift_start',emp.shift_start),0,20)
            rules.check_schedule(trial,replacing=emp.id)
            from .shared_services import SharedServices
            snapshot=copy.deepcopy(self.w)
            employee=next(e for e in snapshot.employments if e.id==emp.id);employee.days=trial.days;employee.shift_start=trial.shift_start
            from .domain import Engine
            SharedServices(Engine(snapshot)).validate()
            emp.days=trial.days;emp.shift_start=trial.shift_start
            plan=self.ensure(b);manual=set(plan['manual_staff'])
            if flag(args.get('manager_schedule',False)):manual.discard(emp.id)
            else:manual.add(emp.id)
            plan['manual_staff']=sorted(manual)
            rules.record(emp.person_id,'Restaurant rota: '+', '.join(DAY_NAMES[d] for d in emp.days)+f' from {emp.shift_start:02}:00; pay and weekly hours unchanged. '+('Manager may adjust coverage.' if emp.id not in manual else 'Player-pinned schedule.'))
            end=emp.shift_start*60+emp.weekly_hours*60//len(emp.days)
            return (rules.person(emp.person_id).name+': '+', '.join(DAY_NAMES[d] for d in emp.days)+
                f' {emp.shift_start:02}:00–{end//60:02}:{end%60:02}. '+
                ('Manager may adjust this schedule. ' if emp.id not in manual else 'Schedule pinned by the player. ')+
                'Weekly contracted hours, pay, approved leave and employee identity are unchanged.')
        b=self.company(args.get('business_id',''))
        if action=='restaurant_schedule':
            from .restaurant_staffing import suggestions
            self.ensure(b)
            changes=suggestions(self.w,b)
            for change in changes:self.action('restaurant_rota',change,source)
            return f'{len(changes)} shifts updated for meal-time coverage. Pinned shifts, shared-service commitments, pay and weekly contracted hours are preserved.'
        if action=='restaurant_plan':
            old=settings(self.w,b)
            changed=dict(days=parse_days(args.get('days',old['days'])),opens=integer(args.get('opens',old['opens']),5,16),
                closes=integer(args.get('closes',old['closes']),12,24),takeaway=integer(args.get('takeaway',old['takeaway']),0,80),
                stock_days=integer(args.get('stock_days',old['stock_days']),1,5),marketing_monthly=integer(args.get('marketing_monthly',old['marketing_monthly']),0,5000000),
                planning_covers=integer(args.get('planning_covers',old['planning_covers']),0,2000),auto_schedule=flag(args.get('auto_schedule',True)))
            if not 4<=changed['closes']-changed['opens']<=16:raise RuleError('Open for between four and sixteen hours per day.')
            self.ensure(b).update(changed)
            self.s['restaurants'][b.id]['rota_requested']=True
            return ('Restaurant plan: '+', '.join(DAY_NAMES[d] for d in changed['days'])+
                f" {changed['opens']:02}:00–{changed['closes']:02}:00; {changed['stock_days']} days of ingredients; {changed['takeaway']}% takeaway; ${changed['marketing_monthly']/100:,.0f}/month advertising. "+
                'Opening hours now govern meal-time trade, including selected weekends. '
                'The manager can stagger unpinned shifts when scheduling is enabled; staffing targets guide hiring within existing limits. '
                'Advertising is a recurring expense, not guaranteed customers. A planning volume is a staffing goal, not booked sales.')
        if action=='restaurant_expand':
            plan=settings(self.w,b);level=plan['level']+1
            if level not in SCALES:raise RuleError('This restaurant has reached the largest single-location layout.')
            if plan.get('expansion'):raise RuleError('Finish the current restaurant expansion before starting another.')
            if b.status!='operating':raise RuleError('The restaurant must be operating before expansion.')
            q=SCALES[level]
            if self.w.cash(b.id)<q['cost']:raise RuleError('Fund the full restaurant expansion before booking work.')
            self.e.post(b.id,source,'Fund restaurant kitchen and dining fit-out',{'asset:cash':-q['cost'],'asset:construction_in_progress':q['cost']})
            plan=self.ensure(b);plan['expansion']=dict(level=level,cost=q['cost'],due=(date.fromisoformat(self.w.date)+timedelta(days=q['days'])).isoformat())
            return f"Expansion funded: {q['seats']} seats and {q['kitchen']} kitchen meals/hour after {q['days']} days. Kitchen capacity falls 25% during work. Extra operating costs begin on completion; demand and staff are still required."
        raise RuleError('Unknown restaurant action.')

    def begin_day(self,b,today):
        plan=self.ensure(b);project=plan.get('expansion')
        if project and project['due']<=self.w.date:
            previous=SCALES[plan['level']];next_scale=SCALES[project['level']]
            self.e.post(b.id,'restaurant-fitout:'+b.id+':'+self.w.date,'Restaurant fit-out completed',{'asset:construction_in_progress':-project['cost'],'asset:equipment':project['cost']})
            b.equipment+=project['cost'];b.monthly_overhead+=next_scale['overhead']-previous['overhead'];plan['level']=project['level'];plan.pop('expansion')
            self.e.event('Restaurant expansion completed',b.name+' now has '+str(next_scale['seats'])+' seats. Review staffing, opening hours and demand.',True)
        cost=daily_share(plan['marketing_monthly'],today)
        paid=min(cost,max(0,self.w.cash(b.id)))
        if paid:self.e.post(b.id,'restaurant-marketing:'+b.id+':'+self.w.date,'Local restaurant advertising',{'asset:cash':-paid,'expense:marketing':paid})
        plan['marketing_paid_today']=paid

    def sales(self,b,buckets,open_day,specialists):
        if not open_day:return dict(output=0,demand=0,capacity=0,hourly=[],lost_customers=0,unit='meals served',bottleneck='Closed today; payroll and holding costs continue.')
        from .distress import Distress
        demand=expected(self.w,b)*(92+stable_roll(self.w,'restaurant:'+b.id+':'+self.w.date,17))//100
        demand=demand*(100+specialists['marketing_percent'])//100*Distress(self.e).capacity(b)//100
        return capacity(self.w,b,buckets,demand)

    def feedback(self,b,operations):
        plan=self.ensure(b);demand=operations['demand'];served=operations['output']
        if not demand:return
        audience=plan.get('audience',b.daily_demand)
        region=next(r for r in self.s['regions'] if r['id']==b.region)
        limit=max(b.daily_demand,min(2000,max(600,region['population']//50)))
        if served*100>=demand*80:
            audience+=max(1,served//80)+plan.get('marketing_paid_today',0)//5000
        elif served*100<demand*50:audience-=max(1,audience//100)
        plan['audience']=max(20,min(limit,audience));plan['market_limit']=limit
