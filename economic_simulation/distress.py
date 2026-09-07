"""Dated payable lots, contractual arrears and finite recovery windows."""
from datetime import date,timedelta
import calendar
from .campaign import Campaign
from .domain import RuleError


def tracked(key):
    return key.startswith('liability:') and not any(x in key for x in ('deposit','loan:','interest:','internal_loan:','internal_interest:'))


def due_date(world,key):
    today=date.fromisoformat(world.date)
    if key=='liability:payroll':return (today+timedelta(days=(4-today.weekday())%7)).isoformat()
    if key=='liability:income_tax':return date(today.year+1,4,15).isoformat()
    if key=='liability:sales_tax':return today.replace(day=calendar.monthrange(today.year,today.month)[1]).isoformat()
    return world.date


def track(world,entity,source,lines):
    if not world.systems:return
    accounts=world.accounts[entity]
    for key,value in lines.items():
        if not tracked(key):continue
        records=world.systems.setdefault('obligation_lots',{}).setdefault(entity,{})
        if key not in records:
            old=max(0,-accounts.get(key,0))
            records[key]=[dict(source='opening:'+key,created=world.date,due=due_date(world,key),remaining=old)] if old else []
        lots=records[key]
        if value<0:lots.append(dict(source=source,created=world.date,due=due_date(world,key),remaining=-value))
        else:
            left=value
            for lot in sorted(lots,key=lambda r:(r['due'],r['created'])):
                paid=min(left,lot['remaining']);lot['remaining']-=paid;left-=paid
        records[key]=[lot for lot in lots if lot['remaining']]


class Distress(Campaign):
    def liquidation_accounts(self,entity):
        allowed=('asset:inventory','asset:finished_goods','asset:equipment','asset:equipment_accumulated','asset:customer_loans','asset:loan_interest')
        return {k:v for k,v in self.w.accounts[entity].items() if (k in allowed or k.startswith('asset:stream_inventory:')) and v}

    def liquidations(self):
        from .simulation_support import stable_roll
        for plan in self.s.get('asset_liquidations',[]):
            if plan['status']!='marketing' or plan['due']>self.w.date:continue
            b=next(b for b in self.w.businesses if b.id==plan['entity'])
            if stable_roll(self.w,plan['id']+':buyer')<20:
                plan['status']='failed';self.e.event('Asset buyer withdrew',b.name+': liquidation did not close. Assets and debts remain; another sale can be marketed.',True);continue
            accounts=self.liquidation_accounts(b.id);book=sum(accounts.values());proceeds=max(0,book)*plan['percent']//100
            if accounts:self.e.post(b.id,plan['id'],'Close sale of remaining operating assets',{'asset:cash':proceeds,'expense:liquidation_loss':book-proceeds,**{k:-v for k,v in accounts.items()}})
            b.inventory_units=b.equipment=0;b.bank_loans=[]
            kits=self.s.get('revenue_kits',{}).get(b.id)
            if kits:
                for row in kits['offers'].values():row.update(lots=[],enabled=False)
            state=self.s.get('industry_state',{}).get(b.id)
            if state:state.update(inventory_lots=[],finished_units=0,finished_cost=0)
            plan.update(status='sold',proceeds=proceeds,book_value=book,loss=book-proceeds)
            self.e.event('Operating assets liquidated',b.name+f': ${proceeds/100:,.2f} cash received and ${max(0,book-proceeds)/100:,.2f} book loss. Deposits, wages and debt still require settlement.',True)

    def obligations(self,entity):
        result=[]
        for key,lots in self.s.get('obligation_lots',{}).get(entity,{}).items():
            for lot in lots:result.append(dict(account=key,**lot))
        for loan in self.s.get('loans',[]):
            if loan['entity']==entity and loan.get('arrears',0):
                result.append(dict(account='loan:'+loan['id'],source=loan['id'],created=loan.get('overdue_since',self.w.date),due=loan.get('overdue_since',self.w.date),remaining=loan['arrears']))
        return result

    def close(self,b,reason):
        if b.status=='closed':return
        b.status='closed';b.auto_restock=b.auto_projects=False
        for plan in self.s['plans']:
            if plan.get('entity')==b.id and plan.get('kind') in ('opening','upgrade') and plan['status']=='active':plan['status']='cancelled'
        b.opening_on=None
        for record in self.s.get('executives',{}).values():
            if record['employer']==b.id:record['active']=False
            if b.id in record['business_ids']:record['business_ids'].remove(b.id)
        for emp in self.w.employments:
            if emp.employer!=b.id or emp.status not in ('active','joining'):continue
            if emp.status=='active':
                cost=emp.salary//4
                self.e.post(b.id,'closure:'+emp.id,'Closure severance obligation',{'expense:severance':cost,'liability:payroll':-cost})
            emp.status='ended';emp.end_date=self.w.date
            person=next(p for p in self.w.people if p.id==emp.person_id)
            person.candidate=True;person.labor_state='unemployed'
            person.history.append(dict(date=self.w.date,event='Employment ended when '+b.name+' closed. Earned wages remain payable.'))
        for assignment in self.s['assignments']:
            if assignment['source']==b.id or assignment['target']==b.id:assignment['active']=False
        for record in self.s.get('directors',[]):
            if b.id in record['business_ids']:record['business_ids'].remove(b.id)
        for request in self.s.get('management_requests',[]):
            if request['business_id']==b.id and request['status']=='open':request.update(status='cancelled',resolved=self.w.date)
        unbilled=self.w.accounts[b.id].get('asset:unbilled',0)
        if unbilled:self.e.post(b.id,'close-project:'+b.id,'Unfinished project written off on closure',{'asset:unbilled':-unbilled,'expense:project_writeoff':unbilled})
        b.project_active=False;b.project_progress=b.project_earned=0;b.parallel_projects=[]
        self.s.setdefault('distress',{}).setdefault(b.id,{}).update(phase='closed',closed=self.w.date,reason=reason)
        self.e.event('Business closed',b.name+': '+reason+' Assets, receivables and liabilities remain with this entity. No automatic parent bailout.',True)

    def tick(self):
        self.liquidations()
        for entity,accounts in list(self.w.accounts.items()):
            if not self.controlled(entity):continue
            # Recognized older balances begin their recovery window when first observed.
            track(self.w,entity,'opening-obligations',{key:0 for key,value in accounts.items() if tracked(key) and value<0})
            b=next((b for b in self.w.businesses if b.id==entity),None)
            if b and b.status=='closed':
                if b.industry=='bank':
                    from .banking import operate_bank
                    from .business_rules import BusinessRules
                    operate_bank(BusinessRules(self.e),b,date.fromisoformat(self.w.date),dict(teller=0,loan_officer=0),0,False)
                    deposits=max(0,-accounts.get('liability:customer_deposits',0));refund=min(deposits,self.w.cash(entity))
                    if refund:self.e.post(entity,'bank-winddown:'+self.w.date,'Return protected deposits during bank wind-down',{'asset:cash':-refund,'liability:customer_deposits':refund})
                from .customer_collections import CustomerCollections
                CustomerCollections(self.e).collect(b)
                owed=-accounts.get('liability:payroll',0);paid=min(max(0,owed),self.w.cash(entity))
                if paid:self.e.post(entity,'closed-payroll:'+self.w.date,'Settle earned wages after closure',{'asset:cash':-paid,'liability:payroll':paid})
            overdue=[r for r in self.obligations(entity) if r['due']<self.w.date and r['remaining']>0]
            record=self.s.setdefault('distress',{}).setdefault(entity,dict(phase='healthy',history=[]))
            record.setdefault('history',[])
            amount=sum(r['remaining'] for r in overdue)
            age=max(((date.fromisoformat(self.w.date)-date.fromisoformat(r['due'])).days for r in overdue),default=0)
            phase='closed' if b and b.status=='closed' else 'critical' if age>=30 else 'impaired' if age>=14 else 'warning' if age else 'healthy'
            if phase!=record['phase']:
                record['history'].append(dict(date=self.w.date,phase=phase,overdue=amount))
                self.e.event('Financial recovery' if phase=='healthy' else 'Financial distress',
                    (b.name if b else entity)+f': {phase}; ${amount/100:,.2f} overdue, oldest {age} days. Fund, collect, negotiate, reduce operations, sell assets or close.',phase!='healthy',financial_amount=amount)
            record.update(phase=phase,overdue=amount,age=age)
            if b and phase in ('impaired','critical'):
                b.reputation=max(5,b.reputation-1)
            if b and age>=60 and b.status!='closed':self.close(b,'Obligations remained overdue for 60 days.')
            if entity in ('personal','company') and age>=90:
                self.s['campaign_outcome']=dict(status='insolvent',entity=entity,date=self.w.date,overdue=amount,
                    reason='Parent obligations remained unpaid through the 90-day recovery window.')
                self.e.event('Campaign insolvency',self.s['campaign_outcome']['reason']+' The campaign has ended; reports remain available.',True)

    def capacity(self,b):
        return {'impaired':75,'critical':40,'closed':0}.get(self.s.get('distress',{}).get(b.id,{}).get('phase'),100)

    def action(self,action,args,source):
        entity=self.require(args.get('entity','personal'))
        if action=='liquidate_assets':
            from .simulation_support import stable_roll
            b=next((b for b in self.w.businesses if b.id==entity and b.status=='closed'),None)
            if not b or sum(self.liquidation_accounts(entity).values())<=0:raise RuleError('Choose a closed operation with remaining equipment, inventory or customer-loan assets.')
            if any(p['entity']==entity and p['status']=='marketing' for p in self.s.get('asset_liquidations',[])):raise RuleError('An asset sale is already being marketed.')
            self.e.post(entity,source,'Asset liquidation marketing',{'asset:cash':-25000,'expense:liquidation_marketing':25000})
            pid=self.uid('liquidation');percent=60+stable_roll(self.w,pid+':price',26)
            self.s.setdefault('asset_liquidations',[]).append(dict(id=pid,entity=entity,status='marketing',created=self.w.date,due=(date.fromisoformat(self.w.date)+timedelta(days=14)).isoformat(),percent=percent))
            return f'Assets marketed for {percent}% of their closing book value. A buyer can withdraw; no proceeds arrive before the 14-day closing. Property and internal loans remain separate assets.'
        if action=='close_operation':
            b=next((b for b in self.w.businesses if b.id==entity and b.owner),None)
            if not b:raise RuleError('Choose an owned operating business.')
            self.close(b,'Owner chose an orderly closure.');return 'Operations closed. Remaining assets and obligations are retained.'
        if action=='settle_obligations':
            # Contract-specific counterparties settle through their existing rules.
            for key in ('liability:payroll','liability:payable','liability:income_tax','liability:sales_tax'):
                amount=min(max(0,-self.w.accounts[entity].get(key,0)),self.w.cash(entity))
                if amount:self.e.post(entity,source+':'+key,'Settle recorded obligation',{'asset:cash':-amount,key:amount})
            return 'Available cash applied to payroll, suppliers and taxes. Rent and loan counterparties settle on their normal cycle.'
        if action=='write_off_invoice':
            b=next((b for b in self.w.businesses if b.id==entity),None)
            invoice=next((r for r in b.receivables if r['id']==args.get('invoice_id') and (r.get('defaulted') or r.get('overdue_since') or r['due']<self.w.date)),None) if b else None
            if not invoice:raise RuleError('Choose an overdue customer invoice.')
            from .customer_collections import CustomerCollections, busy
            if busy(self.w,b.id,invoice):raise RuleError('Recovery is in progress. Wait for the result or cancel unfinished legal work before writing off this invoice.')
            amount=invoice['amount']
            self.e.post(entity,source,'Write off documented uncollectible customer invoice',{'asset:receivable':-amount,'expense:bad_debt':amount})
            invoice['amount']=0
            CustomerCollections(self.e).record(b,invoice,'write-off','Remaining balance written off; no cash received',loss=amount)
            b.receivables.remove(invoice)
            return 'The unpaid invoice was recognized as a loss. No cash was received.'
        if action=='negotiate_terms':
            lots=self.s.get('obligation_lots',{}).get(entity,{}).get('liability:payable',[])
            eligible=[r for r in lots if not r.get('negotiated')]
            if not eligible:raise RuleError('No supplier obligations are available for another extension.')
            # Existing supplier amounts remain owed. Refusal is stable, not rerolled.
            from .simulation_support import stable_roll
            accepted=stable_roll(self.w,'terms:'+entity+':'+eligible[0]['source'],100)<60
            for r in eligible:
                r['negotiated']=True
                if accepted:r['due']=(date.fromisoformat(self.w.date)+timedelta(days=21)).isoformat()
            return 'Supplier accepted a 21-day extension; the full debt remains owed.' if accepted else 'Supplier refused new terms. No debt was forgiven.'
        raise RuleError('Unknown recovery action.')

    def validate(self):
        for entity,accounts in self.s.get('obligation_lots',{}).items():
            for key,lots in accounts.items():
                if sum(r['remaining'] for r in lots)!=max(0,-self.w.accounts[entity].get(key,0)):
                    raise RuleError('Dated obligations do not reconcile to their liability account.')
