"""Property systems, tenant offers, resource work and contingent property sales."""
from datetime import date,timedelta
from .campaign import Campaign,integer
from .domain import RuleError,daily_share,calendar_target,GAME_RULES
from .simulation_support import stable_roll

SYSTEMS=('structure','roof','plumbing','electrical','heating_cooling','interior','exterior','equipment')
WORK={'emergency':(25,360,False),'repair':(15,720,False),'preventive':(5,360,False),
      'replacement':(80,1800,True),'cosmetic':(20,1200,True),'conversion':(30,3600,True)}


def systems_for(world,p):
    return world.systems.get('property_systems',{}).get(p.id) or {
        key:dict(condition=max(5,min(100,p.condition+stable_roll(world,p.id+':'+key,17)-8)),age=stable_roll(world,p.id+':age:'+key,25),maintained_until='',wear=0)
        for key in SYSTEMS}


def rent_factor(world,p):
    work=any(j['property_id']==p.id and j['status']=='working' and j['kind'] in ('emergency','replacement','conversion') for j in world.systems.get('property_work',[]))
    if work:return 50
    if p.id in world.systems.get('property_systems',{}) and min(x['condition'] for x in systems_for(world,p).values())<25:return 80
    return 100


class PropertyOperations(Campaign):
    def ensure_market_types(self):
        if self.s.get('extended_property_types'):return
        from .domain import Property,PROPERTY_CONTENT
        for spec in PROPERTY_CONTENT['properties']:
            if spec['category']!='commercial':continue
            for category in ('office','mixed_use'):
                if any(p.category==category and p.region==spec['region'] and p.status=='market' for p in self.w.properties):continue
                values=dict(spec,category=category,kind='Office building' if category=='office' else 'Shops and apartments',name=spec['region']+(' Office Court' if category=='office' else ' Market House'),description='Purpose-built office suites.' if category=='office' else 'A mixed-use building with space for shops and residences.')
                p=Property(**values,id='p'+str(self.w.next_id),asking=0);self.w.next_id+=1
                p.asking=p.value*94//100;self.w.properties.append(p)
        self.s['extended_property_types']=True

    def ensure(self,p):
        return self.s.setdefault('property_systems',{}).setdefault(p.id,systems_for(self.w,p))

    def quote(self,p,system,kind):
        if p.category=='land':raise RuleError('An empty lot has no building systems to repair.')
        if system not in SYSTEMS or kind not in WORK:raise RuleError('Choose a property system and type of work.')
        gain,effort,capital=WORK[kind];condition=systems_for(self.w,p)[system]['condition']
        gain=max(0,95-condition) if kind=='replacement' else min(gain,100-condition)
        materials=max(15000,p.full_value*max(5,gain)//15000)
        if system in ('structure','roof','electrical'):materials*=3
        if kind=='emergency':materials*=2
        return dict(materials=materials,effort=effort,labor=effort*100,total=materials+effort*100,
            gain=gain,capital=capital,qualification=65 if system in ('structure','electrical') or kind=='conversion' else 40,
            downtime=max(1,(effort+239)//240),exposure='Failure risk and rent disruption rise as condition falls below 40.')

    def plan_work(self,p,args,require_crew=False):
        """Validate without changing cash, system facts, identities or queues."""
        system=args.get('system','interior');kind=args.get('kind','repair');q=self.quote(p,system,kind)
        if kind=='conversion':
            from .real_estate import area
            use=args.get('use',p.category)
            if use not in ('residential','commercial','industrial','office','mixed_use'):raise RuleError('Choose a supported conversion use.')
            if systems_for(self.w,p)['structure']['condition']<40:raise RuleError('Repair the existing structure before changing the permitted use.')
            if use=='industrial' and area(p)<300:raise RuleError('Industrial conversion requires at least 300 square meters of suitable space.')
        if any(j['property_id']==p.id and j['system']==system and j['status']=='working' for j in self.s.get('property_work',[])):
            raise RuleError('Work on this system is already committed.')
        if kind in ('cosmetic','conversion') and any(l['property_id']==p.id and l['status']=='active' for l in self.s['leases']):
            raise RuleError('This disruptive work requires vacant space.')
        provider=args.get('provider','outside')
        from .qualified_capacity import TRADE_LICENSES, eligible
        license_name=TRADE_LICENSES.get(system)
        if provider=='owner':
            from .property_development import owner_busy
            if owner_busy(self.w) or self.s.get('owner_work'):raise RuleError('Finish or outsource the existing owner project first.')
            if system not in ('interior','exterior') or kind not in ('repair','preventive','cosmetic'):raise RuleError('Owner work is limited to basic interior/exterior repair, prevention and cosmetic work. Trade and structural work require qualified contractors.')
        elif provider!='outside':
            self.require(provider)
            b=next((b for b in self.w.businesses if b.id==provider and b.status=='operating'),None)
            if not b:raise RuleError('Choose an operating internal contractor.')
            from .business_rules import BusinessRules
            rules=BusinessRules(self.e)
            qualified=[emp for emp in rules.staff(b.id) if rules.position(emp.position_id).role in ('maintenance','tradesperson','builder','engineer','electrician','plumber','hvac_technician') and rules.person(emp.person_id).skills.get('maintenance',0)>=q['qualification'] and (not license_name or rules.person(emp.person_id).licenses.get(license_name,'')>=self.w.date)]
            if license_name and not qualified:raise RuleError('This contractor needs staff with '+license_name+' license. Hire, train or choose outside labor.')
            if require_crew and not qualified:raise RuleError('This contractor needs qualified maintenance staff. Hire, train or choose outside labor.')
        assigned=[uid for uid in str(args.get('assigned_staff','')).split(',') if uid]
        if assigned and (provider in ('outside','owner') or not set(assigned)<=set(emp.id for emp in qualified)):
            raise RuleError('Assigned repair staff must be qualified employees of the chosen contractor.')
        cost=q['materials']+(q['labor'] if provider=='outside' else 0)
        return dict(system=system,kind=kind,q=q,provider=provider,license_name=license_name,cost=cost)

    def book_work(self,p,args,source,plan):
        system,kind,q,provider,license_name,cost=(plan[k] for k in ('system','kind','q','provider','license_name','cost'))
        self.e.post(p.owner,source,'Property work deposit and materials',{'asset:cash':-cost,'asset:prepaid_works':cost})
        flows=self.s.setdefault('property_income_totals',{}).setdefault(p.id,dict(since=self.w.date,earned=0,collected=0))
        flows['work_paid']=flows.get('work_paid',0)+cost
        job=dict(id=self.uid('work'),property_id=p.id,owner=p.owner,system=system,kind=kind,provider=provider,
            **q,remaining=q['effort'],prepaid=cost,status='working',created=self.w.date,actual_cost=0,
            use=args.get('use',p.category),quality=0,labor_used=0,required_license=license_name,staff=[],
            assigned_staff=[uid for uid in str(args.get('assigned_staff','')).split(',') if uid])
        job['outside_paid']=cost if provider=='outside' else 0
        self.ensure(p);self.s.setdefault('property_work',[]).append(job)
        return job

    def repair_all(self,p,args,source):
        if args.get('kind','repair')!='repair':
            raise RuleError('Repair all books ordinary repairs. Select an individual system for other work.')
        active={j['system'] for j in self.s.get('property_work',[]) if j['property_id']==p.id and j['status']=='working'}
        facts=systems_for(self.w,p)
        keys=[key for key in SYSTEMS if facts[key]['condition']<100 and key not in active]
        if not keys:raise RuleError('Nothing to book: all systems are at 100 condition or already have work underway.')
        if args.get('provider')=='owner' and len(keys)>1:
            raise RuleError('The owner can repair one basic system at a time. Choose an outside contractor or a qualified owned company for Repair all.')
        plans=[]
        for key in keys:
            job_args=dict(args,system=key,kind='repair')
            try:plan=self.plan_work(p,job_args,require_crew=True)
            except RuleError as exc:raise RuleError(key.replace('_',' ').title()+': '+str(exc)) from exc
            plans.append((job_args,plan))
        total=sum(plan['cost'] for _,plan in plans)
        if total>self.w.cash(p.owner):
            from .money_display import money
            raise RuleError('Repair all needs '+money(total)+' paid now; this property owner has '+money(self.w.cash(p.owner))+'. Transfer funds or select individual repairs. No repairs were booked.')
        # All eligibility and combined cash checks precede the first posting.
        for job_args,plan in plans:self.book_work(p,job_args,source+':'+plan['system'],plan)
        from .money_display import money
        items='; '.join(plan['system'].replace('_',' ').title()+' '+str(facts[plan['system']]['condition'])+'/100: '+money(plan['cost']) for _,plan in plans)
        skipped=[key.replace('_',' ').title()+' ('+('work underway' if key in active else '100/100')+')' for key in SYSTEMS if key not in keys]
        return ('Repair all booked for '+p.name+': '+str(len(plans))+' systems, '+money(total)+' paid now. '+items+'. '
            +('Skipped: '+', '.join(skipped)+'. ' if skipped else '')
            +'One ordinary repair per system; up to 15 condition points before workmanship effects, not guaranteed restoration to 100. '
            +str(sum(plan['q']['effort'] for _,plan in plans)//60)+' qualified hours total. Outside crews take about 3 simulated days per repair and work in parallel; internal crews share available hours and labor is charged as delivered.')

    def action(self,action,args,source):
        from .real_estate import RealEstate
        p=self.e.get_property(args.get('property_id',''))
        if action=='fund_flip':
            entity=self.require(args.get('entity','personal'))
            budget=self.s.get('flip_budgets',{}).get(p.id)
            if not budget or budget['entity']!=entity:raise RuleError('Prepare this investor’s flip budget first.')
            if p.id not in self.s.get('inspections',{}):raise RuleError('Inspect the property before funding a flip.')
            reserve=budget['renovation']+budget['contingency']+budget['holding']
            committed=self.e.quote('buy',p.id,entity)['total']+reserve
            self.e.action('buy',dict(property_id=p.id,entity=entity),source+':purchase')
            if reserve:self.e.post(entity,source+':reserve','Ring-fence approved flip capital',{'asset:cash':-reserve,'asset:flip_reserve':reserve})
            self.s.setdefault('flip_progress',{})[p.id]=dict(property_id=p.id,entity=entity,reserve=reserve,holding_remaining=budget['holding'],committed=committed,phase='funded',created=self.w.date)
            return 'Flip acquired and future project capital reserved. Reserves are assets, not income or renovation expense.'
        if action=='inspect_property' and p.category=='land':raise RuleError('Land options show the serviced site area. Building-system inspections apply after construction.')
        if action=='inspect_property':
            entity=self.require(args.get('entity',p.owner or 'personal'))
            self.e.post(entity,source,'Independent property inspection',{'asset:cash':-35000,'expense:inspection':35000})
            facts=self.ensure(p)
            readings={key:max(0,min(100,value['condition']+stable_roll(self.w,'inspection:'+p.id+':'+key,11)-5)) for key,value in facts.items()}
            self.s.setdefault('inspections',{})[p.id]=dict(date=self.w.date,readings=readings,uncertainty=5,cost=35000,owner=entity)
            return 'Inspection delivered estimated condition for eight existing systems, with +/-5 uncertainty. The inspection did not create defects.'
        if action=='flip_budget':
            entity=self.require(args.get('entity',p.owner or 'personal'))
            renovation=integer(args.get('renovation',500000),0,1000000000)
            duration=integer(args.get('days',90),7,730)
            purchase=p.basis if p.owner else self.e.quote('buy',p.id,entity)['total']
            holding=p.upkeep*duration//30;contingency=renovation//5
            low=p.value*80//100;high=p.value*110//100
            plan=dict(property_id=p.id,entity=entity,date=self.w.date,purchase=purchase,renovation=renovation,
                contingency=contingency,holding=holding,days=duration,sale_low=low,sale_high=high,
                profit_low=low*95//100-purchase-renovation-contingency-holding,
                profit_high=high*97//100-purchase-renovation-holding)
            self.s.setdefault('flip_budgets',{})[p.id]=plan
            return f"Budget recorded. Downside ${plan['profit_low']/100:,.2f}; upper scenario ${plan['profit_high']/100:,.2f}. Financing proceeds are excluded from profit; no purchase committed."
        self.require(p.owner)
        if p.occupancy_use=='personal_residence' and (action in ('advertise_space','accept_tenant','renew_property_lease','market_property','accept_property_offer') or action=='property_work' and args.get('kind')=='conversion'):
            raise RuleError('Move out of your personal residence before leasing, selling or converting it. Repairs remain available.')
        if p.status=='building':raise RuleError('Finish funded construction before other property actions.')
        if p.category=='land' and action not in ('market_property','accept_property_offer','withdraw_property_sale'):raise RuleError('Develop an empty lot before property operations.')
        if action=='outsource_property_work':
            job=next((j for j in self.s.get('property_work',[]) if j['id']==args.get('work_id') and j['property_id']==p.id and j['status']=='working'),None)
            if not job or job['provider']=='outside':raise RuleError('Choose unfinished work assigned to an internal contractor.')
            cost=job['remaining']*100
            self.e.post(p.owner,source,'Prepay remaining outside repair labor',{'asset:cash':-cost,'asset:prepaid_works':cost})
            job['prepaid']+=cost;job['provider']='outside';job['outside_paid']=cost
            flows=self.s.setdefault('property_income_totals',{}).setdefault(p.id,dict(since=self.w.date,earned=0,collected=0))
            flows['work_paid']=flows.get('work_paid',0)+cost
            return 'Remaining work moved to a qualified outside contractor. Prior labor, materials and costs remain recorded.'
        if action=='add_flip_reserve':
            progress=self.s.get('flip_progress',{}).get(p.id)
            if not progress or progress['phase']=='sold':raise RuleError('Choose an active funded flip.')
            amount=integer(args.get('amount',0),1,1000000000)
            self.e.post(p.owner,source,'Additional owner-approved flip reserve',{'asset:cash':-amount,'asset:flip_reserve':amount})
            progress['reserve']+=amount;progress['committed']+=amount
            return 'Additional capital reserved. Existing costs, commitments and downside exposure remain visible.'
        if action=='flip_work':
            progress=self.s.get('flip_progress',{}).get(p.id)
            q=self.quote(p,'interior','cosmetic')
            work_args=dict(args,system='interior',kind='cosmetic',provider=args.get('provider','outside'))
            plan=self.plan_work(p,work_args,require_crew=True)
            from .authority import labor_allowance
            from .internal_property_services import REPAIR_ROLES
            commitment=plan['cost']+(labor_allowance(self.w,plan['provider'],REPAIR_ROLES,q['effort']) if plan['provider'] not in ('outside','owner') else 0)
            if not progress or progress['phase']!='funded' or commitment>progress['reserve']:raise RuleError('This work exceeds the remaining approved flip reserve. Revise and fund the project before proceeding.')
            self.e.post(p.owner,source+':release','Release approved work reserve',{'asset:flip_reserve':-plan['cost'],'asset:cash':plan['cost']})
            progress['reserve']-=plan['cost']
            job=self.book_work(p,work_args,source,plan);job['flip_funded']=True
            progress['phase']='working';return 'Approved flip reserve released into real contractor work.'
        if action=='property_work':
            if args.get('system')=='all':return self.repair_all(p,args,source)
            plan=self.plan_work(p,args)
            self.book_work(p,args,source,plan)
            return f"Work committed: ${plan['cost']/100:,.2f} paid now; {plan['q']['effort']/60:g} qualified hours plus materials. Internal labor is charged as delivered and competes with outside jobs."
        if action=='advertise_space':
            if not p.spaces:
                RealEstate(self.e).action('configure_spaces',dict(property_id=p.id,units=1),source+':spaces')
            space=next((s for s in p.spaces if s['id']==args.get('space_id')),p.spaces[0])
            if any(l['space_id']==space['id'] and l['status']=='active' for l in self.s['leases']):raise RuleError('This space is occupied.')
            if any(a['space_id']==space['id'] and a['status']=='advertising' for a in self.s.get('vacancies',[])):raise RuleError('Advertising is already active.')
            self.e.post(p.owner,source,'Vacancy advertising',{'asset:cash':-15000,'expense:leasing':15000})
            self.s.setdefault('vacancies',[]).append(dict(id=self.uid('vacancy'),property_id=p.id,space_id=space['id'],status='advertising',due=(date.fromisoformat(self.w.date)+timedelta(days=5)).isoformat(),asking=integer(args.get('rent',p.suggested_rent//len(p.spaces)),10000,10000000)))
            return 'Vacancy advertised. Tenant proposals arrive in five days; compare reliability, fit and improvement requests.'
        if action=='accept_tenant':
            offer=next((o for o in self.s.get('tenant_offers',[]) if o['id']==args.get('offer_id') and o['property_id']==p.id and o['status']=='open'),None)
            if not offer:raise RuleError('Choose an open tenant proposal.')
            rent=integer(args.get('rent',offer['rent']),10000,10000000)
            if rent>offer['max_rent']:raise RuleError('The tenant rejected rent above their stated ceiling.')
            space=next(s for s in p.spaces if s['id']==offer['space_id'])
            if space['area']<offer['area']:raise RuleError('The tenant requires more space than this unit provides.')
            if offer['improvement']:
                self.e.post(p.owner,source,'Negotiated tenant improvement allowance',{'asset:cash':-offer['improvement'],'expense:lease_concessions':offer['improvement']})
            RealEstate(self.e).action('lease_space',dict(property_id=p.id,space_id=space['id'],rent=rent,months=offer['months'],deposit_months=1,tenant='external',tenant_name=offer['name']),source)
            lease=self.s['leases'][-1];lease.update(reliability=offer['reliability'],tenant_offer=offer['id'],renewals=0)
            for other in self.s['tenant_offers']:
                if other['space_id']==space['id'] and other['status']=='open':other['status']='accepted' if other is offer else 'declined'
            return 'Tenant accepted and deposit liability recorded. Rent is earned over the lease; payment reliability affects collection.'
        if action=='renew_property_lease':
            lease=next((l for l in self.s['leases'] if l['id']==args.get('lease_id') and l['property_id']==p.id and l['status']=='active'),None)
            if not lease:raise RuleError('Choose an active lease.')
            if lease['end_date']>(date.fromisoformat(self.w.date)+timedelta(days=60)).isoformat():raise RuleError('Renewals open 60 days before expiry.')
            rent=integer(args.get('rent',lease['rent']),10000,10000000)
            ceiling=lease['rent']*(100+max(0,5-lease.get('renewals',0)))//100
            from .property_requests import PropertyRequests
            ceiling=PropertyRequests(self.e).renewal_ceiling(lease,ceiling)
            from .property_services import presentation
            ceiling=ceiling*min(100,presentation(self.w,p))//100
            if rent>ceiling:raise RuleError('Tenant declined that renewal increase.')
            lease['rent']=rent;lease['end_date']=calendar_target(date.fromisoformat(lease['end_date']),'year').isoformat();lease['renewals']=lease.get('renewals',0)+1
            return 'Lease renewed for one year within the tenant’s negotiated rent ceiling.'
        if action=='market_property':
            if any(j['property_id']==p.id and j['status']=='working' for j in self.s.get('property_work',[])):raise RuleError('Complete the current work before marketing the property.')
            if p.status not in ('vacant','managed','marketing','rented'):raise RuleError('This property is not available for a sale listing.')
            asking=integer(args.get('asking',p.value),10000,1000000000)
            listing=self.s.setdefault('property_listings',{}).get(p.id)
            if listing and listing['status']=='closing':raise RuleError('A sale is already in closing.')
            if listing:listing.update(asking=asking,next_offer=(date.fromisoformat(self.w.date)+timedelta(days=7)).isoformat(),status='marketing')
            else:self.s['property_listings'][p.id]=dict(property_id=p.id,owner=p.owner,asking=asking,status='marketing',round=0,next_offer=(date.fromisoformat(self.w.date)+timedelta(days=7)).isoformat(),created=self.w.date,offers=[])
            # Sale marketing is separate from occupancy; existing rent continues.
            return 'Property marketed. Offers depend on comparable value, condition, demand and asking price; financing can fail before closing.'
        if action=='accept_property_offer':
            listing=self.s.get('property_listings',{}).get(p.id,{})
            offer=next((o for o in listing.get('offers',[]) if o['id']==args.get('offer_id') and o['status']=='open'),None)
            if not offer or listing.get('status')!='marketing':raise RuleError('Choose an open offer for this listing.')
            listing.update(status='closing',accepted=offer['id'],due=(date.fromisoformat(self.w.date)+timedelta(days=14)).isoformat())
            offer['status']='accepted'
            return 'Offer accepted with a 14-day closing and financing condition. Proceeds are not cash yet.'
        if action=='withdraw_property_sale':
            listing=self.s.get('property_listings',{}).get(p.id)
            if not listing or listing['status']!='marketing':raise RuleError('Only an uncommitted sale listing can be withdrawn.')
            listing['status']='withdrawn'
            return 'Sale marketing withdrawn. Suitable vacant spaces can be advertised for rent.'
        raise RuleError('Unknown property operations command.')

    def apply_work(self,job,effort,quality,labor_cost=0):
        p=self.e.get_property(job['property_id']);capital=job['capital']
        if job.get('flip_funded') and job['provider'] not in ('outside','owner') and labor_cost:
            progress=self.s['flip_progress'][p.id]
            if labor_cost>progress['reserve']:raise RuleError('Internal flip labor exceeds its remaining funded reserve. Add project reserve before continuing.')
            self.e.post(p.owner,job['id']+':labor-reserve:'+self.w.date,'Release funded internal flip labor',{'asset:flip_reserve':-labor_cost,'asset:cash':labor_cost})
            progress['reserve']-=labor_cost
        # Consume materials on the first actual work day, not on inspection.
        if not job.get('materials_used'):
            cost=job['materials'];job['prepaid']-=cost;job['materials_used']=True;job['actual_cost']+=cost
            self.e.post(p.owner,job['id']+':materials','Materials installed',{'asset:prepaid_works':-cost,('asset:property' if capital else 'expense:repairs'):cost})
            if capital:p.basis+=cost
        if job['provider']=='outside':
            labor_cost=effort*100;job['prepaid']-=labor_cost
            self.e.post(p.owner,job['id']+':labor:'+self.w.date,'Outside work delivered',{'asset:prepaid_works':-labor_cost,('asset:property' if capital else 'expense:repairs'):labor_cost})
            if capital:p.basis+=labor_cost
        elif labor_cost:
            provider=job['provider']
            if provider==p.owner:
                if capital:self.e.post(provider,job['id']+':capitalized:'+self.w.date,'Capitalize own qualified construction labor',{'asset:property':labor_cost,'expense:construction_labor_capitalized':-labor_cost});p.basis+=labor_cost
            else:
                self.e.post(p.owner,job['id']+':owner:'+self.w.date,'Internal work at actual cost',{('asset:property' if capital else 'expense:internal_services:'+provider):labor_cost,'liability:intercompany:'+provider:-labor_cost})
                self.e.post(provider,job['id']+':provider:'+self.w.date,'Allocate actual internal work cost',{'asset:intercompany:'+p.owner:labor_cost,('expense:construction_labor_capitalized' if capital else 'income:internal_services:'+p.owner):-labor_cost})
                if capital:p.basis+=labor_cost
        job['actual_cost']+=labor_cost;job['remaining']-=effort;job['labor_used']+=effort;job['quality']=quality
        if not capital:
            totals=self.s.setdefault('property_cost_totals',{}).setdefault(p.id,dict(holding=0,interest=0,repairs=0))
            totals['repairs']+=labor_cost+(job['materials'] if job['labor_used']==effort else 0)
        p.condition=max(1,p.condition) # Existing occupants retain their identity during disruption.
        if job['remaining']<=0:
            system=self.ensure(p)[job['system']]
            gain=job['gain']*max(30,quality)//100
            system['condition']=min(100,system['condition']+gain)
            if job['kind']=='replacement':system['age']=0
            system['maintained_until']=(date.fromisoformat(self.w.date)+timedelta(days=180)).isoformat()
            job.update(status='complete',completed=self.w.date,callback=quality<55 and stable_roll(self.w,job['id']+':callback')>quality)
            if job['callback']:system['condition']=max(5,system['condition']-10)
            p.condition=sum(x['condition'] for x in self.ensure(p).values())//len(SYSTEMS)
            self.s.setdefault('property_condition_baseline',{})[p.id]=p.condition
            if job['kind']=='conversion':
                use=job['use']
                if use in ('residential','commercial','industrial','office','mixed_use'):
                    p.category=use;p.specialization=[]
                    for index,space in enumerate(p.spaces):space['use']=('residential' if index%2 else 'commercial') if use=='mixed_use' else use
            if job['callback'] and job['provider']=='outside':
                self.s.setdefault('legal_claims',[]).append(dict(id=self.uid('warranty'),owner=p.owner,property_id=p.id,work_id=job['id'],amount=min(job['actual_cost'],job.get('outside_paid',job['actual_cost']))//3,status='open',created=self.w.date,fact='Completed contractor work requires a documented workmanship callback.'))
            self.e.event('Property work completed',f"{p.name}: {job['kind']} on {job['system']}, ${job['actual_cost']/100:,.2f} actual cost; workmanship {quality}/100."+(' A callback is required.' if job['callback'] else ''),True)

    def deliver(self,rules,b,buckets):
        from .qualified_capacity import TRADE_LICENSES, eligible, capacities, consume
        roles=('maintenance','tradesperson','builder','engineer','electrician','plumber','hvac_technician')
        for job in sorted((j for j in self.s.get('property_work',[]) if j['provider']==b.id and j['status']=='working'),key=lambda j:(j['kind']!='emergency',j['created'],j['id'])):
            p=self.e.get_property(job['property_id'])
            license_name=TRADE_LICENSES.get(job['system'])
            employees=[emp for emp in rules.staff(b.id) if rules.position(emp.position_id).role in roles and eligible(rules,emp,license_name) and rules.person(emp.person_id).skills.get('maintenance',0)>=job['qualification'] and (not job.get('assigned_staff') or emp.id in job['assigned_staff'])]
            capacity=capacities(rules,b,buckets,employees)
            available=sum(capacity.values());travel=30 if b.region!=p.region else 0
            effort=min(job['remaining'],max(0,available-travel))
            if not effort:continue
            used,cost,staff,quality=consume(rules,b,buckets,employees,effort+travel)
            if used<=travel:continue
            job['staff']=sorted(set(job.get('staff',[]))|set(staff))
            self.apply_work(job,used-travel,quality,cost)

    def tick(self):
        self.ensure_market_types()
        today=date.fromisoformat(self.w.date)
        for p in self.w.properties:
            if not p.owner or p.category=='land':continue
            facts=self.ensure(p);baseline=self.s.setdefault('property_condition_baseline',{}).get(p.id,p.condition)
            if baseline!=p.condition:
                for value in facts.values():value['condition']=max(1,min(100,value['condition']+p.condition-baseline))
            if today.day==1:
                for key,value in facts.items():
                    value['wear']+=1+(value['age']//15)+(1 if p.status in ('rented','managed','occupied') else 0)
                    if value['maintained_until']>=self.w.date:value['wear']=max(0,value['wear']-2)
                    if value['wear']>=6:value['condition']=max(1,value['condition']-1);value['wear']-=6
                    if today.month==1:value['age']+=1
                p.condition=sum(x['condition'] for x in facts.values())//len(SYSTEMS)
            self.s['property_condition_baseline'][p.id]=p.condition
        for job in self.s.get('property_work',[]):
            if job['status']=='working' and job['provider']=='outside':self.apply_work(job,min(240,job['remaining']),45+stable_roll(self.w,job['id']+':quality',51))
        for job in self.s.get('property_work',[]):
            if job['status']=='working' and job['provider']=='owner':
                self.apply_work(job,min(240,job['remaining']),min(90,50+self.s['owner_skills']['maintenance']//2))
        for vacancy in self.s.get('vacancies',[]):
            if vacancy['status']!='advertising' or vacancy['due']>self.w.date:continue
            p=self.e.get_property(vacancy['property_id']);space=next(s for s in p.spaces if s['id']==vacancy['space_id'])
            from .property_services import presentation
            market=max(10000,p.suggested_rent*space['area']//max(1,sum(s['area'] for s in p.spaces)))*presentation(self.w,p)//100
            if vacancy['asking']>market*150//100:
                vacancy['status']='no_interest'
                self.e.event('Vacancy needs repricing',p.name+': asking rent is too far above comparable space. Lower the ask and advertise again.',True);continue
            for index in range(3):
                key=vacancy['id']+':'+str(index);reliability=55+stable_roll(self.w,key+':reliability',45)
                rent=min(vacancy['asking'],market*105//100)*(90+index*8)//100
                self.s.setdefault('tenant_offers',[]).append(dict(id=self.uid('tenant-offer'),property_id=p.id,space_id=space['id'],name='Applicant '+key,rent=rent,max_rent=rent*103//100,reliability=reliability,area=space['area']*(70+stable_roll(self.w,key+':area',41))//100,months=(6,12,24)[index],improvement=(0,p.suggested_rent//2,p.suggested_rent)[index],status='open'))
            vacancy['status']='proposals';self.e.event('Tenant proposals received',p.name+' has three proposals with different reliability, space needs and concessions.',True)
        self.sales_tick()

    def sales_tick(self):
        from .finance_rules import Finance
        for listing in self.s.get('property_listings',{}).values():
            p=self.e.get_property(listing['property_id'])
            if listing['status']=='marketing' and listing['next_offer']<=self.w.date:
                listing['round']+=1;key=p.id+':offer:'+str(listing['round'])
                market=p.value*(85+stable_roll(self.w,key,26))//100
                listing['next_offer']=(date.fromisoformat(self.w.date)+timedelta(days=7)).isoformat()
                if listing['asking']>market*115//100:continue
                price=min(listing['asking'],market);offer=dict(id=self.uid('sale-offer'),price=price,concession=price*stable_roll(self.w,key+':concession',4)//100,finance_risk=10+stable_roll(self.w,key+':risk',26),status='open')
                listing['offers'].append(offer)
                self.e.event('Property offer received',p.name+f": ${price/100:,.2f}, subject to concessions and financing. Review before accepting.",True)
            if listing['status']=='closing' and listing['due']<=self.w.date:
                offer=next(o for o in listing['offers'] if o['id']==listing['accepted'])
                if stable_roll(self.w,offer['id']+':financing')<offer['finance_risk']:
                    offer['status']='failed';listing.update(status='marketing',next_offer=(date.fromisoformat(self.w.date)+timedelta(days=7)).isoformat())
                    self.e.event('Buyer financing failed',p.name+' returns to marketing. Holding costs continue; no sale income was booked.',True);continue
                owner=p.owner;gross=offer['price']-offer['concession']
                from .property_development import brokerage, use_representation
                fees=brokerage(self.w,p,owner,gross,3);net=gross-fees
                secured=[l for l in self.s['loans'] if l['entity']==owner and l.get('property_id')==p.id and l['status']=='active']
                debt=sum(l['principal']+l['interest_due'] for l in secured)
                leases=[l for l in self.s['leases'] if l['property_id']==p.id and l['status']=='active']
                deposits=sum(l['deposit_remaining'] for l in leases)
                arrears=sum(l['arrears'] for l in leases)
                if arrears>gross:
                    self.e.event('Property closing needs review',p.name+' has receivables exceeding the agreed price. Resolve collections before closing.',True);continue
                if net+self.w.cash(owner)<debt+deposits:
                    self.e.event('Property closing needs funds',p.name+' sale cannot clear its secured debt. Add capital before closing.',True);continue
                basis=p.basis
                buyer='external-property-buyer:'+offer['id']
                self.w.accounts.setdefault(buyer,{})
                capital=gross+p.upkeep*12
                self.e.post(buyer,offer['id']+':buyer-capital','Independent buyer acquisition capital',{'asset:cash':capital,'equity:capital':-capital})
                self.e.post(buyer,offer['id']+':buyer','Independent buyer acquired building; tenant businesses unchanged',{'asset:cash':-gross,'asset:property':gross-arrears,'asset:closing_receivables':arrears})
                use_representation(self.w,p,owner,gross*3//100,fees)
                self.e.post(owner,offer['id'],'Conditional property sale closed',{'asset:cash':net,'expense:selling':fees,'asset:property':-basis,'asset:closing_receivables':-arrears,'income:property_gain':-(gross-arrears-basis)})
                for lease in leases:
                    amount=lease['arrears'];lid=lease['id'];tenant=lease['tenant']
                    receivable='asset:rent_receivable:'+lid if tenant=='external' else 'asset:intercompany:'+tenant
                    if amount:
                        self.e.post(owner,offer['id']+':assign:'+lid,'Assign existing lease receivable at closing',{'asset:closing_receivables':amount,receivable:-amount})
                        self.e.post(buyer,offer['id']+':receive:'+lid,'Existing tenant receivable acquired',{'asset:closing_receivables':-amount,receivable:amount})
                        if tenant!='external':self.e.post(tenant,offer['id']+':counterparty:'+lid,'Existing rent obligation follows landlord transfer',{'liability:intercompany:'+owner:amount,'liability:intercompany:'+buyer:-amount})
                    deposit=lease['deposit_remaining']
                    if deposit:
                        self.e.post(owner,offer['id']+':deposit:'+lid,'Transfer tenant deposit liability and cash',{'asset:cash':-deposit,'liability:deposit:'+lid:deposit})
                        self.e.post(buyer,offer['id']+':deposit:'+lid,'Receive protected tenant deposit',{'asset:cash':deposit,'liability:deposit:'+lid:-deposit})
                    lease['history'].append(dict(date=self.w.date,from_owner=owner,to_owner=buyer,event='Landlord transfer; tenant ownership unchanged'))
                    lease['owner']=buyer
                for loan in secured:Finance(self.e).action('repay_loan',dict(entity=owner,loan_id=loan['id'],amount=loan['principal']+loan['interest_due']),offer['id']+':debt:'+loan['id'])
                totals=self.s.get('property_cost_totals',{}).get(p.id,{})
                other=sum(totals.values())+self.s.get('inspections',{}).get(p.id,{}).get('cost',0)
                listing.update(status='sold',sold=self.w.date,proceeds=net,principal_and_interest=debt,project_profit=gross-fees-basis-other-arrears,cash_returned=net-debt-deposits,deposit_transfer=deposits,receivables_transferred=arrears)
                p.owner=buyer;p.status='managed' if leases else 'rented' if p.status=='rented' else 'vacant';p.basis=gross-arrears
                self.s.setdefault('outside_property_owners',{})[buyer]=dict(name='Independent property buyer',property_id=p.id)
                progress=self.s.get('flip_progress',{}).get(p.id)
                if progress:
                    unused=progress['reserve']
                    if unused:self.e.post(owner,offer['id']+':reserve','Return unused project reserve',{'asset:flip_reserve':-unused,'asset:cash':unused})
                    progress.update(reserve=0,phase='sold');listing['unused_reserve_returned']=unused
                self.e.event('Property sale closed',p.name+f": project result ${listing['project_profit']/100:,.2f}; cash after secured debt ${listing['cash_returned']/100:,.2f}.",True)
