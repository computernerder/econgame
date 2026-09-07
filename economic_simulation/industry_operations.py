"""Inventory aging, manufacturing capacity, project rework and local progression."""
from datetime import date,timedelta
from .campaign import Campaign,integer
from .simulation_support import stable_roll
from .domain import RuleError


class IndustryOperations(Campaign):
    def state(self,b):
        return self.s.setdefault('industry_state',{}).setdefault(b.id,dict(equipment_condition=100,maintenance_meter=0,
            customer_relationships=50,inventory_age=0,rework_minutes=0,finished_units=0,finished_cost=0,improvements={}))

    def before(self,b,buckets):
        state=self.state(b);state.setdefault('improvements',{})
        for key,value in dict(equipment_condition=100,maintenance_meter=0,customer_relationships=50,inventory_age=0,rework_minutes=0,finished_units=0,finished_cost=0).items():state.setdefault(key,value)
        from .restaurant import active,settings
        today=date.fromisoformat(self.w.date)
        if active(self.w,b):
            if today.weekday() not in settings(self.w,b)['days']:return
        elif today.weekday()>=5:return
        state['maintenance_meter']+=3 if b.industry=='factory' else 1
        if state['maintenance_meter']>=20:state['equipment_condition']=max(10,state['equipment_condition']-1);state['maintenance_meter']=0
        factor=max(20,state['equipment_condition'])
        for role,values in buckets.items():
            if role in ('machine_operator','production_worker','mechanic','chef','builder','tradesperson'):
                buckets[role]=[value*factor//100 for value in values]
        for role,values in buckets.items():
            if role not in ('manager','hr','legal','accounting','finance','training'):
                buckets[role]=[v*(100+state['improvements'].get('automation',0)*3)//100 for v in values]
        if b.industry in ('construction','trades'):
            loss=stable_roll(self.w,b.id+':rework:'+self.w.date,21)
            if state['improvements'].get('quality'):loss//=2
            for role in ('builder','laborer','tradesperson','apprentice'):
                values=buckets.get(role,[]);wasted=sum(values)*loss//100;state['rework_minutes']+=wasted
                buckets[role]=[v*(100-loss)//100 for v in values]
        lots=self.lots(b)
        if b.industry=='grocery':
            spoiled=sum(lot['units'] for lot in lots if (date.fromisoformat(self.w.date)-date.fromisoformat(lot['received'])).days>=7)
            if spoiled:
                self.e.post(b.id,'spoilage:'+b.id+':'+self.w.date,'Expired grocery deliveries written off',{'asset:inventory':-spoiled*b.unit_cost,'expense:spoilage':spoiled*b.unit_cost})
                self.remove_stock(b,spoiled);b.inventory_units-=spoiled
        state['inventory_age']=max(((date.fromisoformat(self.w.date)-date.fromisoformat(lot['received'])).days for lot in lots if lot['units']),default=0)

    def lots(self,b):
        state=self.state(b)
        lots=state.setdefault('inventory_lots',[])
        difference=b.inventory_units-sum(lot['units'] for lot in lots)
        if difference>0:lots.append(dict(received=self.w.date,units=difference))
        elif difference<0:self.remove_stock(b,-difference,sync=False)
        return lots

    def add_stock(self,b,units):
        self.lots(b).append(dict(received=self.w.date,units=units))

    def remove_stock(self,b,units,sync=True):
        lots=self.lots(b) if sync else self.state(b)['inventory_lots']
        for lot in lots:
            take=min(units,lot['units']);lot['units']-=take;units-=take
            if not units:break
        lots[:]=[lot for lot in lots if lot['units']]

    def customer_feedback(self,b,operations):
        if not operations.get('demand'):return
        state=self.state(b);fill=operations.get('output',0)*100//max(1,operations['demand'])
        if fill<60:state['customer_relationships']=max(10,state['customer_relationships']-1)
        elif fill>=90 and date.fromisoformat(self.w.date).weekday()==4:
            state['customer_relationships']=min(100,state['customer_relationships']+1)

    def demand_factor(self,b):
        state=self.state(b)
        return 90+state['customer_relationships']//5+state.get('improvements',{}).get('loyalty',0)*3

    def sale_factor(self,b,quantity=0):
        if b.industry!='car_dealership':return 100
        remaining=quantity or b.inventory_units;total=count=0
        for lot in self.lots(b):
            units=min(remaining,lot['units']);remaining-=units;count+=units
            age=(date.fromisoformat(self.w.date)-date.fromisoformat(lot['received'])).days
            total+=units*max(70,100-age//15)
            if not remaining:break
        return total//max(1,count) if count else 100

    def factory(self,rules,b,minutes,open_day):
        state=self.state(b)
        from .distress import Distress
        qualified=min(minutes.get('machine_operator',0),minutes.get('production_worker',0)*2)
        capacity=qualified*b.capacity_percent*Distress(self.e).capacity(b)//300000 if open_day else 0
        from .project_portfolio import autofill,remaining as work_remaining,deliver
        autofill(rules,b,min(capacity,max(1,b.daily_demand or 10)*self.demand_factor(b)//100)*60)
        remaining=work_remaining(b)
        # Existing orders and unbilled earnings survive migration. Each finished
        # item fulfills 60 qualified minutes of the accepted manufacturing order.
        ordered=(remaining+59)//60
        unit_material=max(1000,b.material_hourly_cost//2)
        units=min(capacity,max(0,ordered-state['finished_units']),self.w.cash(b.id)//unit_material)
        material=units*unit_material
        if material:
            self.e.post(b.id,'manufacture:'+b.id+':'+self.w.date,'Raw materials converted into finished goods',{'asset:cash':-material,'asset:finished_goods':material})
            state['finished_units']+=units;state['finished_cost']+=material
        defects=units*max(0,100-state['equipment_condition']-state['improvements'].get('quality',0)*5)//200
        if defects:
            loss=state['finished_cost']*defects//max(1,state['finished_units'])
            self.e.post(b.id,'defects:'+b.id+':'+self.w.date,'Rejected manufacturing output',{'asset:finished_goods':-loss,'expense:quality_losses':loss})
            state['finished_units']-=defects;state['finished_cost']-=loss
        demand=max(1,b.daily_demand or 10)*self.demand_factor(b)//100 if open_day else 0
        sold=min(demand,state['finished_units'],ordered)
        progress=earned=0
        if sold:
            cost=state['finished_cost']*sold//state['finished_units']
            self.e.post(b.id,'factory-dispatch:'+b.id+':'+self.w.date,'Manufacturing order materials shipped',{'asset:finished_goods':-cost,'expense:project_materials':cost})
            state['finished_units']-=sold;state['finished_cost']-=cost
            progress,earned,allocations=deliver(rules,b,min(remaining,sold*60),'manufactured_goods',30)
        else:allocations=[]
        return dict(output=sold,unit='finished products shipped',demand=demand,capacity=capacity,produced=units,
            project_minutes=progress,project_fee_earned=earned,project_allocations=allocations,qualified_capacity=qualified,
            defects=defects,finished_units=state['finished_units'],bottleneck='Accepted orders, machine/labor capacity, material cash and quality; collection 30 days after completion')

    def collection(self,b,invoice):
        if invoice.get('defaulted'):return False
        from .customer_collections import RISK_INDUSTRIES
        if b.industry not in RISK_INDUSTRIES:return True
        if invoice.get('collection_attempted'):return True
        risk=stable_roll(self.w,'customer-payment:'+invoice['id'])
        # One fixed outcome per invoice: 1% default, 8% late, 91% on time.
        # Legacy defaults and promised dates above remain intact.
        if risk<1:
            invoice.update(defaulted=True,overdue_since=self.w.date)
            self.e.event('Customer default',b.name+' · '+invoice['id']+': payment default recorded. Customer collections offers a free reminder, installments, a contingency agency or legal recovery before a write-off.',True,financial_amount=invoice['amount'],invoice_id=invoice['id'])
            return False
        if risk<9:
            invoice.update(collection_attempted=True,due=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat(),overdue_since=self.w.date)
            self.e.event('Customer collection delayed',b.name+' · '+invoice['id']+': customer promised payment in 30 days. Collection retries automatically then. Use Customer collections to request earlier recovery.',True,financial_amount=invoice['amount'],invoice_id=invoice['id'])
            return False
        return True

    def action(self,args,source):
        from .business_rules import BusinessRules
        b=BusinessRules(self.e).company(args.get('business_id',''));state=self.state(b)
        kind=args.get('kind','maintenance')
        if kind not in ('maintenance','equipment','quality','loyalty','automation'):raise RuleError('Choose a local improvement.')
        level=state['improvements'].get(kind,0)
        if kind!='maintenance' and level>=3:raise RuleError('This location has completed this improvement track.')
        cost=(100000 if kind=='maintenance' else 250000)*(level+1)
        self.e.post(b.id,source,'Local operational improvement: '+kind,{'asset:cash':-cost,'expense:operational_development':cost})
        if kind=='maintenance':state['equipment_condition']=min(100,state['equipment_condition']+25)
        else:
            state['improvements'][kind]=level+1
            if kind=='equipment':b.capacity_percent=min(200,b.capacity_percent+10)
            if kind=='loyalty':state['customer_relationships']=min(100,state['customer_relationships']+8)
        return 'Local improvement delivered. Its cost is real; results remain limited by staff, inventory, condition and demand.'
