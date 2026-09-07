"""Optional business capabilities. Kits consume equipment, cash and finite labor.

Unconfigured businesses retain their existing model; configuring an offer never
reprices accepted contracts or creates revenue merely by installing equipment.
"""
from datetime import date, timedelta
from .campaign import Campaign, integer, flag
from .domain import RuleError, daily_share


def kit(label, equipment, cost=0, days=0, monthly=0, **options):
    return dict(label=label,equipment=equipment,cost=cost,days=days,monthly=monthly,**options)


CATALOG={
 'gas_station':{
  'fuel':kit('Fuel sales','Existing pumps, tanks and payment terminal',kind='core',roles='Cashier + attendant',weight=80),
  'convenience_grocery':kit('Convenience groceries','Display shelves, refrigerated case and grocery POS module',1200000,3,20000,kind='sales',roles='Cashier + attendant (stocking)',weight=20,price=1200,unit_cost=750,demand=45,expiry=7),
  'coffee_snacks':kit('Coffee and packaged snacks','Coffee brewer, warming display and service counter',450000,2,12000,kind='sales',roles='Cashier + attendant (preparation)',weight=15,price=600,unit_cost=200,demand=70,expiry=3),
 },
 'engineering':{
  'pcb_design':kit('PCB design projects','Existing CAD workstations and electronics design tools',kind='project',roles='Engineer + technician (70% contribution)',weight=60,effort=10800,fee=2400000,materials=0,demand=900),
  'support':kit('Support retainers','Existing support and ticketing tools',kind='retainer',roles='Engineer + technician',weight=10,demand=60),
  'consulting':kit('Engineering consulting','Existing meeting and analysis tools',kind='consulting',roles='Engineer + technician',weight=30,demand=240),
  'drawing_review':kit('Drawing review and stamping','Review workstation, document control and signing tools',650000,3,25000,kind='project',roles='Engineer with current professional engineer license',license='professional_engineer',weight=20,effort=2400,fee=720000,materials=0,demand=240),
  'embedded_design':kit('Embedded controls design','Firmware toolchain, development boards, oscilloscope and test bench',1800000,4,40000,kind='project',roles='Engineer + technician (70% contribution)',weight=30,effort=14400,fee=3600000,materials=1000,demand=720),
  'prototype_testing':kit('PCB prototype testing','Bench supply, logic analyzer, fixtures and environmental test equipment',2400000,5,50000,kind='project',roles='Engineer + technician (70% contribution)',weight=25,effort=4800,fee=1440000,materials=2500,demand=480),
 },
 'factory':{
  'general_production':kit('General manufacturing orders','Existing general production machines and assembly benches',kind='project',roles='Machine operator + production worker',weight=100,effort=10800,fee=3000000,materials=5000,demand=600),
  'electronics_assembly':kit('Electronics assembly','Stencil printer, pick-and-place machine, reflow oven and inspection station',15000000,7,180000,kind='project',roles='Machine operator + production worker',weight=40,effort=7200,fee=2880000,materials=12000,demand=480),
  'precision_parts':kit('Precision machined parts','CNC mill, workholding, metrology tools and coolant system',21000000,7,220000,kind='project',roles='Machine operator + production worker',weight=40,effort=10800,fee=4320000,materials=14000,demand=360),
  'packaged_goods':kit('Packaged consumer goods','Mixer, filling line, labeler and packaging conveyor',8500000,5,100000,kind='project',roles='Machine operator + production worker',weight=30,effort=4800,fee=1200000,materials=6000,demand=900),
 },
}
CORE={'gas_station':'fuel','engineering':'pcb_design','factory':'general_production'}


def state(world,b):return world.systems.get('revenue_kits',{}).get(b.id)


def defaults(b):
    return {key:dict(enabled=True,weight=q['weight'],price_percent=b.price_percent if key=='fuel' else 100,ready='0001-01-01',lots=[]) for key,q in CATALOG.get(b.industry,{}).items() if not q['cost']}


def settings(world,b):return (state(world,b) or {}).get('offers',defaults(b))


def price_bounds(world,b,key):
    if any(f['operator']==b.id and f['status']=='active' for f in world.systems.get('franchises',[])):return 90,110
    return (75,150) if key=='fuel' else (50,175)


def active(world,b,key):
    row=settings(world,b).get(key)
    return bool(row and row['enabled'] and row['ready']<=world.date)


def tag(world,b,number):
    return (state(world,b) or {}).get('jobs',{}).get(str(number),dict(kit=CORE.get(b.industry,''),materials=b.material_hourly_cost//2 if b.industry=='factory' else b.material_hourly_cost))


def project_choices(world,b):
    return [key for key,q in CATALOG.get(b.industry,{}).items() if q['kind']=='project' and active(world,b,key)]


def quote(world,b,offer,kit_key=None):
    if not state(world,b):
        return {**offer,'blocked':'Configure revenue streams before choosing a specialty.'} if kit_key else offer
    keys=project_choices(world,b)
    if not keys:return {**offer,'blocked':'Enable an installed project stream and wait for its equipment setup to finish.'}
    if kit_key and kit_key not in keys:return {**offer,'blocked':'This stream is disabled, not installed or still being set up.'}
    key=kit_key or keys[(offer['number']-1)%len(keys)];q=CATALOG[b.industry][key]
    core=key==CORE[b.industry]
    base_minutes=(b.contract_base_minutes or b.contract_minutes) if core else q['effort']
    base_fee=(b.contract_base_fee or b.contract_fee) if core else q['fee']
    effort=max(60,base_minutes*offer['size']//6000*60)
    fee=max(100,base_fee*effort*offer['rate_percent']*settings(world,b)[key]['price_percent']//(base_minutes*10000))
    materials=(b.material_hourly_cost//2 if b.industry=='factory' else b.material_hourly_cost) if core else q['materials']
    return {**offer,'fee':fee,'minutes':effort,'kit':key,'label':q['label'],'materials':materials}


def remember(world,b,offer):
    if state(world,b):
        from .project_portfolio import jobs
        records=state(world,b)['jobs'];records[str(offer['number'])]=dict(kit=offer['kit'],materials=offer['materials'])
        keep={str(j['number']) for j in jobs(b)+b.project_history}
        state(world,b)['jobs']={number:record for number,record in records.items() if number in keep}


def commitment(world,b):
    from .project_portfolio import jobs
    total=sum(((j['minutes']-j['progress'])*tag(world,b,j['number'])['materials']+59)//60 for j in jobs(b))
    return max(0,total-world.systems.get('industry_state',{}).get(b.id,{}).get('finished_cost',0)) if b.industry=='factory' else total


def shares(world,b):
    from .project_portfolio import jobs
    committed={tag(world,b,j['number'])['kit'] for j in jobs(b)} if b.industry in ('engineering','factory') else set()
    rows=settings(world,b)
    return {key:row['weight'] for key,row in rows.items() if active(world,b,key) or key in committed}


def split_buckets(buckets,weights):
    total=sum(weights.values())
    return {key:{role:[v*weight//max(1,total) for v in values] for role,values in buckets.items()} for key,weight in weights.items()}


def capacity(rules,b,buckets,management):
    from .industries import project_capacity
    from .distress import Distress
    from .qualified_capacity import eligible,capacities
    from .simulation_support import stable_roll
    from .industry_operations import IndustryOperations
    result={}
    for key,pool in split_buckets(buckets,shares(rules.w,b)).items():
        q=CATALOG[b.industry][key];minutes={r:sum(v) for r,v in pool.items()}
        if q.get('license'):
            employees=[e for e in rules.staff(b.id) if rules.position(e.position_id).role=='engineer' and eligible(rules,e,q['license'])]
            # Named residual capacity already excludes property and office work.
            licensed=sum(capacities(rules,b,buckets,employees).values())
            work=min(minutes.get('engineer',0),licensed)
        elif b.industry=='factory':
            work=min(minutes.get('machine_operator',0),minutes.get('production_worker',0)*2)*b.capacity_percent//50
        else:work=project_capacity(b.industry,minutes)*management*min(120,b.capacity_percent)//10000
        if b.industry!='factory':work=work*IndustryOperations(rules.e).state(b)['equipment_condition']//100
        work=work*Distress(rules.e).capacity(b)//100
        price=settings(rules.w,b)[key]['price_percent']
        demand=q.get('demand',600)*max(15,200-price)//100
        demand=demand*IndustryOperations(rules.e).demand_factor(b)//100
        demand=demand*(90+stable_roll(rules.w,'kit-demand:'+b.id+key+rules.w.date,21))//100
        result[key]=max(0,min(work,demand))
    return result


class RevenueKits(Campaign):
    def initialize(self,b):
        from .project_portfolio import jobs
        return state(self.w,b) or dict(offers=defaults(b),jobs={str(j['number']):tag(self.w,b,j['number']) for j in jobs(b)},last={})

    def action(self,action,args,source):
        from .business_rules import BusinessRules
        from .authority import cash_forecast
        rules=BusinessRules(self.e);b=rules.company(args.get('business_id',''))
        if b.industry not in CATALOG:raise RuleError('Revenue kits are available for gas stations, engineering firms and factories.')
        if b.status not in ('operating','independent'):raise RuleError('Open the business before changing revenue streams.')
        key=args.get('kit','');q=CATALOG[b.industry].get(key)
        if not q:raise RuleError('Choose a revenue kit for this industry.')
        data=self.initialize(b);rows=data['offers']
        if action=='buy_revenue_kit':
            if key in rows:raise RuleError('This kit is already installed or being set up.')
            if cash_forecast(self.w,b.id,30)['available']<q['cost']+q['monthly']:
                raise RuleError('Kit funding must leave enough cash for the next 30 days of known obligations. Fund this business or reduce commitments.')
            self.e.post(b.id,source,'Revenue kit: '+q['label']+' — '+q['equipment'],{'asset:cash':-q['cost'],'asset:equipment':q['cost']})
            b.equipment+=q['cost']
            ready=(date.fromisoformat(self.w.date)+timedelta(days=q['days'])).isoformat()
            rows[key]=dict(enabled=True,weight=q['weight'],price_percent=100,ready=ready,lots=[])
            result=q['label']+' purchased. Equipment setup finishes '+ready+'. Staff and operating cash are still required.'
        elif action=='revenue_policy':
            if key not in rows:raise RuleError('Purchase the required equipment kit first.')
            rows[key].update(enabled=flag(args.get('enabled',False)),weight=integer(args.get('weight',rows[key]['weight']),1,100),price_percent=integer(args.get('price_percent',100),*price_bounds(self.w,b,key)))
            if key=='fuel':b.price_percent=rows[key]['price_percent']
            result=q['label']+' offering updated. Existing contracts retain their fees and continue using staff time; disabling stops new sales or contracts. Equipment remains owned.'
        elif action=='restock_stream':
            if key not in rows or q['kind']!='sales':raise RuleError('Install a sales kit before ordering its inventory.')
            units=integer(args.get('units',1),1,10000);cost=units*q['unit_cost']
            reserve=max(0,integer(args.get('reserve',0)))
            if self.w.cash(b.id)-cost<reserve:raise RuleError('This stock order would consume the required cash reserve.')
            self.e.post(b.id,source,'Inventory purchased: '+q['label'],{'asset:cash':-cost,'asset:stream_inventory:'+key:cost})
            rows[key]['lots'].append(dict(units=units,received=self.w.date))
            result=q['label']+' inventory purchased; it becomes an expense when sold or spoiled.'
        else:raise RuleError('Unknown revenue-stream action.')
        self.s.setdefault('revenue_kits',{})[b.id]=data
        if action!='restock_stream':self.e.event('Revenue streams updated',b.name+': '+result)
        return result

    def overhead(self,b):
        for key in settings(self.w,b):
            cost=daily_share(CATALOG[b.industry][key]['monthly'],date.fromisoformat(self.w.date))
            if cost:self.e.post(b.id,'kit-upkeep:'+b.id+key+':'+self.w.date,'Equipment upkeep and tools: '+CATALOG[b.industry][key]['label'],{'expense:kit_upkeep:'+key:cost,'liability:payable':-cost})

    def gas(self,rules,b,buckets,management,open_day):
        from .leadership import Leadership
        from .authority import Authority
        from .domain import GAME_RULES
        from .simulation_support import stable_roll
        from .industry_operations import IndustryOperations
        from .distress import Distress
        pools=split_buckets(buckets,shares(self.w,b));data=state(self.w,b);data['last']={}
        condition=IndustryOperations(self.e).state(b)['equipment_condition']
        core={role:[v*condition//100 for v in values] for role,values in pools.get('fuel',{}).items()} if active(self.w,b,'fuel') else {}
        for key,row in data['offers'].items():
            q=CATALOG[b.industry][key]
            if q['kind']!='sales':continue
            lots=row['lots'];expired=sum(l['units'] for l in lots if (date.fromisoformat(self.w.date)-date.fromisoformat(l['received'])).days>=q['expiry'])
            lots[:]=[l for l in lots if (date.fromisoformat(self.w.date)-date.fromisoformat(l['received'])).days<q['expiry']]
            if expired:self.e.post(b.id,'kit-spoilage:'+b.id+key+':'+self.w.date,'Expired '+q['label'],{'asset:stream_inventory:'+key:-expired*q['unit_cost'],'expense:spoilage:'+key:expired*q['unit_cost']})
            enabled=open_day and active(self.w,b,key)
            if enabled and b.auto_restock:
                units=max(0,q['demand']*3-sum(l['units'] for l in lots));cost=units*q['unit_cost']
                reserve=sum(e.salary for e in rules.staff(b.id))//4
                if units and self.w.cash(b.id)-cost>=reserve:
                    leadership=Leadership(self.e);record,emp=leadership.actor(b)
                    args=dict(business_id=b.id,kit=key,units=units,reserve=reserve)
                    configured=Authority(self.e).key(b,record) in Authority(self.e).contracts() or bool(leadership.director(b.id,False)[0])
                    if not (b.authority.get('enabled') or record or configured):self.action('restock_stream',args,'kit-stock:'+b.id+key+':'+self.w.date)
                    else:leadership.perform(b,'kit-stock:'+key,'restock_stream',args,cost,cost<=b.authority.get('purchasing_limit',0),'Replenish '+q['label']+' inventory as one complete order.')
            pool=pools.get(key,{})
            capacity=sum(min(pool.get('cashier',[0]*24)[h]//3,pool.get('attendant',[0]*24)[h]//2) for h in range(24))*management*b.capacity_percent//10000 if enabled else 0
            capacity=capacity*condition//100
            demand=q['demand']*max(15,200-row['price_percent'])//100 if enabled else 0
            demand=demand*(90+stable_roll(self.w,'kit-sales:'+b.id+key+self.w.date,21))//100
            demand=demand*IndustryOperations(self.e).demand_factor(b)*Distress(self.e).capacity(b)//10000
            quantity=min(capacity,demand,sum(l['units'] for l in lots));earned=quantity*q['price']*row['price_percent']//100
            if quantity:
                cost=quantity*q['unit_cost'];tax=earned*GAME_RULES['tax']['sales_percent']//100
                self.e.post(b.id,'kit-sales:'+b.id+key+':'+self.w.date,q['label']+' sold',{'asset:cash':earned+tax,'income:'+key:-earned,'liability:sales_tax':-tax,'asset:stream_inventory:'+key:-cost,'expense:cost_of_sales:'+key:cost})
                left=quantity
                for lot in lots:take=min(left,lot['units']);lot['units']-=take;left-=take
                lots[:]=[l for l in lots if l['units']]
            data['last'][key]=dict(output=quantity,revenue=earned,capacity=capacity,demand=demand,spoiled=expired,stock=sum(l['units'] for l in lots))
        for role in buckets:buckets[role]=core.get(role,[0]*24)

    def projects(self,rules,b,buckets,management,open_day):
        from .project_portfolio import jobs,autofill,deliver,remaining
        from .industry_operations import IndustryOperations
        budgets=capacity(rules,b,buckets,management) if open_day else {}
        data=state(self.w,b);data['last']={}
        autofill(rules,b,sum(v for key,v in budgets.items() if CATALOG[b.industry][key]['kind']=='project'))
        total_progress=total_earned=other=0;allocations=[]
        for key,row in data['offers'].items():
            q=CATALOG[b.industry][key];budget=budgets.get(key,0);earned=used=0
            if q['kind'] in ('retainer','consulting'):
                if budget and active(self.w,b,key):
                    rate=b.hourly_rate if q['kind']=='consulting' else 0
                    if q['kind']=='retainer':
                        from .business_rules import weekday_share
                        earned=weekday_share(b.retainer,date.fromisoformat(self.w.date))*min(60,budget)//60
                    else:earned=budget*rate//60
                    earned=earned*row['price_percent']//100;used=budget
                    rules.invoice(b,earned,'support_retainer' if key=='support' else 'hourly_consulting','kit-service:'+b.id+key+':'+self.w.date)
                    other+=used
            else:
                selected=[j for j in jobs(b) if tag(self.w,b,j['number'])['kit']==key]
                pending=sum(j['minutes']-j['progress'] for j in selected)
                budget=min(budget,pending)
                if b.industry=='factory':budget=budget//60*60
                # Allocate funds conservatively using the most expensive accepted
                # material rate in this stream. No automatic supplier borrowing.
                rate=max((tag(self.w,b,j['number'])['materials'] for j in selected),default=0)
                factory_state=IndustryOperations(self.e).state(b) if b.industry=='factory' and key=='general_production' else {}
                prepaid=min(budget//60,factory_state.get('finished_units',0))*60
                if rate:budget=min(budget,prepaid+self.w.cash(b.id)*60//rate)
                if b.industry=='factory':budget=budget//60*60
                if prepaid:
                    units=prepaid//60;cost=factory_state['finished_cost']*units//factory_state['finished_units']
                    self.e.post(b.id,'kit-existing-goods:'+b.id+':'+self.w.date,'Existing finished goods shipped',{'asset:finished_goods':-cost,'expense:project_materials:'+key:cost})
                    factory_state['finished_units']-=units;factory_state['finished_cost']-=cost
                produced_cost=((budget-prepaid)*rate+59)//60
                if produced_cost:
                    self.e.post(b.id,'kit-materials:'+b.id+key+':'+self.w.date,'Materials consumed: '+q['label'],{'asset:cash':-produced_cost,'expense:project_materials:'+key:produced_cost})
                if b.industry=='factory':
                    condition=IndustryOperations(self.e).state(b)['equipment_condition']
                    rejected=((budget-prepaid)//60)*max(0,100-condition)//200
                    budget-=rejected*60
                if budget:
                    used,earned,work=deliver(rules,b,budget,key,30 if b.industry=='factory' else 14,selected_numbers={j['number'] for j in selected})
                    total_progress+=used;total_earned+=earned;allocations.extend(work)
            data['last'][key]=dict(output=used,revenue=earned,capacity=budgets.get(key,0),demand=q['demand'])
        return dict(output=total_progress+other,unit='order minutes shipped' if b.industry=='factory' else 'qualified minutes',demand=remaining(b),qualified_capacity=sum(budgets.values()),project_minutes=total_progress,project_fee_earned=total_earned,project_allocations=allocations,bottleneck='Stream work shares, equipment setup/condition, qualified staff, customer demand and material cash; review revenue kits below')


def view(world,b):
    if b.industry not in CATALOG:return None
    from .authority import cash_forecast
    from .project_portfolio import jobs
    data=state(world,b);rows=settings(world,b);weights=shares(world,b);total=sum(weights.values())
    result=[]
    for key,q in CATALOG[b.industry].items():
        row=rows.get(key);installed=row is not None
        status='Not installed' if not installed else 'Setup until '+row['ready'] if row['ready']>world.date else 'Enabled' if row['enabled'] else 'Disabled for new work'
        if q.get('license'):
            status+=' · requires current professional engineer license'
        result.append(dict(q,key=key,min_price=price_bounds(world,b,key)[0],max_price=price_bounds(world,b,key)[1],installed=installed,status=status,enabled=row['enabled'] if row else False,weight=row['weight'] if row else q['weight'],price_percent=row['price_percent'] if row else 100,share=round(weights.get(key,0)*100/max(1,total)),last=(data or {}).get('last',{}).get(key),stock=sum(l['units'] for l in (row or {}).get('lots',[])),active_jobs=sum(tag(world,b,j['number'])['kit']==key for j in jobs(b))))
    return dict(configured=bool(data),rows=result,available=cash_forecast(world,b.id,30)['available'] if b.owner else 0)


def validate(world,b):
    data=state(world,b)
    if not data:return
    if b.industry not in CATALOG:raise RuleError('Invalid revenue-kit industry.')
    for number,record in data['jobs'].items():
        if record.get('kit') not in data['offers'] or type(record.get('materials')) is not int or record['materials']<0:raise RuleError('Invalid accepted revenue-stream contract.')
    for key,row in data['offers'].items():
        if key not in CATALOG[b.industry]:raise RuleError('Unknown installed revenue kit.')
        if type(row['enabled']) is not bool or not 1<=row['weight']<=100 or not 50<=row['price_percent']<=175:raise RuleError('Invalid revenue-stream policy.')
        date.fromisoformat(row['ready'])
        q=CATALOG[b.industry][key]
        if q['kind']=='sales':
            if any(type(l['units']) is not int or l['units']<0 for l in row['lots']):raise RuleError('Invalid stream inventory.')
            if world.accounts[b.id].get('asset:stream_inventory:'+key,0)!=sum(l['units'] for l in row['lots'])*q['unit_cost']:raise RuleError('Revenue-stream inventory does not reconcile.')
