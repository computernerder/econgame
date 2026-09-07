"""Fictional financing, debt service, tax accruals and qualified lawful credits."""
from __future__ import annotations
import calendar
from datetime import date,timedelta
from .campaign import Campaign,integer,flag
from .domain import GAME_RULES,RuleError,calendar_target
from .business_rules import BusinessRules


def debt_accounts(loan):
    lender=loan.get('lender')
    return (('liability:internal_loan:'+lender,'liability:internal_interest:'+lender) if lender else
            ('liability:loan:'+loan['id'],'liability:interest:'+loan['id']))


class Finance(Campaign):
    def release_guarantee(self,loan):
        guarantor=loan.get('guarantor');borrower=loan['entity']
        if not guarantor:return
        claim=loan.get('guarantee_claim',0)
        release=min(max(0,claim-loan.get('arrears',0)),max(0,-self.w.accounts[guarantor].get('liability:intercompany:'+borrower,0)))
        if release:
            source='guarantee-release:'+loan['id']+':'+self.w.date
            self.e.post(guarantor,source,'Rescind guarantee call covered by borrower repayment',{'liability:intercompany:'+borrower:release,'expense:internal_guarantee:'+borrower:-release})
            self.e.post(borrower,source,'Guarantee claim reduced after debt recovery',{'asset:intercompany:'+guarantor:-release,'income:internal_guarantee:'+guarantor:release})
        loan['guarantee_claim']=max(0,claim-release)

    def owned_banks(self,entity):
        return [b for b in self.w.businesses if b.industry=='bank' and b.id!=entity and b.status=='operating' and self.controlled(b.id)]

    def lender_payment(self,loan,source,principal,interest):
        if not loan.get('lender') or not principal+interest:return
        borrower=loan['entity']
        self.e.post(loan['lender'],source,'Borrower principal and interest received',{'asset:cash':principal+interest,'asset:internal_loan:'+borrower:-principal,'asset:internal_interest:'+borrower:-interest})

    def action(self,action,args,command_id):
        entity=self.require(args.get('entity','personal'))
        if action=='borrow':
            amount=integer(args.get('amount',0),10000,1000000000);months=integer(args.get('months',60),6,360)
            collateral=args.get('property_id') or None;guarantor=args.get('guarantor') or None
            location=self.s.get('operating_locations',{}).get(entity)
            if location:guarantor=location['company']
            if guarantor:
                self.require(guarantor)
                if guarantor!=self.parent(entity):raise RuleError('Only the direct owner may explicitly guarantee this loan.')
            lender=args.get('lender') or None
            bank=next((b for b in self.owned_banks(entity) if b.id==lender),None)
            if lender and not bank:raise RuleError('Choose an operating bank you own, different from the borrower.')
            existing=sum(l['principal'] for l in self.s['loans'] if l['entity']==entity and l['status']=='active')
            accounts=self.w.accounts[entity]
            equity=sum(v for k,v in accounts.items() if k.startswith(('asset:','liability:')))
            limit=max(1000000,equity*(75 if bank else 50)//100)-existing
            if collateral:
                p=next((p for p in self.w.properties if p.id==collateral and p.owner==entity),None)
                if not p:raise RuleError('Collateral must be a property owned by the borrower.')
                if any(l['status']=='active' and l.get('property_id')==collateral for l in self.s['loans']):raise RuleError('That building is already pledged.')
                limit=max(limit,p.value*(80 if bank else 70)//100-existing)
            if bank:
                from .banking import bank_view
                limit=min(limit,bank_view(self.w,bank)['lendable'])
            if amount>max(0,limit):raise RuleError(f'The lender offers at most ${max(0,limit)/100:,.2f} against current resources and debt.')
            rate=max(100,self.s['interest_bps']+(0 if collateral else 200)-(200 if bank else 0))
            lid=self.uid('loan');due=calendar_target(date.fromisoformat(self.w.date),'month').isoformat()
            loan=dict(id=lid,entity=entity,original=amount,principal=amount,months=months,remaining=months,rate_bps=rate,interest_due=0,interest_remainder=0,next_due=due,property_id=collateral,guarantor=guarantor,status='active',missed=0,created=self.w.date,history=[],covenant_ltv=85,lender=lender)
            self.s['loans'].append(loan)
            principal_key,_=debt_accounts(loan)
            self.e.post(entity,command_id,'Loan proceeds; not income',{'asset:cash':amount,principal_key:-amount})
            if bank:self.e.post(bank.id,command_id,'Group loan funded',{'asset:cash':-amount,'asset:internal_loan:'+entity:amount})
            return ('Owner-bank benefit: 2 percentage points off standard APR, with enhanced approval limits. ' if bank else '')+f'Borrowed ${amount/100:,.2f} at {rate/100:.2f}% APR for {months} months. First principal and interest payment is due {due}.'
        loan=next((l for l in self.s['loans'] if l['id']==args.get('loan_id') and l['entity']==entity and l['status']=='active'),None)
        if action in ('repay_loan','restructure_loan'):
            if not loan:raise RuleError('Choose an active loan for this borrower.')
            principal_key,interest_key=debt_accounts(loan)
            if action=='repay_loan':
                amount=integer(args.get('amount',0),1,loan['principal']+loan['interest_due'])
                interest=min(amount,loan['interest_due']);principal=amount-interest
                self.e.post(entity,command_id,'Early loan payment',{'asset:cash':-amount,interest_key:interest,principal_key:principal})
                self.lender_payment(loan,command_id,principal,interest)
                loan['principal']-=principal;loan['interest_due']-=interest
                loan['arrears']=max(0,loan.get('arrears',0)-amount)
                loan['overdue_principal']=max(0,loan.get('overdue_principal',0)-principal)
                self.release_guarantee(loan)
                loan['history'].append(dict(date=self.w.date,due=amount,paid=amount,principal=principal,interest=interest,kind='early'))
                if not loan['principal'] and not loan['interest_due']:loan['status']='repaid'
                return 'Payment applied to accrued interest and then principal. Repaying principal is not an expense.'
            if loan.get('restructured'):raise RuleError('This loan has already used its forgiving restructuring option.')
            fee=max(10000,loan['principal']//100)
            self.e.post(entity,command_id,'Loan restructuring fee',{'asset:cash':-fee,('expense:internal_fee:'+loan['lender'] if loan.get('lender') else 'expense:finance_fees'):fee})
            if loan.get('lender'):self.e.post(loan['lender'],command_id,'Loan restructuring fee received',{'asset:cash':fee,'income:internal_fee:'+entity:-fee})
            loan['remaining']+=12;loan['rate_bps']+=100;loan['missed']=0;loan['restructured']=True;loan['next_due']=calendar_target(date.fromisoformat(self.w.date),'month').isoformat()
            loan['arrears']=0;loan.pop('overdue_since',None)
            loan['overdue_principal']=0
            self.release_guarantee(loan)
            return 'Loan restructured once: 12 additional installments and a 1-point APR increase. Accrued interest is still owed.'
        if action=='tax_plan':
            if entity in ('personal','company'):raise RuleError('Select an operating company for a research/documentation program.')
            rules=BusinessRules(self.e)
            staff=rules.staff(entity)
            qualified=any(rules.position(e.position_id).role in ('accounting','legal') for e in staff)
            qualified=qualified or any(a['active'] and a['target']==entity and a['role'] in ('accounting','legal') for a in self.s['assignments'])
            if not qualified:raise RuleError('A qualified accounting/legal employee or shared assignment is required.')
            amount=integer(args.get('amount',500000),100000,5000000)
            self.e.post(entity,command_id,'Documented research and regional development',{'asset:cash':-amount,'expense:qualified_research':amount})
            self.s['research'].append(dict(id=self.uid('research'),entity=entity,amount=amount,due=(date.fromisoformat(self.w.date)+timedelta(days=90)).isoformat(),status='active',credit=0,used=0))
            return 'Research funded. A fictional 10% credit becomes eligible after 90 days, capped at 25% of income tax; spending is never refunded in full.'
        if action=='file_taxes':
            liability=-self.w.accounts[entity].get('liability:income_tax',0)
            if liability<=0:raise RuleError('No accrued income tax is currently payable.')
            cost=10000
            self.e.post(entity,command_id,'File and pay accrued fictional income tax',{'asset:cash':-liability-cost,'liability:income_tax':liability,'expense:tax_filing':cost})
            self.s['tax_returns'].append(dict(id=self.uid('return'),entity=entity,date=self.w.date,paid=liability,filing_cost=cost,status='filed'))
            return 'Accrued income tax paid and the filing recorded. No past payroll or revenue was changed.'
        raise RuleError('Unknown financing action.')

    def end_day(self,today):
        stop=False
        for loan in self.s['loans']:
            if loan['status']!='active':continue
            entity=loan['entity'];lid=loan['id'];days=366 if calendar.isleap(today.year) else 365
            principal_key,interest_key=debt_accounts(loan)
            interest,remainder=divmod(loan['principal']*loan['rate_bps']+loan['interest_remainder'],10000*days)
            loan['interest_remainder']=remainder;loan['interest_due']+=interest
            if interest:self.e.post(entity,f'interest:{lid}:{self.w.date}','Loan interest accrued',{('expense:internal_interest:'+loan['lender'] if loan.get('lender') else 'expense:interest'):interest,interest_key:-interest})
            if interest and loan.get('property_id'):
                self.s.setdefault('property_cost_totals',{}).setdefault(loan['property_id'],dict(holding=0,interest=0,repairs=0))['interest']+=interest
            if interest and loan.get('lender'):self.e.post(loan['lender'],f'interest:{lid}:{self.w.date}','Group loan interest earned',{'asset:internal_interest:'+entity:interest,'income:internal_interest:'+entity:-interest})
            if loan['next_due']>self.w.date:continue
            installment=(loan['principal']+loan['remaining']-1)//max(1,loan['remaining'])
            principal=min(loan['principal'],installment+loan.get('overdue_principal',0))
            due=principal+loan['interest_due'];available=self.w.cash(entity)
            if loan['guarantor'] and available<due:
                guarantor=loan['guarantor'];support=min(due-available,self.w.cash(guarantor))
                if support:
                    source=f'guarantee:{lid}:{self.w.date}'
                    existing=min(support,loan.get('guarantee_claim',0),max(0,-self.w.accounts[guarantor].get('liability:intercompany:'+entity,0)))
                    self.e.post(guarantor,source,'Explicit loan guarantee called',{'asset:cash':-support,'liability:intercompany:'+entity:existing,'expense:internal_guarantee:'+entity:support-existing})
                    self.e.post(entity,source,'Guarantee support received',{'asset:cash':support,'asset:intercompany:'+guarantor:-existing,'income:internal_guarantee:'+guarantor:-(support-existing)});available+=support
                    loan['guarantee_claim']=max(0,loan.get('guarantee_claim',0)-existing)
            paid=min(due,available);interest_paid=min(paid,loan['interest_due']);principal_paid=paid-interest_paid
            if paid:self.e.post(entity,f'debt-payment:{lid}:{self.w.date}','Scheduled principal and interest payment',{'asset:cash':-paid,interest_key:interest_paid,principal_key:principal_paid})
            self.lender_payment(loan,f'debt-payment:{lid}:{self.w.date}',principal_paid,interest_paid)
            loan['principal']-=principal_paid;loan['interest_due']-=interest_paid;loan['remaining']=max(1,loan['remaining']-1)
            loan['overdue_principal']=max(0,principal-principal_paid)
            loan['arrears']=loan['overdue_principal']+loan['interest_due']
            loan['history'].append(dict(date=self.w.date,due=due,paid=paid,principal=principal_paid,interest=interest_paid));loan['history']=loan['history'][-120:]
            loan['next_due']=calendar_target(today,'month').isoformat()
            if paid<due:
                loan['missed']+=1
                loan.setdefault('overdue_since',self.w.date)
                if loan.get('guarantor'):
                    guarantor=loan['guarantor']
                    existing=min(loan.get('guarantee_claim',0),max(0,-self.w.accounts[guarantor].get('liability:intercompany:'+entity,0)))
                    unpaid=max(0,loan['arrears']-existing)
                    source=f'guarantee-obligation:{lid}:{self.w.date}'
                    if unpaid:
                        self.e.post(guarantor,source,'Unfunded explicit guarantee called',{'expense:internal_guarantee:'+entity:unpaid,'liability:intercompany:'+entity:-unpaid})
                        self.e.post(entity,source,'Called guarantee receivable; not cash',{'asset:intercompany:'+guarantor:unpaid,'income:internal_guarantee:'+guarantor:-unpaid})
                    loan['guarantee_claim']=existing+unpaid
                if self.controlled(entity):self.decision(f'loan-shortfall:{lid}:{self.w.date}','Loan payment shortfall',f'Payment due ${due/100:,.2f}; paid ${paid/100:,.2f}. Add funds, sell collateral after repayment, or use the one-time restructuring option.',entity,financial_amount=due-paid);stop=True
            if not loan['principal'] and not loan['interest_due']:loan['status']='repaid'
            self.release_guarantee(loan)
            if not loan.get('arrears',0):loan.pop('overdue_since',None)
            if loan['property_id']:
                p=next(p for p in self.w.properties if p.id==loan['property_id'])
                if loan['principal']*100>p.value*loan['covenant_ltv'] and self.controlled(entity):self.decision('covenant:'+lid,'Loan collateral covenant',f'{p.name} no longer covers the agreed loan-to-value cushion. Pay down debt or improve the property.',entity);stop=True
        for project in self.s['research']:
            if project['status']=='active' and project['due']<=self.w.date:project['status']='eligible';project['credit']=project['amount']*GAME_RULES['tax']['research_credit_percent']//100
        self.monthly_taxes(today)
        return stop

    def monthly_taxes(self,today):
        if today.day!=calendar.monthrange(today.year,today.month)[1]:return
        tax=GAME_RULES['tax']
        locations=self.s.get('operating_locations',{})
        for entity,accounts in sorted(self.w.accounts.items(),key=lambda item:item[0] not in locations):
            from .holding_company import exists
            if entity=='company' and not exists(self.w):continue
            if entity not in self.s['period_bases']:self.s['period_bases'][entity]={'year':today.year,'profit':0,'tax':0,'paid':0}
            base=self.s['period_bases'][entity]
            depreciation=accounts.get('asset:equipment',0)//tax['equipment_life_months']
            remaining=accounts.get('asset:equipment',0)+accounts.get('asset:equipment_accumulated',0)
            depreciation=min(max(0,remaining),depreciation)
            if depreciation:self.e.post(entity,f'depreciation:{entity}:{self.w.date}','Monthly straight-line equipment depreciation',{'expense:depreciation':depreciation,'asset:equipment_accumulated':-depreciation})
            profit=-sum(v for k,v in accounts.items() if k.startswith(('income:','expense:')) and k not in ('income:dividends','expense:income_tax'))
            members=[entity]+[uid for uid,record in locations.items() if record['company']==entity]
            if len(members)>1:
                from .business_views import group_profit
                profit=group_profit(self.w,members)+sum(self.w.accounts[uid].get('expense:income_tax',0) for uid in members)
            taxable=0 if entity in locations else profit-base['profit']-self.s['tax_carry'].get(entity,0)
            gross=max(0,taxable)*tax['income_percent']//100
            eligible=[p for p in self.s['research'] if p['entity'] in members and p['status']=='eligible']
            available=sum(p['credit'] for p in eligible)
            credit=min(available,gross*tax['credit_cap_percent']//100);assessed=gross-credit
            delta=assessed-base['tax']
            if delta:self.e.post(entity,f'income-tax:{entity}:{self.w.date}','Accrue fictional income tax net of capped credits',{'expense:income_tax':delta,'liability:income_tax':-delta})
            base['tax']=assessed
            sales=-accounts.get('liability:sales_tax',0)
            if sales:
                paid=min(sales,self.w.cash(entity))
                if paid:self.e.post(entity,f'sales-tax-pay:{entity}:{self.w.date}','Remit collected sales tax',{'asset:cash':-paid,'liability:sales_tax':paid})
            if today.month==12:
                self.s['tax_carry'][entity]=max(0,-taxable)
                remaining_credit=credit
                for p in eligible:
                    used=min(p['credit'],remaining_credit);p['used']+=used;p['credit']-=used;remaining_credit-=used
                self.s['annual'].append(dict(year=today.year,entity=entity,profit=profit-base['profit'],tax=assessed,credit=credit,after_tax=profit-base['profit']-assessed))
                base.update(year=today.year+1,profit=profit,tax=0)
                if self.controlled(entity) and -accounts.get('liability:income_tax',0)>0:self.decision(f'tax-filing:{entity}:{today.year}','Annual tax filing ready',f'{today.year} return is ready. Accrued tax is payable from the Finance screen; unpaid amounts remain obligations.',entity,days=105,financial_amount=-accounts.get('liability:income_tax',0))

    def validate(self):
        expected={}
        def add(entity,key,amount):expected[(entity,key)]=expected.get((entity,key),0)+amount
        for loan in self.s.get('loans',[]):
            principal_key,interest_key=debt_accounts(loan)
            add(loan['entity'],principal_key,-loan['principal'])
            add(loan['entity'],interest_key,-loan['interest_due'])
            if loan.get('lender'):
                add(loan['lender'],'asset:internal_loan:'+loan['entity'],loan['principal'])
                add(loan['lender'],'asset:internal_interest:'+loan['entity'],loan['interest_due'])
        for (entity,key),amount in expected.items():
            if self.w.accounts[entity].get(key,0)!=amount:raise RuleError('Loan balances do not reconcile to the journal.')
