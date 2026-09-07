"""Prepaid outside-service agreements with finite capacity and expiring credit."""
from datetime import date, timedelta
from .campaign import Campaign
from .domain import RuleError
from .simulation_support import stable_roll


class SupplierContracts(Campaign):
    def offers(self,task,quality):
        names=('Regional Practice','Specialist Cooperative','National Service Bureau')
        offers=self.s.setdefault('supplier_offers',[])
        for index,(minutes,capacity) in enumerate(((1200,120),(3600,240),(7200,360))):
            willing=stable_roll(self.w,'supplier:'+task['id']+':'+str(index))<quality
            rate=150-max(1,quality*(index+1)//15)
            offers.append(dict(id=self.uid('supplier-offer'),request=task['id'],buyer=task['recipient'],
                department=task['service_department'],supplier=names[index],original_rate=150,rate=rate,
                minutes=minutes,daily_capacity=capacity,valid_until=(date.fromisoformat(self.w.date)+timedelta(days=14)).isoformat(),
                credit_days=60,status='open' if willing else 'refused',created=self.w.date))
        task['outcome']='Three suppliers responded with capacity, rates and prepaid blocks; some may refuse. Quotes are future terms, not cash savings. Unused unassigned credits expire after 60 days.'

    def action(self,args,source):
        buyer=self.require(args.get('entity','personal'))
        offer=next((o for o in self.s.get('supplier_offers',[]) if o['id']==args.get('offer_id') and o['buyer']==buyer),None)
        if not offer or offer['status']!='open' or offer['valid_until']<self.w.date:
            raise RuleError('Choose a current accepted supplier quote for this account.')
        if any(c['buyer']==buyer and c['department']==offer['department'] and c['status']=='active' and c['expires']>=self.w.date for c in self.s.get('supplier_contracts',[])):
            raise RuleError('This account already has an active agreement for the department. Use it before buying another block.')
        cost=offer['minutes']*offer['rate']
        self.e.post(buyer,source,'Prepaid outside-service agreement',{'asset:cash':-cost,'asset:service_credit':cost})
        contract=dict(id=self.uid('supplier-contract'),buyer=buyer,department=offer['department'],supplier=offer['supplier'],
            rate=offer['rate'],minutes=offer['minutes'],available=offer['minutes'],credit=cost,paid=cost,
            daily_capacity=offer['daily_capacity'],created=self.w.date,
            expires=(date.fromisoformat(self.w.date)+timedelta(days=offer['credit_days'])).isoformat(),
            status='active',delivered=0,expired_cost=0,expense=0,last_day='',used_today=0,source_offer=offer['id'])
        self.s.setdefault('supplier_contracts',[]).append(contract);offer['status']='accepted'
        return f'Prepaid ${cost/100:,.2f} for {offer["minutes"]/60:g} hours. All assigned tasks share {offer["daily_capacity"]/60:g} provider hours per day. Unused unassigned credit expires on {contract["expires"]}.'

    def contract(self,task):
        return next((c for c in self.s.get('supplier_contracts',[]) if c['id']==task.get('supplier_contract')),None)

    def reserve(self,task,source):
        if task['mode']!='outside':return False
        contract=next((c for c in self.s.get('supplier_contracts',[]) if c['buyer']==task['recipient'] and c['department']==task['department']
                       and c['status']=='active' and c['expires']>=self.w.date and c['available']>=task['effort']),None)
        if not contract:return False
        cost=task['effort']*contract['rate'];contract['available']-=task['effort'];contract['credit']-=cost
        task.update(supplier_contract=contract['id'],outside_rate=contract['rate'],prepaid=cost)
        self.e.post(task['recipient'],source,'Assign purchased service credit to project',{'asset:service_credit':-cost,'asset:prepaid_services':cost})
        return True

    def capacity(self,task):
        contract=self.contract(task)
        if not contract:return 240
        if contract['last_day']!=self.w.date:contract.update(last_day=self.w.date,used_today=0)
        return max(0,contract['daily_capacity']-contract['used_today'])

    def delivered(self,task,minutes):
        contract=self.contract(task)
        if contract:
            contract['used_today']+=minutes;contract['delivered']+=minutes;contract['expense']+=minutes*contract['rate']

    def release(self,task,source):
        """Purchased blocks return credit, never turn into a cash-refund loophole."""
        contract=self.contract(task)
        if not contract:return False
        value=task.get('prepaid',0)
        if not value:return True
        if contract['expires']>=self.w.date and contract['status']=='active':
            self.e.post(task['recipient'],source,'Unused project credit returned to agreement',{'asset:prepaid_services':-value,'asset:service_credit':value})
            contract['credit']+=value;contract['available']+=value//contract['rate']
        else:
            self.e.post(task['recipient'],source,'Expired cancelled project credit',{'asset:prepaid_services':-value,'expense:unused_service_credit':value})
            contract['expired_cost']+=value
        task['prepaid']=0
        return True

    def tick(self):
        for contract in self.s.get('supplier_contracts',[]):
            if contract['status']=='active' and contract['expires']<self.w.date:
                value=contract['credit']
                if value:self.e.post(contract['buyer'],contract['id']+':expiry','Unused outside-service credit expired',{'asset:service_credit':-value,'expense:unused_service_credit':value})
                contract.update(status='expired',credit=0,available=0,expired_cost=contract['expired_cost']+value)
                self.e.event('Service agreement expired',contract['supplier']+f': ${value/100:,.2f} unused credit expensed. Already reserved projects retain their purchased delivery capacity.',value>0,financial_amount=value)
