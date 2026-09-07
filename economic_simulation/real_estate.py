"""Usable spaces, leases, tenant obligations and owner-performed renovation."""
from __future__ import annotations
from datetime import date,timedelta
from .campaign import Campaign,integer
from .domain import RuleError,calendar_target,daily_share


def required_category(business):
    return 'industrial' if business.industry in ('trades','construction','factory','self_storage','logistics') else 'commercial'


def commercial(prop):return prop.category in ('commercial','industrial','office','mixed_use')

def compatible(use,business):
    return use==required_category(business) or use=='office' and business.industry in ('engineering','property_management','bank','office') or use=='mixed_use' and required_category(business)=='commercial'


def area(prop):return prop.usable_area or (1200 if commercial(prop) else 240 if prop.kind.lower()=='duplex' else 120)


class RealEstate(Campaign):
    def property(self,pid):
        p=next((p for p in self.w.properties if p.id==pid),None)
        if not p or not p.owner:raise RuleError('Choose an owned property.')
        self.require(p.owner);return p

    def action(self,action,args,command_id):
        if action in ('lease_response','end_lease','write_off_rent'):
            lease=next((l for l in self.s['leases'] if l['id']==args.get('lease_id') and (l['status']=='active' or action=='write_off_rent')),None)
            if not lease:raise RuleError('Choose an active lease.')
            self.require(lease['owner'])
            if action=='write_off_rent':
                if lease['tenant']!='external' or not lease['arrears']:raise RuleError('Choose an external tenant with unpaid rent.')
                amount=lease['arrears'];self.e.post(lease['owner'],command_id,'Write off uncollectible rent',{'expense:bad_debt':amount,'asset:rent_receivable:'+lease['id']:-amount});lease['arrears']=0
                return 'Uncollectible rent written off as a loss. Cash and past revenue were not fabricated.'
            if action=='lease_response':
                if lease['tenant']!='external':raise RuleError('Fund the tenant company to settle unpaid intercompany rent automatically on the next day.')
                if not lease['arrears']:raise RuleError('This tenant has no unpaid rent.')
                response=args.get('response','plan')
                if response=='plan':
                    lease['payment_plan']=True
                    return 'Payment plan recorded. The external tenant settles half the arrears on the next collection date; the rest remains due.'
                if response!='vacate':raise RuleError('Choose a payment plan or possession notice.')
                lease['end_date']=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat()
                return 'A 30-day possession notice was served. Arrears remain receivable until settlement or an explicit write-off.'
            fee=lease['rent'] if lease['end_date']>self.w.date else 0
            if fee:
                self.e.post(lease['owner'],command_id,'Lease early-termination compensation',{'asset:cash':-fee,'expense:lease_termination':fee})
                if lease['tenant']!='external':self.e.post(lease['tenant'],command_id,'Compensation for early lease termination',{'asset:cash':fee,'income:lease_compensation':-fee})
            lease['end_date']=self.w.date
            return 'Lease termination scheduled. Deposit settlement and any remaining rent receivable are retained.'
        p=self.property(args.get('property_id',''))
        if p.occupancy_use=='personal_residence' and action!='self_renovate':raise RuleError('Move out of your personal residence before changing its occupancy or use.')
        if p.status=='building':raise RuleError('Finish construction before changing occupancy.')
        if p.category=='land':raise RuleError('Build on the lot before configuring, occupying or improving premises.')
        if action in ('occupy_property','lease_premises'):
            from .business_rules import BusinessRules
            from .premises import require_available
            b=BusinessRules(self.e).company(args.get('business_id',''))
            require_available(self.w,b)
            if p.specialization and b.industry not in p.specialization:raise RuleError('This specialized building supports: '+', '.join(p.specialization))
            if not compatible(p.category,b):raise RuleError('This business requires '+required_category(b)+' premises. Convert a space before leasing it.')
            if p.region!=b.region:raise RuleError('Choose premises in the business region.')
            if p.status!='vacant' or p.spaces:raise RuleError('Choose a vacant, undivided building. Manage existing spaces through Spaces & leases.')
            if p.condition<40:raise RuleError('Improve this building to at least 40 condition before moving a business in.')
            if action=='occupy_property':
                if p.owner!=b.id:raise RuleError('The operating business must own the building. Use a lease when another company owns it.')
                p.status='occupied';p.occupant=b.id;p.occupancy_use='operating'
                return b.name+' now operates from '+p.name+'. External premises rent stops; property upkeep continues.'
            if p.owner==b.id:raise RuleError('Use company-owned premises directly; a company does not pay rent to itself.')
            p.spaces=[dict(id=self.uid('space'),name='Whole building',area=area(p),use=p.category,office_id=None)]
            return self.action('lease_space',{**args,'space_id':p.spaces[0]['id'],'tenant':b.id,'tenant_name':b.name},command_id)
        if action=='configure_spaces':
            if p.status!='vacant' or any(l['property_id']==p.id and l['status']=='active' for l in self.s['leases']):raise RuleError('Spaces can be configured only in a vacant building with no active lease.')
            units=integer(args.get('units',1),1,20);size=area(p)
            if size//units<20:raise RuleError('Each space must have at least 20 square meters.')
            allowed=p.category
            p.spaces=[dict(id=self.uid('space'),name=f'Unit {i+1}',area=size//units+(i<size%units),use=allowed,office_id=None) for i in range(units)]
            p.status='managed';p.usable_area=size
            return f'{units} separately leasable spaces configured within {size} square meters. No space or tenant was created twice.'
        if action=='lease_space':
            space=next((s for s in p.spaces if s['id']==args.get('space_id')),None)
            if any(x['kind']=='conversion' and x.get('space_id')==args.get('space_id') and x['status']=='active' for x in self.s['plans']):raise RuleError('Finish the conversion before leasing this space.')
            if not space or space.get('office_id'):raise RuleError('Choose a configured space that is not occupied by a headquarters.')
            if any(l['space_id']==space['id'] and l['status']=='active' for l in self.s['leases']):raise RuleError('That space already has an occupier.')
            tenant=args.get('tenant','external')
            if tenant!='external':
                self.require(tenant)
                from .business_rules import BusinessRules
                from .premises import require_available
                b=BusinessRules(self.e).company(tenant)
                require_available(self.w,b)
                if p.specialization and b.industry not in p.specialization:raise RuleError('This specialized building supports: '+', '.join(p.specialization))
                if b.region!=p.region:raise RuleError('Choose premises in the business region.')
                if tenant==p.owner:raise RuleError('Use the headquarters workflow for owner-occupied space; internal rent to yourself is not a transaction.')
                if not compatible(space['use'],b):raise RuleError('This business requires '+required_category(b)+' space. Complete a conversion first.')
            rent=integer(args.get('rent',p.suggested_rent//max(1,len(p.spaces))),10000,10000000);months=integer(args.get('months',12),1,120)
            deposit=rent*integer(args.get('deposit_months',1),0,3);escalation=integer(args.get('escalation_percent',2),0,8)
            lid=self.uid('lease');today=date.fromisoformat(self.w.date);end=today
            for _ in range(months):end=calendar_target(end,'month')
            if deposit:
                if tenant!='external':self.e.post(tenant,command_id+':tenant','Lease security deposit paid',{'asset:cash':-deposit,'asset:lease_deposit:'+lid:deposit})
                self.e.post(p.owner,command_id+':owner','Refundable tenant deposit received',{'asset:cash':deposit,'liability:deposit:'+lid:-deposit})
            lease=dict(id=lid,property_id=p.id,space_id=space['id'],owner=p.owner,tenant=tenant,tenant_name=str(args.get('tenant_name','Independent household' if space['use']=='residential' else 'Independent business tenant')).strip()[:80],rent=rent,deposit=deposit,created=self.w.date,end_date=end.isoformat(),escalation_percent=escalation,next_escalation=calendar_target(today,'year').isoformat(),arrears=0,status='active',history=[],payment_plan=False,deposit_remaining=deposit)
            self.s['leases'].append(lease);p.status='managed'
            return f'Lease begins today at ${rent/100:,.2f}/month with a ${deposit/100:,.2f} refundable deposit, ending {end}. Rent accrues daily and external tenants settle monthly.'
        if action=='convert_space':
            space=next((s for s in p.spaces if s['id']==args.get('space_id')),None)
            use=args.get('use','commercial')
            if not space or use not in ('commercial','residential','industrial','office','mixed_use'):raise RuleError('Choose a configured space and permitted use.')
            if space.get('office_id') or any(l['space_id']==space['id'] and l['status']=='active' for l in self.s['leases']):raise RuleError('The space must be vacant before conversion.')
            if any(x['kind']=='conversion' and x.get('space_id')==space['id'] and x['status']=='active' for x in self.s['plans']):raise RuleError('Conversion is already underway.')
            cost=space['area']*20000
            self.e.post(p.owner,command_id,'Capitalized space conversion',{'asset:cash':-cost,'asset:property':cost});p.basis+=cost
            self.s['plans'].append(dict(id=self.uid('conversion'),kind='conversion',entity=p.owner,property_id=p.id,space_id=space['id'],use=use,due=(date.fromisoformat(self.w.date)+timedelta(days=45)).isoformat(),status='active',cost=cost))
            return f'Conversion funded for ${cost/100:,.2f}. Simulated permission and work take 45 days; the space cannot be leased before completion.'
        if action=='self_renovate':
            from .property_operations import PropertyOperations
            return PropertyOperations(self.e).action('property_work',dict(property_id=p.id,provider='owner',system='interior',kind='cosmetic'),command_id)
        if action=='release_premises':
            if p.status!='occupied':raise RuleError('Choose owner-occupied operating premises.')
            if any(o['property_id']==p.id and o['active'] for o in self.s['offices']):raise RuleError('Close or relocate the headquarters before releasing this building.')
            p.status='vacant';p.occupant=None;p.occupancy_use='rental'
            return 'Operating premises released. The business resumes its external premises lease until another location is arranged.'
        raise RuleError('Unknown property management action.')

    def tick(self,today):
        stop=False
        if self.s['owner_work'] and self.s['owner_work']['due']<=self.w.date:
            self.s['owner_skills']['maintenance']=min(95,self.s['owner_skills']['maintenance']+2);self.s['owner_work']=None
        for plan in self.s['plans']:
            if plan['kind']=='conversion' and plan['status']=='active' and plan['due']<=self.w.date:
                p=next(p for p in self.w.properties if p.id==plan['property_id']);space=next(s for s in p.spaces if s['id']==plan['space_id']);space['use']=plan['use'];plan['status']='complete'
                self.e.event('Space conversion completed',p.name+' '+space['name']+' is approved for '+space['use']+' occupancy.',True);stop=True
        for lease in self.s['leases']:
            owner=lease['owner'];tenant=lease['tenant'];lid=lease['id']
            if lease['status']=='active' and lease['end_date']<=self.w.date:
                lease['status']='ended';self.e.event('Space lease ended',lease['tenant_name']+' vacated. Deposit obligations and unpaid rent are retained.',True);stop=True
            if lease['status']=='ended' and lease['deposit_remaining']:
                offset=min(lease['deposit_remaining'],lease['arrears']) if tenant=='external' else 0
                if offset:
                    self.e.post(owner,f'deposit-arrears:{lid}:{self.w.date}','Apply deposit against unpaid rent',{'liability:deposit:'+lid:offset,'asset:rent_receivable:'+lid:-offset});lease['deposit_remaining']-=offset;lease['arrears']-=offset
                returned=min(lease['deposit_remaining'],self.w.cash(owner))
                if returned:
                    self.e.post(owner,f'deposit-return:{lid}:{self.w.date}','Return tenant security deposit',{'asset:cash':-returned,'liability:deposit:'+lid:returned})
                    if tenant!='external':self.e.post(tenant,f'deposit-return:{lid}:{self.w.date}','Security deposit returned',{'asset:cash':returned,'asset:lease_deposit:'+lid:-returned})
                    lease['deposit_remaining']-=returned
            if lease['status']!='active':
                if tenant!='external':self.settle_company_rent(lease,0)
                continue
            if lease['next_escalation']<=self.w.date:
                old=lease['rent'];lease['rent']=old*(100+lease['escalation_percent'])//100;lease['next_escalation']=calendar_target(today,'year').isoformat();lease['history'].append(dict(date=self.w.date,old_rent=old,new_rent=lease['rent']))
            rent=daily_share(lease['rent'],today)
            from .property_operations import rent_factor
            p=self.e.get_property(lease['property_id'])
            rent=rent*rent_factor(self.w,p)//100
            totals=self.s.setdefault('property_income_totals',{}).setdefault(p.id,dict(since=self.w.date,earned=0,collected=0))
            totals['earned']+=rent
            if tenant=='external':
                self.e.post(owner,f'space-rent:{lid}:{self.w.date}','External space rent accrued',{'asset:rent_receivable:'+lid:rent,'income:rent':-rent});lease['arrears']+=rent
                if today.day==1:
                    default=self.roll('economy',1,100)<=max(2,100-lease.get('reliability',98)) and not lease['payment_plan']
                    payment=0 if default else lease['arrears']//2 if lease['payment_plan'] else lease['arrears']
                    totals['collected']+=payment
                    if payment:self.e.post(owner,f'space-collection:{lid}:{self.w.date}','Tenant rent collection',{'asset:cash':payment,'asset:rent_receivable:'+lid:-payment});lease['arrears']-=payment
                    if default and self.controlled(owner):self.decision(f'tenant-arrears:{lid}:{self.w.date}','Tenant payment missed',f'{lease["tenant_name"]} missed collection. ${lease["arrears"]/100:,.2f} remains receivable. Offer a payment plan or serve notice from Spaces.',owner,financial_amount=lease['arrears']);stop=True
            else:
                self.settle_company_rent(lease,rent)
        return stop

    def settle_company_rent(self,lease,rent):
        owner,tenant=lease['owner'],lease['tenant']
        from .holding_company import name
        names={'personal':'Personal portfolio','company':name(self.w),**{b.id:b.name for b in self.w.businesses}}
        paid=min(rent+lease['arrears'],self.w.cash(tenant));owed=rent-paid
        if not rent and not paid:return
        source=f'internal-rent:{lease["id"]}:{self.w.date}'
        self.e.post(tenant,source,'Premises rent to '+names.get(owner,owner),{'expense:internal_rent:'+owner:rent,'asset:cash':-paid,'liability:intercompany:'+owner:-owed})
        self.e.post(owner,source,'Rent received from '+names.get(tenant,tenant),{'income:internal_rent:'+tenant:-rent,'asset:cash':paid,'asset:intercompany:'+tenant:owed})
        lease['arrears']+=owed
        self.s.setdefault('property_income_totals',{}).setdefault(lease['property_id'],dict(since=self.w.date,earned=0,collected=0))['collected']+=paid

    def validate(self):
        occupied=set()
        for p in self.w.properties:
            if sum(s['area'] for s in p.spaces)>area(p):raise RuleError('Space allocation exceeds usable building area.')
        for lease in self.s.get('leases',[]):
            p=next((p for p in self.w.properties if p.id==lease['property_id']),None)
            if not p or not any(s['id']==lease['space_id'] for s in p.spaces):raise RuleError('Lease refers to an unavailable space.')
            if lease['status']=='active':
                if lease['space_id'] in occupied:raise RuleError('A space cannot have two occupiers.')
                occupied.add(lease['space_id'])
            if self.w.accounts[lease['owner']].get('liability:deposit:'+lease['id'],0)!=-lease['deposit_remaining']:raise RuleError('Deposit obligations do not reconcile.')
            if lease['tenant']=='external' and self.w.accounts[lease['owner']].get('asset:rent_receivable:'+lease['id'],0)!=lease['arrears']:raise RuleError('Tenant receivables do not reconcile.')
