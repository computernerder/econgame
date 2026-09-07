"""Finite service queues, outside expertise and documented work products."""
from datetime import date,timedelta
from .campaign import Campaign,integer
from .domain import RuleError,daily_share,GAME_RULES
from .simulation_support import stable_roll

DEPARTMENTS={
 'real_estate_agent':('Property closing representation',960,'service'),
 'hr':('Recruiting and onboarding',480,'leadership'),
 'it':('Systems integration and support',960,'technology'),
 'maintenance':('Preventive equipment service',720,'maintenance'),
 'legal':('Contract negotiation',1200,'legal'),
 'accounting':('Reconciled management report',480,'finance'),
 'finance':('Cash forecast and financing comparison',600,'finance'),
 'purchasing':('Supplier contract',720,'logistics'),
 'logistics':('Delivery coordination',600,'logistics'),
 'marketing':('Customer research and campaign',960,'retail'),
 'training':('Employee development',960,'leadership')}


class ServiceOffice(Campaign):
    def action(self,action,args,source):
        from .business_rules import BusinessRules
        rules=BusinessRules(self.e)
        if action=='close_legal_claim':
            from .legal_recovery import close_claim
            return close_claim(self.e,args)
        if action=='department_configure':
            provider=rules.company(args.get('provider',''))
            role=args.get('department','')
            if role not in DEPARTMENTS:raise RuleError('Choose a service department.')
            staff=[x.strip() for x in str(args.get('staff','')).split(',') if x.strip()]
            for eid in staff:
                emp=rules.contract(eid)
                if emp.employer!=provider.id or rules.position(emp.position_id).role!=role:
                    raise RuleError('Assign employees in this department role at the service provider.')
            tools=integer(args.get('tools',1),0 if role=='real_estate_agent' and provider.industry=='office' else 1,3)
            key=provider.id+':'+role
            old=self.s.get('departments',{}).get(key,{})
            expense=max(0,tools-old.get('tools',0))*50000
            if expense:self.e.post(provider.id,source,'Service tools and deployment',{'asset:cash':-expense,'expense:service_tools':expense})
            self.s.setdefault('departments',{})[key]=dict(id=key,provider=provider.id,role=role,staff=staff,
                tools=tools,regions=[x.strip() for x in str(args.get('regions',provider.region)).split(',') if x.strip()],
                industries=[x.strip() for x in str(args.get('industries',provider.industry)).split(',') if x.strip()],
                last_capacity=0,last_used=0,last_cost=0,leader=args.get('leader',''))
            return 'Department configured. Tools cost cash; employees and queued work are still required to deliver services.'
        if action=='service_request':
            recipient=self.require(args.get('recipient','personal'))
            role=args.get('department','')
            if role not in DEPARTMENTS:raise RuleError('Choose a supported service.')
            provider=args.get('provider','outside');mode=args.get('mode','internal' if provider!='outside' else 'outside')
            if mode not in ('internal','outside','mixed'):raise RuleError('Choose internal, outsourced or mixed delivery.')
            if mode=='outside':provider='outside'
            automatic_department=None
            if mode!='outside' and provider+':'+role not in self.s.get('departments',{}):
                from .internal_property_services import agent_department
                company=rules.company(provider)
                if role=='real_estate_agent':automatic_department=agent_department(self.w,company)
                if automatic_department is None:raise RuleError('Configure the delivering department first.')
            if provider!='outside':self.require(provider)
            target=args.get('target_id','')
            matter=args.get('matter','routine')
            # Irrelevant fields from old screens must not pollute saved work.
            if role!='legal':matter='routine'
            if not args.get('product'):
                if role=='training':
                    emp=next((e for e in self.w.employments if e.id==target and e.employer==recipient and e.status=='active'),None)
                    if not emp:raise RuleError('Select an active employee at the receiving business for development.')
                elif role!='legal' or matter=='template':target=''
            if role=='legal' and matter not in ('negotiation','collection','template','dispute') and args.get('product') not in ('transaction_review','transfer_consent'):raise RuleError('Choose a legal work product.')
            if role=='legal' and matter in ('collection','dispute'):
                from .customer_collections import overdue, busy
                business=next((b for b in self.w.businesses if b.id==recipient),None)
                invoice=next((r for r in business.receivables if r['id']==target),None) if business else None
                if not invoice:
                    claim=any(c['id']==target and c['owner']==recipient and c['status']=='open' for c in self.s.get('legal_claims',[]))
                    lease=any(l['id']==target and l['owner']==recipient and l['tenant']=='external' and l['arrears']>0 for l in self.s.get('leases',[]))
                    if not claim and not lease:raise RuleError('Select an existing overdue invoice, rent balance or open claim belonging to the receiving account.')
                if invoice:
                    if not overdue(self.w,invoice):raise RuleError('This customer invoice is not overdue.')
                    if busy(self.w,recipient,invoice):raise RuleError('This invoice already has recovery in progress.')
                    if any(t['recipient']==recipient and t['target_id']==target and t['department']=='legal' and t['matter'] in ('collection','dispute') and t['status']=='complete' for t in self.s.get('service_tasks',[])):
                        raise RuleError('Legal already completed its collection attempt on this invoice. Review the outcome and choose another recovery option.')
            original=None
            if role=='legal' and matter=='negotiation':
                listing=next((b for b in self.w.businesses if b.id==target and b.status=='market' and not b.owner),None)
                prop=next((p for p in self.w.properties if p.id==target and p.status=='market'),None)
                if not listing and not prop:raise RuleError('Select an available business or property offer.')
                original=(listing or prop).asking
                if any(t['target_id']==target and t['matter']=='negotiation' for t in self.s.get('service_tasks',[])):
                    raise RuleError('This offer already has a negotiation record; the same counterparty cannot be rerolled.')
            task=dict(id=self.uid('service'),provider=provider,recipient=recipient,department=role,mode=mode,
                priority=integer(args.get('priority',2),1,5),effort=DEPARTMENTS[role][1],remaining=DEPARTMENTS[role][1],
                due=(date.fromisoformat(self.w.date)+timedelta(days=integer(args.get('days',14),1,180))).isoformat(),
                created=self.w.date,status='queued',outcome='',target_id=target,matter=matter,
                original_offer=original,staff=[],worked=0,internal_cost=0,outside_cost=0,recovered=0,improvement=0)
            from .service_products import ServiceProducts
            ServiceProducts(self.e).prepare(task,args)
            # Outside specialists are reserved and prepaid; unused balance is an asset.
            from .supplier_contracts import SupplierContracts
            from .legal_recovery import check_recovery
            contract=SupplierContracts(self.e).available_contract(task)
            rate=contract['rate'] if contract else 150
            check_recovery(self.w,task,task['effort']*rate if mode in ('outside','mixed') else 0,new=True)
            reserved=SupplierContracts(self.e).reserve(task,source)
            if mode in ('outside','mixed') and not reserved:
                prepaid=task['effort']*150
                self.e.post(recipient,source,'Reserve outside specialist capacity',{'asset:cash':-prepaid,'asset:prepaid_services':prepaid})
                task['prepaid']=prepaid
            if automatic_department is not None:self.s.setdefault('departments',{})[automatic_department['id']]=automatic_department
            self.s.setdefault('service_tasks',[]).append(task)
            return f"Service queued: {task['effort']/60:g} qualified hours, due {task['due']}. Work competes for staff time; completion is not guaranteed by the deadline."
        if action=='cancel_service':
            task=next((t for t in self.s.get('service_tasks',[]) if t['id']==args.get('task_id') and t['status'] in ('queued','working')),None)
            if not task:raise RuleError('Choose unfinished service work.')
            self.require(task['recipient'])
            refund=task.get('prepaid',0)
            from .supplier_contracts import SupplierContracts
            if SupplierContracts(self.e).release(task,source):
                task.update(status='cancelled',cancelled=self.w.date,outcome='Cancelled. Unused prepaid block minutes returned to the agreement if still valid; expired credits expensed. No cash refund.')
                return task['outcome']
            if refund:self.e.post(task['recipient'],source,'Cancelled service: unused outside reserve returned',{'asset:prepaid_services':-refund,'asset:cash':refund})
            task.update(status='cancelled',cancelled=self.w.date,prepaid=0,outcome='Cancelled. Delivered work remains an expense; unused outside reserves refunded.')
            return f'Unfinished work cancelled; ${refund/100:,.2f} unused reserve refunded. No completed work product granted.'
        if action=='service_priority':
            task=next((t for t in self.s.get('service_tasks',[]) if t['id']==args.get('task_id')),None)
            if not task:raise RuleError('Choose a queued task.')
            self.require(task['recipient']);task['priority']=integer(args.get('priority',2),1,5)
            return 'Queue priority updated; completed work and incurred costs are retained.'
        if action=='outsource_service':
            task=next((t for t in self.s.get('service_tasks',[]) if t['id']==args.get('task_id') and t['status'] in ('queued','working')),None)
            if not task:raise RuleError('Choose unfinished service work.')
            if task.get('supplier_contract'):raise RuleError('This task already reserves contracted outside capacity. Cancel it before changing suppliers; expired credits are not refundable.')
            self.require(task['recipient'])
            from .legal_recovery import check_recovery
            check_recovery(self.w,task,task['remaining']*150)
            needed=max(0,task['remaining']*150-task.get('prepaid',0))
            if needed:self.e.post(task['recipient'],source,'Reserve replacement outside specialists',{'asset:cash':-needed,'asset:prepaid_services':needed})
            task['prepaid']=task.get('prepaid',0)+needed;task['mode']='outside'
            return 'Remaining work reassigned to reserved outside specialists. Prior work, staff time and costs remain recorded.'
        raise RuleError('Unknown service command.')

    def deliver(self,rules,b,buckets):
        from .workforce import Workforce
        from .time_off import absent
        from .qualified_capacity import eligible, capacities, consume
        if b.industry=='office' and b.status not in ('operating','independent'):
            for dept in self.s.get('departments',{}).values():
                if dept['provider']==b.id:dept.update(last_capacity=0,last_used=0,last_cost=0)
            return
        for dept in self.s.get('departments',{}).values():
            if dept['provider']!=b.id:continue
            role=dept['role'];values=buckets.get(role,[0]*24)
            qualified=[emp for emp in rules.staff(b.id) if rules.position(emp.position_id).role==role
                       and (not dept['staff'] or emp.id in dept['staff']) and date.fromisoformat(self.w.date).weekday() in emp.days
                       and not absent(self.w,emp) and eligible(rules,emp)]
            capacity=min(sum(values),sum(capacities(rules,b,buckets,qualified).values()))
            dept.update(last_capacity=capacity,last_used=0,last_cost=0)
            if not qualified:continue
            quality=sum(rules.person(emp.person_id).skills.get(DEPARTMENTS[role][2],30) for emp in qualified)//len(qualified)
            tasks=sorted((t for t in self.s.get('service_tasks',[]) if t['provider']==b.id and t['department']==role and t['status'] in ('queued','working') and t['mode']!='outside'),key=lambda t:(t['priority'],t['due'],t['id']))
            for task in tasks:
                if task['remaining']<=0:continue
                if not self.recovery_allowed(task):continue
                recipient=next((x for x in self.w.businesses if x.id==task['recipient']),None)
                prop=next((x for x in self.w.properties if x.id==task['target_id']),None)
                region=prop.region if prop and task.get('product')=='property_representation' else recipient.region if recipient else prop.region if prop else b.region
                if region not in dept['regions']:continue
                travel=30 if region!=b.region else 0
                if capacity<=travel:continue
                expertise=100 if not recipient or recipient.industry in dept['industries'] else 65
                speed=max(30,quality)*expertise*(80+dept['tools']*20)//10000
                used=min(capacity,max(travel+1,(task['remaining']*100+max(1,speed)-1)//max(1,speed)+travel))
                progress=min(task['remaining'],(used-travel)*speed//100)
                if progress<=0:continue
                if task['department']=='legal' and task['matter'] in ('collection','dispute'):
                    from .qualified_capacity import estimated_cost
                    if not self.recovery_allowed(task,estimated_cost(rules,b,buckets,qualified,used)):continue
                capacity-=used;dept['last_used']+=used
                actual,cost,used_staff,_=consume(rules,b,buckets,qualified,used)
                if 'labor_remaining' in task:task['labor_remaining']=max(0,task['labor_remaining']-actual)
                if task['recipient']!=b.id and cost:
                    self.e.post(task['recipient'],task['id']+':'+self.w.date,'Internal service delivery',{'expense:internal_services:'+b.id:cost,'liability:intercompany:'+b.id:-cost})
                    self.e.post(b.id,task['id']+':'+self.w.date,'Internal service cost allocation',{'income:internal_services:'+task['recipient']:-cost,'asset:intercompany:'+task['recipient']:cost})
                task['internal_cost']+=cost;dept['last_cost']+=cost
                task['staff']=sorted(set(task['staff'])|set(used_staff))
                self.progress(task,progress,quality)

    def recovery_allowed(self,task,additional=0):
        from .legal_recovery import check_recovery
        try:
            check_recovery(self.w,task,additional+(task['remaining']*task.get('outside_rate',150) if task['mode'] in ('outside','mixed') else 0))
            return True
        except RuleError as error:
            self.action('cancel_service',dict(task_id=task['id']),task['id']+':recovery-guard')
            task['outcome']+=' '+str(error)
            self.e.event('Recovery spending stopped',task['outcome'],True)
            return False

    def progress(self,task,effort,quality):
        task['remaining']-=effort;task['worked']+=effort;task['status']='working'
        task['quality']=quality
        from .service_products import ServiceProducts
        if task['remaining']<=0 and ServiceProducts(self.e).ready(task):
            task.update(status='complete',completed=self.w.date,quality=quality)
            self.finish(task,quality)
            self.e.event('Service work completed',task['id']+': '+task['outcome'])

    def tick(self):
        from .supplier_contracts import SupplierContracts
        suppliers=SupplierContracts(self.e);suppliers.tick()
        for task in sorted(self.s.get('service_tasks',[]),key=lambda t:(t['priority'],t['due'],t['id'])):
            if task['status']=='complete' and task.get('prepaid',0):
                remaining=task['prepaid'];task['prepaid']=0
                self.e.post(task['recipient'],task['id']+':refund','Unused outside capacity refunded',{'asset:prepaid_services':-remaining,'asset:cash':remaining})
            if task['status'] not in ('queued','working'):continue
            if not self.recovery_allowed(task):continue
            if task['mode'] in ('outside','mixed') and task['remaining']>0:
                used=min(suppliers.capacity(task),task['remaining']);cost=used*task.get('outside_rate',150)
                if used:
                    self.e.post(task['recipient'],task['id']+':outside:'+self.w.date,'Outside specialist work delivered',{'asset:prepaid_services':-cost,'expense:outside_services':cost})
                    task['prepaid']-=cost;task['outside_cost']+=cost;suppliers.delivered(task,used);self.progress(task,used,75)
            if task['status'] in ('queued','working') and task['remaining']==0:
                self.progress(task,0,task.get('quality',50))
            if task['status']=='complete' and task.get('prepaid',0):
                remaining=task['prepaid'];task['prepaid']=0
                self.e.post(task['recipient'],task['id']+':refund','Unused outside capacity refunded',{'asset:prepaid_services':-remaining,'asset:cash':remaining})
            if task['due']<self.w.date and not task.get('overdue_notified') and task['status']!='complete':
                task['overdue_notified']=True
                self.e.event('Service deadline missed',task['id']+' has '+str(task['remaining'])+' minutes still queued. Reprioritize, add qualified staff or outsource.',True)

    def finish(self,task,quality):
        from .service_products import ServiceProducts
        if ServiceProducts(self.e).finish(task,quality):return
        role=task['department'];recipient=task['recipient'];target=task['target_id']
        b=next((b for b in self.w.businesses if b.id==recipient),None)
        if role=='legal':
            self.legal_result(task,quality)
            invoice=next((r for r in b.receivables if r['id']==target),None) if b else None
            if invoice:
                self.e.event('Customer recovery needs review',b.name+' · '+target+': '+task['outcome'],True,financial_amount=invoice['amount'],invoice_id=invoice['id'])
            return
        if role=='accounting':
            from .business_views import group_profit
            cutoff=(date.fromisoformat(self.w.date)-timedelta(days=29)).isoformat()
            accounts={}
            if not b:cutoff=self.w.date[:7]+'-01'
            history=b.financial_days if b else {cutoff:self.s.get('monthly_financials',{}).get(recipient,{}).get(self.w.date[:7],{})}
            for day,values in history.items():
                if day>=cutoff:
                    for key,value in values.items():accounts[key]=accounts.get(key,0)+value
            revenue=-sum(v for k,v in accounts.items() if k.startswith('income:'));expenses=sum(v for k,v in accounts.items() if k.startswith('expense:'))
            ledger=self.w.accounts[recipient]
            self.s.setdefault('management_reports',[]).append(dict(id=task['id'],business_id=recipient,name=b.name if b else recipient.title()+' portfolio',date=self.w.date,from_date=cutoff,revenue=revenue,expenses=expenses,profit=revenue-expenses,margin=round((revenue-expenses)*100/max(1,revenue),1),cash=self.w.cash(recipient),receivables=sum(v for k,v in ledger.items() if k.startswith(('asset:receivable','asset:rent_receivable'))),payroll=-ledger.get('liability:payroll',0),inventory=ledger.get('asset:inventory',0),runway=round(self.w.cash(recipient)*30/max(1,expenses),1)))
            task['outcome']='Reconciled actual ledger activity from '+cutoff+' through '+self.w.date+'.'
        elif role=='finance':
            from .authority import cash_forecast
            task['forecast']=cash_forecast(self.w,recipient)
            task['proposals']=[]
            amount=max(0,-task['forecast']['available'])
            if amount>=10000:
                import copy
                from .domain import Engine
                from .finance_rules import Finance
                for lender in [None]+[bank.id for bank in Finance(self.e).owned_banks(recipient)]:
                    for months in (24,60):
                        trial=Engine(copy.deepcopy(self.w))
                        try:
                            Finance(trial).action('borrow',dict(entity=recipient,amount=amount,months=months,lender=lender),'financing-proposal')
                            loan=trial.world.systems['loans'][-1]
                            task['proposals'].append(dict(lender=lender or 'Outside lender',principal=amount,months=months,rate_bps=loan['rate_bps'],estimated_interest=amount*loan['rate_bps']*(months+1)//240000))
                        except RuleError:continue
            task['outcome']=f"Cash forecast completed: ${task['forecast']['available']/100:,.2f} after known commitments. {len(task['proposals'])} finance alternatives passed today's underwriting; no loan committed. Rates, capital and approval are checked again when borrowing."
        elif role=='training':
            emp=next((e for e in self.w.employments if e.id==target and e.employer==recipient and e.status=='active'),None)
            if not emp:task['outcome']='Training could not be delivered: the selected employee is no longer available.';return
            person=next(p for p in self.w.people if p.id==emp.person_id)
            from .business_models import ROLE_SKILLS
            position=next(p for p in self.w.positions if p.id==emp.position_id);skill=ROLE_SKILLS[position.role]
            person.skills[skill]=min(100,person.skills.get(skill,30)+max(1,quality//20))
            if skill not in person.demonstrated:person.demonstrated.append(skill)
            task['outcome']='Completed employee development in '+skill+'.'
        else:
            self.s.setdefault('service_effects',{}).setdefault(recipient,{})[role]=dict(quality=quality,expires=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat(),source=task['id'])
            if role=='maintenance' and b:
                state=self.s.setdefault('industry_state',{}).setdefault(b.id,{})
                state['equipment_condition']=min(100,state.get('equipment_condition',100)+quality//3)
            if role=='hr' and b:
                from .business_rules import BusinessRules
                rules=BusinessRules(self.e)
                from .business_models import INDUSTRY_ROLES
                for _ in range(1+quality//35):rules.make_person(INDUSTRY_ROLES[b.industry][0],candidate=True)
            task['outcome']=DEPARTMENTS[role][0]+' delivered; support remains effective for 30 days and requires renewal work.'

    def legal_result(self,task,quality):
        matter=task['matter'];target=task['target_id'];recipient=task['recipient']
        if matter=='negotiation':
            item=next((b for b in self.w.businesses if b.id==target and not b.owner and b.status=='market'),None) or next((p for p in self.w.properties if p.id==target and not p.owner and p.status=='market'),None)
            if not item:task['outcome']='The original offer is no longer available; no concession or cash recovery.';return
            original=task['original_offer'];willing=stable_roll(self.w,'seller:'+target)
            if willing>=min(90,quality):task['outcome']='Seller refused revised terms. Original offer '+str(original)+' cents retained.';return
            if hasattr(item,'equipment'):
                from .business_rules import BusinessRules
                room=max(0,BusinessRules(self.e).quote(target)['goodwill'])
            else:
                from .property_operations import systems_for
                facts=systems_for(self.w,item)
                obligation=max(0,50-facts['roof']['condition'])*item.full_value//2000
                task['existing_obligation']=obligation
                room=obligation+original//50
            discount=min(room,original*min(5,1+quality//25)//100,max(0,item.asking))
            item.asking-=discount;task['improvement']=discount
            task['outcome']=f'Seller accepted ${discount/100:,.2f} reduction from original ${original/100:,.2f}. This future purchase concession is not cash income.'
        elif matter in ('collection','dispute'):
            claim=next((c for c in self.s.get('legal_claims',[]) if c['id']==target and c['owner']==recipient and c['status']=='open'),None)
            if claim:
                task['exposure']=claim['amount']
                if claim['amount']>5000000 and task['mode']=='internal':
                    task['requires_outside']=True
                    task['outcome']='This specialist matter requires outside counsel. The recorded claim remains open.';return
                if stable_roll(self.w,'warranty-settlement:'+target)>=quality:
                    task['outcome']='Contractor refused settlement; the documented callback claim remains unresolved.';return
                recovered=claim['amount']*quality//100
                self.e.post(recipient,task['id'],'Settlement of documented contractor warranty claim',{'asset:cash':recovered,'income:warranty_recovery':-recovered})
                claim.update(status='settled',settled=self.w.date,recovered=recovered)
                task.update(recovered=recovered,exposure=0,outcome=f'Settled the existing workmanship claim for ${recovered/100:,.2f}. Repairs are still required; no hypothetical lawsuit savings recorded.');return
            business=next((b for b in self.w.businesses if b.id==recipient),None)
            invoice=next((r for r in business.receivables if r['id']==target and (r.get('defaulted') or r.get('overdue_since') or r['due']<self.w.date)),None) if business else None
            if invoice:
                amount=invoice['amount'];task['exposure']=amount
                if stable_roll(self.w,'invoice-collection:'+target)>=quality:
                    task['outcome']='Customer refused settlement; the existing overdue invoice remains receivable.'
                    from .customer_collections import CustomerCollections
                    CustomerCollections(self.e).record(business,invoice,'legal',task['outcome'])
                    return
                recovered=amount*max(20,quality)//100
                from .customer_collections import CustomerCollections
                CustomerCollections(self.e).receive(business,invoice,recovered,task['id'],'legal')
                task['recovered']=recovered;task['exposure']=invoice['amount']
                task['outcome']=f'Recovered ${recovered/100:,.2f} from an existing customer invoice; ${task["exposure"]/100:,.2f} remains due.';return
            lease=next((l for l in self.s['leases'] if l['id']==target and l['owner']==recipient and l['tenant']=='external' and l['arrears']>0),None)
            if lease:
                amount=lease['arrears']
                if stable_roll(self.w,'collection:'+target+':'+str(amount))>=quality:
                    task['outcome']='Collection failed; the documented overdue rent remains receivable.';return
                recovered=amount*max(20,quality)//100
                self.e.post(recipient,task['id'],'Overdue rent recovered by legal',{'asset:cash':recovered,'asset:rent_receivable:'+target:-recovered})
                lease['arrears']-=recovered;task['recovered']=recovered
                self.s.setdefault('property_income_totals',{}).setdefault(lease['property_id'],dict(since=self.w.date,earned=0,collected=0))['collected']+=recovered
                task['outcome']=f'Recovered ${recovered/100:,.2f} of existing overdue rent; remaining exposure ${lease["arrears"]/100:,.2f}.'
            else:task['outcome']='No eligible unpaid claim remains. No invented recovery or avoided-lawsuit saving was recorded.'
        else:
            self.s.setdefault('legal_templates',{}).setdefault(recipient,{})['routine_lease']=dict(date=self.w.date,expires=(date.fromisoformat(self.w.date)+timedelta(days=365)).isoformat(),quality=quality)
            task['outcome']='Routine lease template approved for one year. Authority and affordability checks still apply.'
