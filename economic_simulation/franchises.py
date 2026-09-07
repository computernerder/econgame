"""Brand contracts and independently financed franchise operators."""
from __future__ import annotations
import copy
from datetime import date,timedelta
from .campaign import Campaign,integer,flag
from .domain import BUSINESS_CONTENT,RuleError,calendar_target
from .business_models import Business,Position,Employment,ROLE_PAY
from .business_rules import BusinessRules


class Franchises(Campaign):
    def action(self,action,args,command_id):
        rules=BusinessRules(self.e)
        if action=='create_brand':
            b=rules.company(args.get('business_id',''))
            if b.industry not in ('retail','restaurant'):raise RuleError('Only proven retail and restaurant formats may franchise in this ruleset.')
            if len(b.history)<84 or sum(d['profit'] for d in b.history[-84:])<=0:raise RuleError('Prove this format with at least 12 weeks of positive combined operating profit first.')
            if any(brand['entity']==b.id for brand in self.s['brands']):raise RuleError('This company already sponsors a brand.')
            name=str(args.get('name',b.name)).strip()
            if not 2<=len(name)<=80:raise RuleError('Use a brand name of 2–80 characters.')
            self.e.post(b.id,command_id,'Brand standards, manuals and training preparation',{'asset:cash':-500000,'expense:brand_development':500000})
            self.s['brands'].append(dict(id=self.uid('brand'),entity=b.id,name=name,industry=b.industry,royalty=integer(args.get('royalty',6),2,10),support_load=0,reputation=b.reputation,created=self.w.date))
            return 'Brand established from a proven format. Independent operators need territory, support capacity and 30 days of preparation.'
        if action=='grant_franchise':
            brand=next((b for b in self.s['brands'] if b['id']==args.get('brand_id')),None)
            if not brand:raise RuleError('Choose an established brand.')
            self.require(brand['entity']);region=args.get('region','Rutland County')
            r=next((r for r in self.s['regions'] if r['id']==region),None)
            if not r:raise RuleError('Choose an available region.')
            if any(f['brand_id']==brand['id'] and f['region']==region and f['status']=='active' for f in self.s['franchises']):raise RuleError('This brand already has an active independent operator in that territory.')
            count=sum(f['brand_id']==brand['id'] and f['status']=='active' for f in self.s['franchises'])
            managers=sum(rules.position(emp.position_id).role=='manager' for emp in rules.staff(brand['entity']))
            if count>=max(0,managers*3):raise RuleError('Each staffed brand manager can support at most three independent operators.')
            pool=r.setdefault('investment_pool',50000000)
            capital=10000000
            if pool<capital:raise RuleError('No additional independent investment capital is available in this region.')
            r['investment_pool']-=capital
            template=copy.deepcopy(next(b for b in BUSINESS_CONTENT['catalog'] if b['industry']==brand['industry']))
            staff=template.pop('staff');template.pop('properties',None)
            bid=f'business-{self.w.next_business_id}';self.w.next_business_id+=1
            template.update(name=brand['name']+' · '+region+' franchise',region=region,owner=None,outside_owner='Independent franchise operator',status='independent',asking=0,cash_at_sale=capital)
            if brand['industry']=='self_storage':template['storage_occupied']=0
            b=Business(id=bid,**template);b.disrupted_until=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat();self.w.businesses.append(b);self.w.accounts[bid]={}
            inventory=b.inventory_units*b.unit_cost
            self.e.post(bid,command_id+':external-capital','Independent operator opening capital',{'asset:cash':capital-b.equipment-inventory,'asset:equipment':b.equipment,'asset:inventory':inventory,'equity:capital':-capital})
            manager=None
            for role,salary,hours in staff:
                person=rules.make_person(role);pos=Position(f'position-new-{self.w.next_position_id}',bid,role,manager);self.w.next_position_id+=1;self.w.positions.append(pos)
                if role=='manager':manager=pos.id
                emp=Employment(f'employment-new-{self.w.next_employment_id}',person.id,pos.id,bid,salary,hours,self.w.date);self.w.next_employment_id+=1;self.w.employments.append(emp)
            fee=1500000;support=2000000
            self.e.post(bid,command_id+':fee','Independent franchise initial fee',{'asset:cash':-fee,'expense:franchise_fee':fee})
            self.e.post(brand['entity'],command_id+':brand-fee','External franchise fee received',{'asset:cash':fee,'income:franchise_fees':-fee})
            self.e.post(brand['entity'],command_id+':setup','Franchise training and launch support',{'asset:cash':-support,'expense:franchise_support':support})
            end=calendar_target(date.fromisoformat(self.w.date),'year').isoformat()
            self.s['franchises'].append(dict(id=self.uid('franchise'),brand_id=brand['id'],issuer=brand['entity'],operator=bid,region=region,royalty=brand['royalty'],staff_access=flag(args.get('staff_access',False)),minimum_quality=50,status='active',created=self.w.date,end_date=end,fee=fee,history=[],supplier='Approved regional supplier',last_royalty=0))
            return 'Independent franchise funded from its own finite capital. Net launch support costs your brand $5,000; royalties begin with actual trading after preparation.'
        if action=='join_franchise':
            b=rules.company(args.get('business_id',''))
            if b.industry not in ('retail','restaurant'):raise RuleError('This franchise format supports retail or restaurants.')
            if any(f['operator']==b.id and f['status']=='active' for f in self.s['franchises']):raise RuleError('This company already has a franchise agreement.')
            fee=2000000;self.e.post(b.id,command_id,'External brand franchise entry fee',{'asset:cash':-fee,'expense:franchise_fee':fee})
            self.s['franchises'].append(dict(id=self.uid('franchise'),brand_id='external-established-brand',issuer='external',operator=b.id,region=b.region,royalty=6,staff_access=True,minimum_quality=50,status='active',created=self.w.date,end_date=calendar_target(date.fromisoformat(self.w.date),'year').isoformat(),fee=fee,history=[],supplier='Approved regional supplier',last_royalty=0))
            return 'Joined an established external brand for $20,000 and 6% of actual sales. Standards restrict prices to 90–110%; renewal is annual.'
        f=next((f for f in self.s['franchises'] if f['id']==args.get('franchise_id') and f['status']=='active'),None)
        if not f:raise RuleError('Choose an active franchise agreement.')
        entity=f['operator'] if f['issuer']=='external' else f['issuer'];self.require(entity)
        if action=='franchise_audit':
            self.e.post(entity,command_id,'Franchise quality audit',{'asset:cash':-25000,'expense:franchise_audit':25000})
            b=rules.company(f['operator'],owned=False);staff=rules.staff(b.id)
            quality=sum(rules.person(emp.person_id).morale for emp in staff)//max(1,len(staff))
            f['history'].append(dict(date=self.w.date,kind='quality_audit',quality=quality,status='Meets standard' if quality>=f['minimum_quality'] else 'Needs improvement'))
            if quality<f['minimum_quality']:b.reputation=max(0,b.reputation-3)
            return f'Audit recorded quality {quality}/100 against the {f["minimum_quality"]} standard. Staffing and workplace conditions determine the result.'
        if action=='renew_franchise':
            fee=300000;self.e.post(entity,command_id,'Franchise renewal and documentation',{'asset:cash':-fee,'expense:franchise_renewal':fee})
            f['end_date']=calendar_target(date.fromisoformat(max(f['end_date'],self.w.date)),'year').isoformat()
            return 'Agreement renewed for one year. Existing staff and ownership are unchanged.'
        if action=='end_franchise':
            f['status']='terminated';f['end_date']=self.w.date
            for a in self.s['assignments']:
                if a['target']==f['operator'] and not self.controlled(a['target']):a['active']=False
            return 'Brand agreement ended. The operating company remains independently owned unless it was already your subsidiary.'
        raise RuleError('Unknown franchise action.')

    def tick(self,today):
        for f in self.s['franchises']:
            if f['status']!='active':continue
            b=BusinessRules(self.e).company(f['operator'],owned=False)
            if f['end_date']<=self.w.date:
                f['status']='expired';self.e.event('Franchise agreement expired',b.name+' is no longer affiliated. Operator ownership and employment records remain.',True);continue
            sales=sum(v for k,v in b.last_day.get('streams',{}).items() if k in ('retail_sales','meal_sales')) if b.last_day.get('date')==self.w.date else 0
            due=sales*f['royalty']//100;paid=min(due,self.w.cash(b.id));f['last_royalty']=paid
            if paid:
                internal=f['issuer']!='external' and self.controlled(f['issuer']) and self.controlled(b.id)
                expense='expense:internal_franchise:'+f['issuer'] if internal else 'expense:royalties'
                self.e.post(b.id,f'royalty:{f["id"]}:{self.w.date}','Franchise royalty on fulfilled sales',{'asset:cash':-paid,expense:paid})
                if f['issuer']!='external':self.e.post(f['issuer'],f'royalty:{f["id"]}:{self.w.date}','Franchise royalty received',{'asset:cash':paid,('income:internal_franchise:'+b.id if internal else 'income:royalties'):-paid})
            if due>paid:self.decision('royalty-shortfall:'+f['id']+':'+self.w.date,'Franchise royalty shortfall',b.name+' has insufficient cash for this royalty. Review the operation and contract.',f['issuer'] if f['issuer']!='external' else b.id,financial_amount=due-paid)
            if today.day==1:f['history'].append(dict(date=self.w.date,kind='monthly_review',cash=self.w.cash(b.id),reputation=b.reputation))
