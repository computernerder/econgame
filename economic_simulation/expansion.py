"""Company formation, phased openings, investment upgrades and divestment."""
from __future__ import annotations
import copy
from datetime import date,timedelta
from .campaign import Campaign,integer,flag
from .domain import BUSINESS_CONTENT,GAME_RULES,RuleError,calendar_target
from .business_models import Business,Position,ROLE_PAY,INDUSTRY_ROLES,investment_account
from .business_rules import BusinessRules
from .industries import PROJECTS
from .business_views import descendants


def opening_staff(world, business):
    """Accepted hires cover recruitment, but only active staff permit opening."""
    from .business_models import OPENING_ROLES
    positions={p.id:p for p in world.positions}
    staff=[e for e in world.employments if e.employer==business.id and e.status in ('active','joining')]
    active={positions[e.position_id].role for e in staff if e.status=='active'}
    promised={positions[e.position_id].role for e in staff if e.status=='joining' and e.start_date>=world.date}
    required=set(OPENING_ROLES[business.industry])
    pending=[e.start_date for e in staff if e.status=='joining' and positions[e.position_id].role in required-active]
    return dict(missing=required-active-promised, waiting=required-active, starts=max(pending,default=''))


class Expansion(Campaign):
    def __init__(self,engine):super().__init__(engine);self.rules=BusinessRules(engine)

    def seed_group(self):
        if any(b.market_parent for b in self.w.businesses):return
        self.rules.add_business(5,group=True);root=self.w.businesses[-1]
        root.description='An established group with a grocer, retail subsidiary, engineering subsidiary, staffed central leadership and owned headquarters premises. The whole ownership tree transfers together.'
        for index in (0,2):
            self.rules.add_business(index);child=self.w.businesses[-1];child.market_parent=root.id;root.asking+=child.asking
        self.s['offices'].append(dict(id=self.uid('office'),business_id=root.id,property_id=root.id+'-property-1',desks=30,active=False,date=self.w.date))

    def opening_quote(self,industry,reserve=None):
        if industry not in GAME_RULES['startup']:raise RuleError('Choose a supported business industry.')
        q=dict(GAME_RULES['startup'][industry]);q['reserve']=integer(reserve if reserve is not None else q['reserve'],q['reserve']//2,1000000000)
        q['total']=sum(q[k] for k in ('deposit','fitout','inventory','expense','reserve'))
        return q

    def action(self,action,args,command_id):
        if action=='start_business':
            parent=self.require(args.get('entity','personal'));industry=args.get('industry','retail');q=self.opening_quote(industry,args.get('reserve'))
            name=str(args.get('name','')).strip();region=args.get('region','Rutland County')
            if not 2<=len(name)<=80:raise RuleError('Use a business name of 2–80 characters.')
            if region not in {r['id'] for r in self.s['regions']}:raise RuleError('Choose an available region.')
            if industry=='office':spec=dict(industry=industry,region=region,description='A staffed central office offering shared services.',asking=0,cash_at_sale=0,equipment=0,monthly_overhead=60000,monthly_lease=120000)
            else:
                spec=copy.deepcopy(next(s for s in BUSINESS_CONTENT['catalog'] if s['industry']==industry));spec.pop('staff');spec.pop('properties',None)
            spec.update(name=name,region=region,asking=0,cash_at_sale=0,equipment=q['fitout'],owner=parent,status='developing',acquired_on=self.w.date,inventory_units=0)
            bid=f'business-{self.w.next_business_id}';self.w.next_business_id+=1;b=Business(id=bid,**spec)
            b.inventory_units=q['inventory']//b.unit_cost if b.unit_cost else 0
            if industry=='self_storage':b.storage_occupied=0
            if industry=='rental':b.monthly_lease=0;b.monthly_overhead=10000
            if industry in PROJECTS:b.project_active=False
            self.w.businesses.append(b);self.w.accounts[bid]={}
            self.e.post(parent,command_id+':fund','Opening capital: '+name,{'asset:cash':-q['total'],investment_account(bid):q['total']})
            self.e.post(bid,command_id+':capital','Startup capital received',{'asset:cash':q['total'],'equity:capital':-q['total']})
            stock=b.inventory_units*b.unit_cost
            self.e.post(bid,command_id+':setup','Deposit, fit-out, inventory and pre-opening costs',{'asset:cash':-q['deposit']-q['fitout']-stock-q['expense'],'asset:deposit':q['deposit'],'asset:equipment':q['fitout'],'asset:inventory':stock,'expense:startup':q['expense']})
            roles=INDUSTRY_ROLES[industry][:3] if industry!='rental' else ['property_manager','maintenance']
            manager=None
            for role in roles:
                pos=Position(f'position-new-{self.w.next_position_id}',bid,role,manager);self.w.next_position_id+=1;self.w.positions.append(pos)
                if role=='manager':manager=pos.id
            delay=7 if self.roll('projects',1,100)<=10 else 0
            b.opening_on=(date.fromisoformat(self.w.date)+timedelta(days=q['days']+delay)).isoformat()
            self.s['plans'].append(dict(id=self.uid('opening'),kind='opening',entity=bid,created=self.w.date,due=b.opening_on,status='active',phase='Permits and design',base_days=q['days'],delay=delay,budget=q))
            self.s['ownership_history'].append(dict(date=self.w.date,entity=bid,from_owner=None,to_owner=parent,kind='formation'))
            self.e.event('Business opening funded',f'{name} targets {b.opening_on}. Recruit into its vacancies; rent and any payroll consume its reserve before revenue.',True)
            return f'{name} funded for ${q["total"]/100:,.2f}. Earliest opening {b.opening_on}; hire required staff before that date.'
        b=self.rules.company(args.get('business_id',''))
        if action=='due_diligence':
            raise RuleError('Choose a listed acquisition target from the opportunities screen.')
        if action=='upgrade_business':
            if b.capacity_percent>=200:raise RuleError('This location has reached its practical expansion capacity. Open another operation.')
            if any(p['kind']=='upgrade' and p.get('entity')==b.id and p['status']=='active' for p in self.s['plans']):raise RuleError('This operation already has an expansion underway.')
            cost=max(500000,b.equipment//4)
            self.e.post(b.id,command_id,'Operating equipment expansion',{'asset:cash':-cost,'asset:equipment':cost});b.equipment+=cost
            self.s['plans'].append(dict(id=self.uid('upgrade'),kind='upgrade',entity=b.id,created=self.w.date,due=(date.fromisoformat(self.w.date)+timedelta(days=21)).isoformat(),status='active',cost=cost))
            return f'Equipment expansion funded for ${cost/100:,.2f}. Capacity improves by 20% after 21 days; demand and staffing still constrain output.'
        if action=='integration':
            mode=args.get('mode','autonomy')
            if mode not in ('autonomy','shared_services','rebrand','leadership_review'):raise RuleError('Choose a supported integration plan.')
            if b.integration.get('status')=='active':raise RuleError('Complete the current integration first.')
            cost={'autonomy':0,'shared_services':200000,'rebrand':350000,'leadership_review':100000}[mode]
            if cost:self.e.post(b.id,command_id,'Acquisition integration program',{'asset:cash':-cost,'expense:integration':cost})
            b.integration=dict(mode=mode,status='active',due=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat(),cost=cost)
            return 'Integration plan scheduled for 30 days. Employees keep their identities; shared work still requires explicit agreements and assignments.'
        if action=='sell_business':
            if b.status=='developing':raise RuleError('Use Cancel opening for a business still in development.')
            if any(p['kind']=='business_sale' and p['entity']==b.id and p['status']=='active' for p in self.s['plans']):raise RuleError('A sale is already agreed.')
            entities=descendants(self.w,b.id)
            if any(a['active'] and (a['source'] in entities or a['target'] in entities) for a in self.s['assignments']):raise RuleError('End shared assignments involving this group before selling.')
            if any(loan['status']=='active' and loan.get('guarantor') in entities and loan['entity'] not in entities for loan in self.s['loans']):raise RuleError('Release cross-group loan guarantees before selling.')
            quote=self.sale_quote(b)
            self.s['plans'].append(dict(id=self.uid('sale'),kind='business_sale',entity=b.id,entities=entities,due=(date.fromisoformat(self.w.date)+timedelta(days=14)).isoformat(),status='active',price=quote,owner=b.owner))
            return f'Whole-company sale agreed for ${quote/100:,.2f} before a 2% fee, closing in 14 days. Included subsidiaries, assets and employees transfer together.'
        if action=='cancel_opening':
            if b.status!='developing':raise RuleError('Only a developing business can cancel its opening plan.')
            if any(p.owner==b.id for p in self.w.properties) or any(x.owner==b.id for x in self.w.businesses):raise RuleError('Dispose of properties and subsidiaries before cancelling this startup.')
            if any(l['entity']==b.id and l['status']=='active' for l in self.s['loans']):raise RuleError('Repay startup borrowing before cancellation.')
            accounts=self.w.accounts[b.id];equipment=accounts.get('asset:equipment',0);inventory=accounts.get('asset:inventory',0);deposit=accounts.get('asset:deposit',0)
            proceeds=equipment*70//100+inventory*80//100+deposit
            if proceeds:self.e.post(b.id,command_id+':liquidate','Cancelled opening recoveries',{'asset:equipment':-equipment,'asset:inventory':-inventory,'asset:deposit':-deposit,'asset:cash':proceeds,'expense:abandoned_opening':equipment+inventory+deposit-proceeds})
            b.equipment=0;b.inventory_units=0
            for emp in self.rules.staff(b.id):self.rules.action('end_employment',{'employment_id':emp.id},command_id+':'+emp.id)
            for emp in self.w.employments:
                if emp.employer==b.id and emp.status=='joining':emp.status='ended';emp.end_date=self.w.date;self.rules.person(emp.person_id).candidate=True
            owed=-sum(v for k,v in accounts.items() if k.startswith('liability:'))
            if owed>self.w.cash(b.id):raise RuleError('Fund the remaining obligations before cancelling; costs already incurred remain payable.')
            for key,value in list(accounts.items()):
                if key.startswith('liability:') and value<0:self.e.post(b.id,command_id+':settle:'+key,'Settle startup obligation',{'asset:cash':value,key:-value})
            cash=self.w.cash(b.id);investment=self.w.accounts[b.owner].get(investment_account(b.id),0)
            self.e.post(b.id,command_id+':close','Return remaining startup cash',{'asset:cash':-cash,'equity:distributions':cash})
            self.e.post(b.owner,command_id+':owner','Cancelled startup investment',{'asset:cash':cash,investment_account(b.id):-investment,'expense:investment_loss':investment-cash})
            b.owner=None;b.outside_owner='Closed';b.status='closed'
            for plan in self.s['plans']:
                if plan.get('entity')==b.id and plan['status']=='active':plan['status']='cancelled'
            return 'Opening cancelled. Recoveries returned to the owner after obligations; sunk losses remain in the journal.'
        raise RuleError('Unknown business development action.')

    def sale_quote(self,b):
        entities=descendants(self.w,b.id)
        net=sum(v for entity in entities for k,v in self.w.accounts[entity].items() if k.startswith(('asset:','liability:')) and not k.startswith('asset:investment'))
        earnings=sum(day.get('profit',0) for day in b.history[-30:])
        premium=max(0,min(b.asking or net,max(0,earnings)*12))
        return max(100000,net*90//100+premium)

    def diligence(self,args,command_id):
        b=self.rules.company(args.get('business_id',''),owned=False);buyer=self.require(args.get('entity','personal'))
        if b.status!='market':raise RuleError('Choose an available acquisition target.')
        self.e.post(buyer,command_id,'Acquisition due diligence',{'asset:cash':-50000,'expense:due_diligence':50000})
        report=dict(id=self.uid('diligence'),kind='diligence',entity=b.id,status='complete',date=self.w.date,due=self.w.date,report=f'{b.name}: disclosed debt $0; {len(self.rules.quote(b.id)["staff"])} staff; working cash ${b.cash_at_sale/100:,.2f}; management reputation {b.reputation}/100. No undisclosed liabilities were found. Buyer still bears demand, staffing and integration risk.')
        self.s['plans'].append(report)
        return report['report']

    def start_day(self):
        stop=False;today=date.fromisoformat(self.w.date)
        for plan in self.s['plans']:
            if plan['status']!='active' or plan['kind'] not in ('opening','upgrade','business_sale'):continue
            b=self.rules.company(plan['entity'])
            if plan['kind']=='opening':
                elapsed=(today-date.fromisoformat(plan['created'])).days
                plan['phase']='Permits and design' if elapsed<7 else 'Fit-out and supplier preparation' if self.w.date<plan['due'] else 'Staffing and commissioning'
            if plan['due']>self.w.date:continue
            if plan['kind']=='opening':
                staffing=opening_staff(self.w,b)
                decision=next((d for d in self.s['decisions'] if d['source']=='opening-staff:'+b.id),None)
                if staffing['missing']:
                    # A genuinely new gap can reopen a previously covered recruitment issue.
                    detail=b.name+' needs '+', '.join(sorted(staffing['missing']))+' before it can open.'
                    if decision:decision.update(status='open',detail=detail)
                    self.decision('opening-staff:'+b.id,'Opening needs staff',detail,b.id);stop=True;continue
                if decision and decision['status']=='open':
                    decision.update(status='resolved',choice='staffed',resolved=self.w.date)
                    decision['options']['staffed']='Required roles recruited'
                if staffing['waiting']:
                    plan['phase']='Accepted hires start '+staffing['starts']+'; commissioning waits for active staff'
                    continue
                b.status='operating';b.opening_on=None;plan['status']='complete';plan['phase']='Open and ramping up';b.capacity_percent=70
                if b.industry in PROJECTS:b.project_active=True
                self.e.event('New business opened',b.name+' is trading. Capacity ramps toward normal over its first month.',True);stop=True
            elif plan['kind']=='upgrade':
                b.capacity_percent=min(200,b.capacity_percent+20);plan['status']='complete';self.e.event('Business expansion complete',b.name+' has more equipment capacity; staffing and demand still matter.',True);stop=True
            elif plan['kind']=='business_sale':
                if b.owner!=plan['owner']:raise RuleError('Sale ownership changed; resolve the pending sale first.')
                owner=b.owner;price=plan['price'];fee=price*2//100;investment=self.w.accounts[owner].get(investment_account(b.id),0);goodwill=self.w.accounts[owner].get('asset:goodwill:'+b.id,0)
                self.e.post(owner,'company-sale:'+plan['id'],'Whole-company divestment: '+b.name,{'asset:cash':price-fee,investment_account(b.id):-investment,'asset:goodwill:'+b.id:-goodwill,'expense:selling':fee,'income:investment_gain':-(price-investment-goodwill)})
                b.owner=None;b.outside_owner='Independent buyer';b.status='independent';plan['status']='complete'
                self.s['ownership_history'].append(dict(date=self.w.date,entity=b.id,from_owner=owner,to_owner='Independent buyer',kind='divestment'))
                for emp in self.w.employments:
                    if emp.employer in plan['entities']:
                        self.rules.record(emp.person_id,'Employment continued under an independent buyer after divestment.')
                self.e.event('Company sale completed',b.name+' and its subsidiaries transferred to an independent buyer. Their revenue and employees are no longer consolidated.',True);stop=True
        for b in self.w.businesses:
            if not self.controlled(b.id):continue
            if b.status=='operating' and b.capacity_percent<100:b.capacity_percent+=1
            if b.integration.get('status')=='active' and b.integration['due']<=self.w.date:
                mode=b.integration['mode'];b.integration['status']='complete'
                if mode=='rebrand':b.reputation=min(100,b.reputation+5)
                if mode=='leadership_review':
                    for emp in self.rules.staff(b.id):self.rules.person(emp.person_id).trust=min(100,self.rules.person(emp.person_id).trust+3)
                self.e.event('Integration phase completed',b.name+' completed '+mode.replace('_',' ')+'. Existing staff and records were retained.',True);stop=True
        return stop
