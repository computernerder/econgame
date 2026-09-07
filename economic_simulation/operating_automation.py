"""Default routine proposals and explicit overrides use the same authority boundary."""
from datetime import date,timedelta
from .campaign import Campaign,flag,integer
from .domain import RuleError
from .manager_defaults import limits as manager_limits
from .authority import Authority
from .leadership import Leadership
from .manager_defaults import automation

FLAGS=('pricing','scheduling','staff_reductions','property_operations','prefer_internal_property','service_renewals','locations','financing','flipping')


class OperatingAutomation(Campaign):
    def action(self,args):
        bid=self.require(args.get('business_id',''))
        if not any(b.id==bid for b in self.w.businesses):raise RuleError('Choose a business operation.')
        policy=self.s.setdefault('operating_automation',{}).setdefault(bid,{})
        for field in FLAGS:
            if field in args:policy[field]=flag(args[field])
        if 'location_limit' in args:policy['location_limit']=integer(args['location_limit'],1,20)
        for key,default,maximum in [('loan_limit',1000000,1000000000),('flip_limit',1,10),('flip_capital',10000000,1000000000),('flip_downside',0,1000000000)]:
            if key in args:policy[key]=integer(args[key],0,maximum)
        if 'service_roles' in args:policy['service_roles']=[x.strip() for x in str(args['service_roles']).split(',') if x.strip()]
        from .service_office import DEPARTMENTS
        if any(role not in DEPARTMENTS for role in policy.get('service_roles',[])):raise RuleError('Choose supported service departments.')
        return 'Routine proposals enabled as selected. Each decision still requires an available leader, scope, permission, budget and uncommitted cash.'

    def tick(self):
        from .routine_management import RoutineManagement
        RoutineManagement(self.e).tick()
        from .business_models import SUPPORT_ROLES
        from .service_office import DEPARTMENTS
        leader=Leadership(self.e);authority=Authority(self.e)
        for b in self.w.businesses[:]:
            if b.status!='operating' or not self.controlled(b.id):continue
            policy=automation(self.w,b)
            record,actor=leader.actor(b)
            if not actor or not policy:continue
            limit=manager_limits(b)['purchasing_limit']
            if policy.get('property_operations'):self.properties(b,leader,limit)
            if policy.get('flipping'):self.flips(b,leader,limit,policy)
            if policy.get('financing') and not any(l['entity']==b.id and l['status']=='active' and l.get('created')==self.w.date for l in self.s['loans']):
                from .authority import cash_forecast
                needed=max(0,-cash_forecast(self.w,b.id,14)['available'])
                if needed>=10000 and needed<=policy['loan_limit']:
                    leader.perform(b,'working-capital','borrow',dict(entity=b.id,amount=needed,months=24),needed,needed<=limit,'Propose finite working-capital credit without collateral or parent guarantee; actual lender underwriting applies.')
            if policy.get('service_renewals'):
                for role in policy.get('service_roles',[]):
                    effect=self.s.get('service_effects',{}).get(b.id,{}).get(role,{})
                    if effect.get('expires','')>=self.w.date:continue
                    if any(t['recipient']==b.id and t['department']==role and t['status']=='complete' and t.get('completed','')>=(date.fromisoformat(self.w.date)-timedelta(days=30)).isoformat() for t in self.s.get('service_tasks',[])):continue
                    if any(t['recipient']==b.id and t['department']==role and t['status'] in ('queued','working') for t in self.s.get('service_tasks',[])):continue
                    providers=[d for d in self.s.get('departments',{}).values() if d['role']==role and b.region in d['regions']]
                    provider=providers[0]['provider'] if providers else 'outside'
                    cost=0 if provider!='outside' else DEPARTMENTS[role][1]*150
                    args=dict(recipient=b.id,provider=provider,mode='outside' if provider=='outside' else 'internal',department=role,matter='template' if role=='legal' else 'routine')
                    if role=='it' and self.s.get('deployed_systems',{}).get(b.id):
                        if min(s['condition'] for s in self.s['deployed_systems'][b.id].values())>60:continue
                        from .service_products import PRODUCTS
                        args['product']='system_support'
                        cost=0 if provider!='outside' else PRODUCTS['system_support'][2]*150
                    if role=='training':
                        staff=leader.rules.staff(b.id)
                        if not staff:continue
                        args['target_id']=min(staff,key=lambda e:sum(leader.rules.person(e.person_id).skills.values())).id
                    leader.perform(b,'service:'+role,'service_request',args,cost,cost<=limit,'Renew '+role+' service coverage through actual queued work.')
            from .restaurant import active as restaurant_active,settings as restaurant_settings
            dining=restaurant_active(self.w,b)
            if dining and policy.get('scheduling'):
                plan=restaurant_settings(self.w,b)
                roster=sorted(e.id for e in leader.rules.staff(b.id))
                if plan.get('rota_requested') or plan.get('scheduled_roster')!=roster or date.fromisoformat(self.w.date).weekday()==0:
                    from .restaurant_staffing import auto_schedule
                    auto_schedule(leader,b)
                    self.s['restaurants'][b.id]['scheduled_roster']=roster
            if date.fromisoformat(self.w.date).weekday()!=0:continue
            if policy.get('pricing') and b.industry in ('retail','boutique','restaurant','grocery','gas_station','car_dealership'):
                day=b.last_day;price=b.price_percent
                if day.get('output',0)>=day.get('capacity',1) and day.get('demand',0)>day.get('capacity',0):price=min(115,price+2)
                elif day.get('output',0)<day.get('capacity',0)//2:price=max(85,price-2)
                if price!=b.price_percent:leader.perform(b,'pricing','business_policy',dict(business_id=b.id,price_percent=price,benefits=b.benefits,auto_restock=b.auto_restock),0,True,f'Adjust prices to {price}% from observed demand and capacity.')
            if policy.get('scheduling') and not dining:
                for emp in leader.rules.staff(b.id):
                    if emp.id==actor.id or emp.shift_start==8:continue
                    leader.perform(b,'schedule:'+emp.id,'employment_terms',dict(employment_id=emp.id,amount=emp.salary,weekly_hours=emp.weekly_hours,shift_start=8),0,True,'Align '+leader.rules.person(emp.person_id).name+' with operating coverage; preserve pay and hours.')
            if policy.get('staff_reductions'):
                staff=leader.rules.staff(b.id);target=b.authority.get('staffing_target',len(staff))
                optional=[emp for emp in staff if emp.id!=actor.id and leader.rules.position(emp.position_id).role in SUPPORT_ROLES]
                if len(staff)>target and optional:
                    emp=optional[-1];cost=emp.salary*12//52
                    leader.perform(b,'reduce:'+emp.id,'end_employment',dict(employment_id=emp.id),cost,cost<=limit,'Reduce optional support staffing to the owner’s selected target; severance paid and earned wages retained.')
            if policy.get('locations'):
                from .management import policy as business_policy
                from .expansion import Expansion
                strategy_record,_=leader.actor(b,'start_location')
                grants=authority.grants(b,strategy_record)
                contract=grants[0][1] if grants else {}
                if contract.get('objective')!='growth' or b.capacity_percent<160:continue
                if 'locations' not in self.s.get('operating_automation',{}).get(b.id,{}) and business_policy(b,self.w)['growth']!='auto':continue
                from .management import growth_status
                growth=growth_status(self.w,b)
                if growth['profit']<=0:continue
                if 'locations' not in self.s.get('operating_automation',{}).get(b.id,{}) and (growth['operating_days']<14 or not growth['utilized']):continue
                count=1+sum(child.owner==b.id and child.industry==b.industry and child.status!='closed' for child in self.w.businesses)
                if count>=policy['location_limit']:continue
                quote=Expansion(self.e).opening_quote(b.industry)
                name=b.name+' · location '+str(count+1)
                leader.perform(b,'location:'+str(count+1),'start_location',dict(entity=b.id,name=name,region=b.region),quote['total'],quote['total']<=limit,'Proposed another same-industry location with separately funded setup and working capital; hire required roles before opening.')

    def flips(self,b,leader,limit,policy):
        from .property_operations import PropertyOperations
        from .internal_property_services import InternalPropertyServices
        internal=InternalPropertyServices(self.e)
        for pid,budget in self.s.get('flip_budgets',{}).items():
            if budget['entity']!=b.id:continue
            p=self.e.get_property(pid);progress=self.s.get('flip_progress',{}).get(pid)
            active=[r for r in self.s.get('flip_progress',{}).values() if r['entity']==b.id and r['phase']!='sold']
            if p.status=='market':
                total=self.e.quote('buy',pid,b.id)['total']+budget['renovation']+budget['contingency']+budget['holding']
                if len(active)>=policy['flip_limit'] or total+sum(r['committed'] for r in active)>policy['flip_capital'] or budget['profit_low'] < -policy['flip_downside']:continue
                if pid not in self.s.get('inspections',{}):
                    leader.perform(b,'inspect-flip:'+pid,'inspect_property',dict(property_id=pid,entity=b.id),35000,35000<=limit,'Inspect an existing planned flip before any acquisition.');continue
                if not internal.prepare_closing(b,p,leader,limit):continue
                leader.perform(b,'fund-flip:'+pid,'fund_flip',dict(property_id=pid,entity=b.id),total,total<=limit,'Acquire a planned flip with renovation, contingency and holding reserves escrowed.');continue
            if p.owner!=b.id or not progress or progress['phase']=='sold':continue
            if progress['phase']=='funded':
                if budget['renovation']:
                    provider=internal.repair(b,p,'interior','cosmetic')
                    leader.perform(b,'work-flip:'+pid,'flip_work',dict(property_id=pid,provider=provider['provider'],assigned_staff=provider.get('assigned_staff','')),0,provider['cost']<=progress['reserve'],'Use the funded project reserve for interior work; overruns need additional owner approval. '+provider['reason'])
                else:progress['phase']='ready'
            jobs=[j for j in self.s.get('property_work',[]) if j['property_id']==pid]
            if progress['phase']=='working' and jobs and all(j['status']=='complete' for j in jobs):progress['phase']='ready'
            if progress['phase']=='ready':
                if not internal.prepare_closing(b,p,leader,limit):continue
                if leader.perform(b,'market-flip:'+pid,'market_property',dict(property_id=pid,asking=p.value),0,True,'Market the completed flip using current comparable value; no guaranteed buyer.'):progress['phase']='marketing'
            listing=self.s.get('property_listings',{}).get(pid,{})
            if listing.get('status')=='marketing':
                offers=[o for o in listing['offers'] if o['status']=='open']
                if offers:
                    if not internal.prepare_closing(b,p,leader,limit):continue
                    offer=max(offers,key=lambda o:(o['price']-o['concession'])*(100-o['finance_risk']))
                    leader.perform(b,'sell-flip:'+offer['id'],'accept_property_offer',dict(property_id=pid,offer_id=offer['id']),0,True,'Accept the strongest net offer after financing risk, subject to the sale authority policy.')

    def review_new_requests(self):
        """Handle tenant questions raised after the morning operating review."""
        leader=Leadership(self.e)
        for b in self.w.businesses:
            if b.status=='operating' and self.controlled(b.id) and automation(self.w,b).get('property_operations') and leader.actor(b)[1]:
                self.properties(b,leader,manager_limits(b)['purchasing_limit'],requests_only=True)

    def properties(self,b,leader,limit,requests_only=False):
        from .property_operations import systems_for,PropertyOperations
        from .internal_property_services import InternalPropertyServices
        internal=InternalPropertyServices(self.e)
        for p in self.w.properties:
            if p.owner!=b.id or p.category=='land' or p.status in ('sold','expired'):continue
            # Recurring care uses RoutineManagement's policy and cumulative
            # budget. Explicit repair/leasing opt-outs remain separate policies.
            requests=[r for r in self.s.get('property_requests',[]) if r['property_id']==p.id and r['status'] in ('open','overdue')]
            for request in sorted(requests,key=lambda r:r['due']):
                if any(j['property_id']==p.id and j['system']==request['system'] and j['status']=='working' for j in self.s.get('property_work',[])):continue
                kind='emergency' if request['severity']=='urgent' else 'repair'
                provider=internal.repair(b,p,request['system'],kind)
                if leader.perform(b,'tenant-request:'+request['id'],'respond_property_request',dict(property_id=p.id,request_id=request['id'],kind=kind,provider=provider['provider'],assigned_staff=provider.get('assigned_staff','')),provider['cost'],provider['cost']<=limit,'Repair the reported '+request['system']+' problem before '+request['due']+'. '+provider['reason']):
                    self.e.pause_reasons[:]=[r for r in self.e.pause_reasons if not (r['title']=='Tenant maintenance request' and r.get('request_id')==request['id'])]
                    for event in self.e.events:
                        if event['title']=='Tenant maintenance request' and event.get('request_id')==request['id']:
                            event.update(pause_suppressed=True,handled_by=leader.rules.person(leader.actor(b)[1].person_id).name)
            if requests_only:continue
            if self.s.get('property_listings',{}).get(p.id,{}).get('status') in ('marketing','closing'):
                internal.prepare_closing(b,p,leader,limit)
            for space in p.spaces:
                lease=next((l for l in self.s['leases'] if l['space_id']==space['id'] and l['status']=='active'),None)
                if lease:
                    if lease['end_date']<=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat():
                        leader.perform(b,'renew:'+lease['id'],'renew_property_lease',dict(property_id=p.id,lease_id=lease['id'],rent=lease['rent']),0,True,'Renew an expiring lease at current rent under the approved legal template.')
                    continue
                offers=[o for o in self.s.get('tenant_offers',[]) if o['space_id']==space['id'] and o['status']=='open' and o['area']<=space['area']]
                if offers:
                    from .simulation_support import stable_roll
                    judgment=leader.judgment(b);_,employee=leader.actor(b)
                    incentive=employee.compensation.get('commission_percent',0) if employee else 0
                    def assessed(o):
                        uncertainty=(100-judgment)//3
                        reliability=max(1,min(100,o['reliability']+stable_roll(self.w,o['id']+':assessment:'+employee.id,uncertainty*2+1)-uncertainty))
                        return o['rent']*(reliability+incentive)//100-o['improvement']//o['months']
                    offer=max(offers,key=assessed)
                    leader.perform(b,'tenant:'+space['id'],'accept_tenant',dict(property_id=p.id,offer_id=offer['id'],rent=offer['rent']),offer['improvement'],offer['improvement']<=limit,'Select tenant by expected collections after concessions, not highest headline rent.')
                elif not any(v['space_id']==space['id'] and v['status']=='advertising' for v in self.s.get('vacancies',[])):
                    leader.perform(b,'vacancy:'+space['id'],'advertise_space',dict(property_id=p.id,space_id=space['id'],rent=p.suggested_rent//max(1,len(p.spaces))),15000,15000<=limit,'Advertise a vacant unit and compare tenant proposals.')
            worst=min(systems_for(self.w,p),key=lambda key:systems_for(self.w,p)[key]['condition'])
            if systems_for(self.w,p)[worst]['condition']<30 and not any(j['property_id']==p.id and j['system']==worst and j['status']=='working' for j in self.s.get('property_work',[])):
                provider=internal.repair(b,p,worst,'emergency')
                leader.perform(b,'repair:'+p.id+':'+worst,'property_work',dict(property_id=p.id,system=worst,kind='emergency',provider=provider['provider'],assigned_staff=provider.get('assigned_staff','')),provider['cost'],provider['cost']<=limit,'Emergency '+worst+' work. '+provider['reason'])
