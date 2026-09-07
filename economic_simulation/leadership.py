"""Employee leadership, bounded daily authority and prospective annual pay reviews."""
import copy
from datetime import date,timedelta
from .positions import open_positions
from .manager_defaults import limits as manager_limits,staffed as manager_staffed,action_limit
from .campaign import Campaign,integer,flag
from .director_scope import coverage,assigned as director_businesses,prospective,workload
from .domain import Engine,RuleError,calendar_target
from .business_rules import BusinessRules
from .business_models import ROLE_PAY


def review(world,emp):
    business=next(b for b in world.businesses if b.id==emp.employer)
    baseline=max(emp.start_date,business.acquired_on or emp.start_date,emp.last_pay_review or emp.start_date)
    transfers=world.systems.get('employment_transfers',{}).get(emp.id,[])
    if transfers:baseline=max(emp.start_date,transfers[-1]['review_baseline'],emp.last_pay_review or emp.start_date)
    due=calendar_target(date.fromisoformat(baseline),'year').isoformat()
    percent=business.authority.get('annual_raise_percent',3)
    increase=(emp.salary*percent+99)//100
    if emp.compensation.get('pay_basis')=='hourly':
        rate=emp.compensation.get('hourly_rate',0)
        increase=((rate*percent+99)//100+rate)*emp.weekly_hours*52//12-emp.salary
    return dict(due=due,percent=percent,increase=max(0,increase),salary=emp.salary+max(0,increase),annual_cost=max(0,increase)*12,overdue=due<=world.date)


def mark_review(world,emp):
    emp.last_pay_review=world.date
    for request in world.systems.get('management_requests',[]):
        if request['key']=='raise:'+emp.id and request['status']=='open':request.update(status='resolved',resolved=world.date)


class Leadership(Campaign):
    def __init__(self,engine):
        super().__init__(engine);self.rules=BusinessRules(engine)

    def available(self,emp):
        if not emp or emp.status!='active' or not self.controlled(emp.employer):return False
        if self.rules.company(emp.employer).status=='closed':return False
        if date.fromisoformat(self.w.date).weekday() not in emp.days:return False
        from .time_off import absent
        if absent(self.w,emp):return False
        person=self.rules.person(emp.person_id)
        if person.notice_on and person.notice_on<=self.w.date:return False
        from .workforce import Workforce
        policy=Workforce(self.e).effective(emp.employer,emp)[0]
        today=date.fromisoformat(self.w.date)
        duties=workload(self.w,emp);count=duties['count']
        if count and duties['overloaded']:return False
        return not (policy['paid_holidays'] and (today.month,today.day) in ((1,1),(7,4),(12,25)))

    def director(self,bid,available=True):
        selected=coverage(self.w).get(bid)
        if selected:
            record,_=selected
            emp=next(e for e in self.w.employments if e.id==record['employment_id'])
            # Absence of the nearest assigned director does not bypass that
            # director's restrictions by choosing a more distant ancestor.
            if not available or self.available(emp):return record,emp
        return None,None

    def actor(self,b,action='',args=None):
        """Daily work belongs to the local manager; oversight is not a second manager."""
        args=args or {}
        record,director=self.director(b.id)
        strategic=action in ('restaurant_expand','upgrade_business','start_business','start_location','borrow','fund_business','fund_flip','flip_work','market_property','accept_property_offer')
        target=next((e for e in self.w.employments if e.id==args.get('employment_id')),None)
        if target and self.rules.position(target.position_id).role in ('manager','property_manager') and action in ('annual_raise','end_employment','employment_terms','time_off_decide'):
            strategic=True
        if action in ('hire','hire_for_role'):
            position=next((p for p in self.w.positions if p.id==args.get('position_id')),None)
            if (position.role if position else args.get('role')) in ('manager','property_manager'):strategic=True
        if strategic and director:return record,director
        managers=[e for e in self.rules.staff(b.id) if self.rules.position(e.position_id).role in ('manager','property_manager') and self.available(e)]
        oversight={r['employment_id'] for r in self.s.get('directors',[]) if r['active'] and r['business_ids']}
        oversight.update(r['employment_id'] for r in self.s.get('executives',{}).values() if r['active'])
        local=[e for e in managers if e.id not in oversight]
        enabled=manager_limits(b)['enabled']
        if local:
            # A manager's disabled delegation or lower budget does not authorize a
            # director to bypass it. Lack of available coverage is different.
            return None,local[0] if enabled else None
        if director:return record,director
        return None,managers[0] if managers and enabled else None

    def reserved_minutes(self,emp):
        if not self.available(emp):return 0
        from .executives import Executives
        return Executives(self.e).reserved(emp)+workload(self.w,emp)['minutes']

    def judgment(self,b):
        record,employee=self.actor(b)
        if not employee:return 20
        person=self.rules.person(employee.person_id)
        skill={'engineering':'engineering','construction':'maintenance','trades':'maintenance','factory':'maintenance','restaurant':'cooking','bank':'finance','rental':'property','property_management':'property','logistics':'logistics'}.get(b.industry,'retail')
        load=len(director_businesses(self.w,record))*4 if record else 0
        return max(20,min(95,(person.skills.get('leadership',30)+person.skills.get(skill,30))//2-load-person.burnout//5+person.engagement//10))

    def budget(self,record):
        if record.get('day')!=self.w.date:record.update(day=self.w.date,spent=0)
        return max(0,record['limit']-record.get('spent',0))

    def request(self,b,key,action,args,cost,detail):
        if self.deferred(b,key):return
        from .leadership_activity import actor_snapshot
        record,employee=self.actor(b,action,args)
        attribution=actor_snapshot(self.w,employee,record)
        requests=self.s.setdefault('management_requests',[])
        existing=next((r for r in requests if r['key']==key and r['business_id']==b.id and r['status']=='open'),None)
        if existing:
            existing.update(args=args,cost=cost,detail=detail,**attribution)
            self.e.pause_reasons.append(dict(title='Owner approval needed',detail=b.name+': '+detail,financial_amount=cost,management_id=existing['id']))
            return
        requests.append(dict(**attribution,id=self.uid('management'),key=key,business_id=b.id,action=action,args=args,cost=cost,detail=detail,status='open',created=self.w.date,
            recommendation='Approve only after reviewing funding and authority, or change the operating policy.',
            risk='Execution consumes cash or creates future obligations; leaving this request open does not authorize spending.',
            due=(date.fromisoformat(self.w.date)+timedelta(days=7)).isoformat()))
        self.e.event('Owner approval needed',b.name+': '+detail,True,financial_amount=cost)
        self.e.events[-1]['management_id']=requests[-1]['id']

    def perform(self,b,key,action,args,cost,allowed,detail):
        if self.deferred(b,key):return False
        if action=='recover_invoice' and args.get('method')=='agency':
            invoice=next((r for r in b.receivables if r['id']==args.get('invoice_id')),None)
            if invoice:cost=max(cost,invoice['amount']//4)
        record,emp=self.actor(b,action,args)
        allowed=bool(emp) and (cost<=self.budget(record) if record else allowed)
        if action in ('recover_invoice','property_service') and not record:allowed=allowed and cost<=action_limit(b,action,args)
        if action=='annual_raise' and emp and args['employment_id']==emp.id:allowed=False
        if action=='decide' and emp:
            decision=next((d for d in self.s['decisions'] if d['id']==args['decision_id']),{})
            if emp.person_id in decision.get('people',[]):allowed=False
        if not allowed:
            self.request(b,key,action,args,cost,detail+' '+('No authorized manager is available today.' if not emp else 'This exceeds the delegated limit or requires owner approval.'));return False
        source='leadership:'+b.id+':'+key+':'+self.w.date
        try:
            preview=Engine(copy.deepcopy(self.w));preview.simulating=True
            preview.action(action,args,source);preview.validate()
            from .authority import Authority,cash_forecast
            authority=Authority(self.e)
            cash_cost=max(0,self.w.cash(b.id)-preview.world.cash(b.id))
            # Verify the caller's estimate against the actual transaction and new pay.
            old_pay={e.id:e.salary for e in self.w.employments if e.employer==b.id}
            annual=sum(max(0,e.salary-old_pay.get(e.id,0))*12 for e in preview.world.employments
                       if e.employer==b.id and e.status in ('active','joining'))
            previous=sum(row['amount'] for row in cash_forecast(self.w,b.id,1)['rows'] if row['kind']=='committed')
            upcoming=sum(row['amount'] for row in cash_forecast(preview.world,b.id,1)['rows'] if row['kind']=='committed')
            cost=max(cost,cash_cost+annual+max(0,upcoming-previous))
            if record and cost>self.budget(record):
                raise RuleError('The verified commitment exceeds the director’s remaining daily limit.')
            refusal=authority.check(b,record,action,args,cost,preview.world)
            if refusal:raise RuleError(refusal)
            outcome=self.e.action(action,args,source)
        except RuleError as error:
            self.request(b,key,action,args,cost,detail+' '+str(error));return False
        if record:record['spent']+=cost
        authority.record(b,record,emp,action,cost,cash_cost,detail,outcome=outcome)
        for r in self.s.get('management_requests',[]):
            if r['business_id']==b.id and r['key']==key and r['status']=='open':r.update(status='resolved',resolved=self.w.date,resolved_by='Delegated leader',outcome=outcome)
        self.e.event('Delegated decision completed',self.rules.person(emp.person_id).name+' · '+b.name+': '+detail)
        return True

    def action(self,action,args,command_id):
        if action=='leadership_defaults':
            b=self.rules.company(args.get('business_id',''));self.require(b.id)
            mode=args.get('mode','daily')
            if mode not in ('daily','growth'):raise RuleError('Choose daily management or director growth defaults.')
            operating=b.authority.get('operating_policy',{})
            automatic=self.s.get('operating_automation',{}).get(b.id,{})
            if mode=='daily':
                for key in ('enabled','purchasing_limit','salary_limit','training_budget','overtime_cap','auto_raises','staffing_target','routine_management'):
                    b.authority.pop(key,None)
                for key in ('hiring','hiring_role','training','rentals','jobs','stock'):operating.pop(key,None)
                for key in ('pricing','scheduling','staff_reductions','property_operations','service_renewals','service_roles'):automatic.pop(key,None)
                self.s.get('time_off_policies',{}).pop(b.id,None)
                b.auto_restock=b.auto_projects=True
            else:
                for key in ('growth','growth_target','growth_budget'):operating.pop(key,None)
                for key in ('locations','location_limit'):automatic.pop(key,None)
            return 'Default '+('daily manager duties' if mode=='daily' else 'director growth policies')+' restored. Authority contracts, parent restrictions, reserves and already committed spending remain in force. Work runs on the next available review; no transaction has been executed by this policy change.'
        if action=='director_inheritance':
            b=self.rules.company(args.get('business_id',''))
            from .leadership_history import duties,record_change
            people=[self.rules.contract(r['employment_id']) for r in self.s.get('directors',[]) if r['active']]
            before={emp.id:duties(self.w,emp) for emp in people}
            b.authority['inherit_director']=flag(args.get('enabled',True))
            for emp in people:record_change(self.rules,emp,before[emp.id],'Parent director inheritance changed at '+b.name+'.')
            return 'Parent director inheritance '+('enabled' if b.authority['inherit_director'] else 'disabled')+'. Explicit assignments remain in place. Local managers, existing authority limits and payroll accounts are unchanged.'
        if action=='management_reopen':
            request=next((r for r in self.s.get('management_requests',[]) if r['id']==args.get('request_id') and r['status']=='deferred'),None)
            if not request:raise RuleError('This request is no longer deferred.')
            self.require(request['business_id'])
            request.update(status='open',reopened=self.w.date)
            request.pop('resolved',None);request.pop('deferred_until',None)
            return 'Request returned to the inbox for review. No approval or spending occurred.'
        if action=='management_defer':
            request=next((r for r in self.s.get('management_requests',[]) if r['id']==args.get('request_id') and r['status']=='open'),None)
            if not request:raise RuleError('This approval is no longer open.')
            self.require(request['business_id'])
            request.update(status='deferred',resolved=self.w.date,deferred_until=(date.fromisoformat(self.w.date)+timedelta(days=7)).isoformat())
            return 'Request deferred for seven days. This action will not be executed or proposed again during that period; obligations already incurred still apply.'
        if action=='leadership_raise':
            from .leadership_pay import scope,quote,apply
            emp=self.rules.contract(args.get('employment_id',''));self.require(emp.employer)
            role,businesses=scope(self.w,emp)
            if emp.status!='active' or not businesses:raise RuleError('This employee no longer holds active leadership duties.')
            return apply(self.rules,emp,quote(self.w,emp,role,businesses))
        if action=='director_assign':
            emp=self.rules.contract(args.get('employment_id',''));self.require(emp.employer)
            if emp.status!='active':raise RuleError('Appoint an active employee as director.')
            if self.s.get('executives',{}).get(emp.id,{}).get('active'):
                raise RuleError('This employee already has executive oversight duties; use that scope rather than duplicating director time.')
            b=self.rules.company(args.get('business_id',''))
            from .manager_defaults import director_limit
            existing=next((r for r in self.s.get('directors',[]) if r['employment_id']==emp.id and r['active']),None)
            limit=integer(args.get('limit',existing['limit'] if existing else director_limit(b)),0,1000000000)
            records=self.s.get('directors',[])
            record=next((r for r in records if r['employment_id']==emp.id and r['active']),None)
            assigned=set(record['business_ids'] if record else [])|{b.id}
            effective=prospective(self.w,emp,b)
            if any(a['active'] and a['employment_id']==emp.id for a in self.s['assignments']):raise RuleError('End shared-service time assignments before appointing this employee as director.')
            free=emp.weekly_hours*60//max(1,len(emp.days))-180
            executive=record and record.get('role') in ('home_office_director','division_vp','corporate_services_vp')
            per_business,maximum=(30,8) if executive else (60,5)
            if len(assigned)>maximum or len(effective)>maximum or len(effective)*per_business>max(0,free):raise RuleError('Leadership scope exceeds scheduled hours, including inherited subsidiaries. Reduce assignments or increase hours; directors need 60 minutes per business (maximum five), executives 30 minutes (maximum eight), plus three hours for their role.')
            from .leadership_pay import quote,apply
            from .leadership_history import duties,record_change
            affected=[emp]+[self.rules.contract(r['employment_id']) for r in records if r is not record and r['active']]
            previous={employee.id:duties(self.w,employee) for employee in affected}
            pay=quote(self.w,emp,record.get('role','director') if record else 'director',effective)
            pay_detail=apply(self.rules,emp,pay)
            self.s['directors']=records
            for other in records:
                if other is not record and b.id in other['business_ids']:other['business_ids'].remove(b.id)
            if not record:
                record=dict(employment_id=emp.id,business_ids=[],limit=limit,active=True,day=self.w.date,spent=0);records.append(record)
            record.update(business_ids=sorted(assigned),limit=limit)
            for employee in affected:
                reason=('Replaced by '+self.rules.person(emp.person_id).name+' at '+b.name+'.') if employee.id!=emp.id else ''
                record_change(self.rules,employee,previous[employee.id],reason)
            self.e.event('Director appointed',self.rules.person(emp.person_id).name+' now oversees '+b.name+'. Their existing employer continues payroll; one working hour per assigned business is reserved each day.')
            return pay_detail+' Director appointed with default growth authority for equipment and same-industry locations within the shared budget and cash reserves. A local manager who is appointed retains daily duties as managing director until another manager takes them over. Eligible subsidiaries inherit this director; existing policy overrides and contracts remain in force.'
        if action=='director_remove':
            b=self.rules.company(args.get('business_id',''))
            from .leadership_history import duties,record_change
            affected=[self.rules.contract(r['employment_id']) for r in self.s.get('directors',[]) if r['active']]
            previous={employee.id:duties(self.w,employee) for employee in affected}
            for r in self.s.get('directors',[]):
                if b.id in r['business_ids']:r['business_ids'].remove(b.id)
            for employee in affected:record_change(self.rules,employee,previous[employee.id],'Director oversight removed from '+b.name+'.')
            from .leadership_pay import resolve_if_unneeded
            for employee in self.w.employments:resolve_if_unneeded(self.w,employee)
            return 'Explicit director oversight removed for this business. Parent oversight applies when inheritance is enabled; employment and agreed salary are unchanged.'
        if action=='annual_raise':
            emp=self.rules.contract(args.get('employment_id',''));self.require(emp.employer)
            if emp.status!='active':raise RuleError('Review an active employee.')
            data=review(self.w,emp)
            if not data['overdue']:raise RuleError('This annual review is not due yet.')
            if emp.compensation.get('pay_basis')=='hourly':
                rate=emp.compensation['hourly_rate'];emp.compensation['hourly_rate']=rate+(rate*data['percent']+99)//100
            emp.salary=data['salary'];mark_review(self.w,emp)
            person=self.rules.person(emp.person_id);person.morale=min(100,person.morale+5);person.loyalty=min(100,person.loyalty+3)
            self.rules.record(person.id,f'Annual pay review: {data["percent"]}% increase; monthly base pay ${emp.salary/100:,.2f}. Future payroll only.')
            return 'Annual raise approved. Future wages change; accrued payroll is unchanged.'
        if action=='management_approve':
            request=next((r for r in self.s.get('management_requests',[]) if r['id']==args.get('request_id') and r['status']=='open'),None)
            if not request:raise RuleError('This approval is no longer open.')
            self.require(request['business_id'])
            before=self.w.cash(request['business_id'])
            result=self.e.action(request['action'],request['args'],command_id+':approved')
            request.update(status='resolved',resolved=self.w.date,resolved_by='Player',outcome=result,
                           cash_cost=max(0,before-self.w.cash(request['business_id'])))
            return result
        raise RuleError('Unknown leadership action.')

    def start_day(self):
        from .director_scope import reconcile
        reconcile(self.e)
        today=date.fromisoformat(self.w.date)
        for request in self.s.get('management_requests',[]):
            if request['status']=='deferred' and request['deferred_until']<self.w.date and self.controlled(request['business_id']):
                request.update(status='open',reopened=self.w.date)
                request.pop('resolved',None);request.pop('deferred_until',None)
                self.e.event('Owner approval needed','Deferred request returned for review: '+request['detail'],True,financial_amount=request['cost'])
        for emp in self.w.employments:
            from .leadership_pay import resolve_if_unneeded
            resolve_if_unneeded(self.w,emp)
            if emp.status!='active' or not self.controlled(emp.employer):continue
            from .leadership_pay import scope,quote
            role,businesses=scope(self.w,emp)
            if businesses:
                pay=quote(self.w,emp,role,businesses)
                if pay['increase']:
                    from .money_display import money
                    self.request(self.rules.company(emp.employer),'leadership-pay:'+emp.id,'leadership_raise',{'employment_id':emp.id},pay['annual'],
                        self.rules.person(emp.person_id).name+' expects a leadership raise: '+money(pay['current'])+' → '+money(pay['salary'])+'/month. Review the added responsibility and future payroll cost.')
            data=review(self.w,emp)
            if not data['overdue'] or today.weekday() not in emp.days:continue
            b=self.rules.company(emp.employer);authority=manager_limits(b)
            self.perform(b,'raise:'+emp.id,'annual_raise',{'employment_id':emp.id},data['annual_cost'],authority.get('auto_raises',True) and data['salary']<=authority.get('salary_limit',400000),f'Annual raise for {self.rules.person(emp.person_id).name}: {data["percent"]}%, adding ${data["increase"]/100:,.2f}/month (${data["annual_cost"]/100:,.2f}/year).')
        for b in self.w.businesses:
            if not self.controlled(b.id) or b.status=='closed':continue
            record,actor=self.actor(b)
            if not actor:continue
            authority=manager_limits(b)
            if authority.get('period')!=self.w.date[:7]:b.authority.update(period=self.w.date[:7],spent=0);authority.update(period=self.w.date[:7],spent=0)
            from .management import policy
            operating=policy(b,self.w)
            b.auto_projects=operating['jobs'];b.auto_restock=operating['stock']
            if today.weekday()==0:
                occupied={e.position_id for e in self.w.employments if e.employer==b.id and e.status in ('active','joining')}
                positions=open_positions(self.w,b.id)
                target=len(positions) if operating['hiring']=='vacancies' else 0 if operating['hiring']=='freeze' else authority.get('staffing_target',len(positions))
                vacancy=next((p for p in positions if p.id not in occupied),None)
                grow_role=operating['hiring_role'] if operating['hiring']=='grow' and not vacancy and len(positions)<100 else None
                from .restaurant import active as restaurant_active
                if grow_role and restaurant_active(self.w,b):
                    from .restaurant_staffing import hiring_role
                    grow_role=hiring_role(self.w,b)
                if (vacancy or grow_role) and len(occupied)<target:
                    role=vacancy.role if vacancy else grow_role
                    salary=ROLE_PAY[role]
                    from .specialists import recruitment_fee
                    fee=recruitment_fee(self.w,b.id)
                    from .specialists import LICENSES
                    required_license=(vacancy.required_license if vacancy else None) or LICENSES.get(role)
                    candidate=next((p for p in self.w.people if p.candidate and (role!='engineer' or any('Engineering' in q for q in p.qualifications)) and (not required_license or p.licenses.get(required_license,'')>=self.w.date)),None)
                    if candidate:
                        action='hire' if vacancy else 'hire_for_role'
                        args=dict(person_id=candidate.id,amount=salary,weekly_hours=40)
                        args.update(dict(position_id=vacancy.id) if vacancy else dict(business_id=b.id,role=role))
                        self.perform(b,'hire:'+(vacancy.id if vacancy else role),action,args,salary*12+fee,salary<=authority.get('salary_limit',400000),f'Fill {role}: ${salary/100:,.2f}/month plus ${fee/100:,.0f} recruitment; annual base-pay commitment ${salary*12/100:,.2f}.')
                    elif not any(p['kind']=='recruitment' and p['entity']==b.id and p['role']==role and p['status']=='active' for p in self.s['plans']):
                        self.perform(b,'recruit:'+role,'recruit',dict(business_id=b.id,role=role,channel='local'),20000,20000<=authority.get('purchasing_limit',150000),'Advertise for '+role+' applicants ($200).')
                budget=authority.get('training_budget',0)-authority.get('spent',0) if operating['training'] else 0
                self.grow(b)
                trainee=next((e for e in self.rules.staff(b.id) if not self.rules.person(e.person_id).training_until and e.id!=actor.id and
                    ('training_budget' in b.authority or any(other.id!=e.id and other.position_id!=e.position_id and
                     self.rules.position(other.position_id).role==self.rules.position(e.position_id).role and self.available(other)
                     for other in self.rules.staff(b.id)))),None)
                if trainee and budget>=50000:
                    if self.perform(b,'train:'+trainee.id,'train',{'employment_id':trainee.id},50000,True,'Fund employee training ($500).'):b.authority['spent']=authority.get('spent',0)+50000
            for emp in self.rules.staff(b.id):
                from .specialists import LICENSES
                position=self.rules.position(emp.position_id)
                license_name=position.required_license or LICENSES.get(position.role)
                if license_name and self.rules.person(emp.person_id).licenses.get(license_name,'')<=(today+timedelta(days=30)).isoformat() and not any(p['kind']=='license' and p['person_id']==emp.person_id and p['status']=='active' for p in self.s['plans']):
                    self.perform(b,'license:'+emp.id,'renew_license',{'employment_id':emp.id,'license':license_name},25000,25000<=authority.get('purchasing_limit',150000),'Renew '+license_name.replace('_',' ')+' ($250).')
            for prop in self.w.properties:
                if operating['rentals'] and prop.owner==b.id and prop.occupancy_use=='rental' and prop.status=='vacant' and not prop.spaces:
                    action='rent' if prop.condition>=40 else 'rehabilitate'
                    cost=0 if action=='rent' else self.e.quote(action,prop.id)['total']
                    self.perform(b,action+':'+prop.id,action,{'property_id':prop.id},cost,cost<=authority.get('purchasing_limit',150000),('Find a tenant for ' if action=='rent' else 'Repair for rental: ')+prop.name)

    def grow(self,b):
        from .management import policy,growth_status
        p=policy(b,self.w);status=growth_status(self.w,b)
        if not status['ready']:return
        cost=status['cost'];detail=f'Equipment growth toward {p["growth_target"]}% capacity: ${cost/100:,.2f}; 21-day expansion, preserving ${status["reserve"]/100:,.2f} cash.'
        if p['growth']=='review':
            self.request(b,'growth','upgrade_business',{'business_id':b.id},cost,detail);return
        if self.perform(b,'growth','upgrade_business',{'business_id':b.id},cost,cost<=manager_limits(b)['purchasing_limit'],detail):
            if b.authority.get('growth_period')!=self.w.date[:7]:b.authority.update(growth_period=self.w.date[:7],growth_spent=0)
            b.authority['growth_spent']=b.authority.get('growth_spent',0)+cost

    def resolve_decisions(self):
        handled=False
        for decision in self.s['decisions']:
            if decision['status']!='open' or decision['cost']<=0:continue
            business=next((b for b in self.w.businesses if b.id==decision['entity'] and self.controlled(b.id)),None)
            if not business or not self.actor(business)[1]:continue
            choice=next((c for c in ('retain','repair','mediate','audit') if c in decision['options']),None)
            if not choice:continue
            if self.perform(business,'decision:'+decision['id'],'decide',dict(decision_id=decision['id'],choice=choice),decision['cost'],decision['cost']<=manager_limits(business)['purchasing_limit'],decision['title']+' ($'+format(decision['cost']/100,',.2f')+').'):
                handled=True
                self.e.pause_reasons[:]=[r for r in self.e.pause_reasons if r.get('decision_id')!=decision['id']]
                for event in self.e.events:
                    if event.get('decision_id')==decision['id']:event['handled_by']='Delegated leadership'

        return handled

    def stock_limit(self,b,units):
        if self.deferred(b,'stock'):return 0
        record,emp=self.actor(b)
        from .authority import Authority
        configured=Authority(self.e).key(b,record) in Authority(self.e).contracts() or any(k in Authority(self.e).contracts() for k in ('manager:'+b.id,'director:'+str((self.director(b.id,False)[0] or {}).get('employment_id',''))))
        if not (manager_limits(b)['enabled'] and manager_staffed(self.w,b) or b.authority.get('enabled') or self.director(b.id,False)[0] or configured):return units
        limit=self.budget(record) if record else manager_limits(b)['purchasing_limit'] if emp else 0
        allowed=min(units,limit//b.unit_cost)
        if allowed<units:
            self.request(b,'stock','restock',{'business_id':b.id,'units':units},units*b.unit_cost,f'Stock replenishment needs ${units*b.unit_cost/100:,.2f}; delegated limit is ${limit/100:,.2f}.')
            return 0  # Escalate the full order, never split it to evade the limit.
        if not units:return 0
        from .authority import Authority
        authority=Authority(self.e)
        preview=Engine(copy.deepcopy(self.w));cost=units*b.unit_cost
        try:
            preview.post(b.id,'stock-preview','Proposed stock purchase',{'asset:cash':-cost,'asset:inventory':cost})
            refusal=authority.check(b,record,'restock',{'business_id':b.id,'units':units},cost,preview.world)
        except RuleError as error:refusal=str(error)
        if refusal:
            self.request(b,'stock','restock',{'business_id':b.id,'units':units},cost,refusal)
            return 0
        if record:record['spent']+=allowed*b.unit_cost
        if emp:authority.record(b,record,emp,'restock',cost,cost,'Automatic stock replenishment')
        return allowed

    def deferred(self,b,key):
        return any(r['business_id']==b.id and r['key']==key and r['status']=='deferred' and r['deferred_until']>=self.w.date for r in self.s.get('management_requests',[]))

    def accept_project(self,b,kit_key=None):
        from .authority import Authority
        from .engineering import accept,next_offer
        authority=Authority(self.e)
        record,employee=self.actor(b,'new_project')
        configured=authority.key(b,record) in authority.contracts() or 'manager:'+b.id in authority.contracts() or ('director:'+str((self.director(b.id,False)[0] or {}).get('employment_id',''))) in authority.contracts()
        if not configured and not (manager_limits(b)['enabled'] and manager_staffed(self.w,b)) and not self.director(b.id,False)[0]:
            quote=next_offer(self.w,b,kit_key)
            cost=(quote['minutes']*quote.get('materials',b.material_hourly_cost)+59)//60
            outcome=accept(self.rules,b,automatic=True,kit_key=kit_key)
            acting_record,employee=self.actor(b)
            # Report the existing automatic-policy path without changing its authority accounting.
            authority.record(b,acting_record,employee,'new_project',cost,0,outcome,
                             outcome='Accepted under the business automatic-job policy.',charge_authority=False)
            return True
        quote=next_offer(self.w,b,kit_key)
        cost=(quote['minutes']*quote.get('materials',b.material_hourly_cost)+59)//60
        return self.perform(b,'project:'+str(quote['number']),'new_project',{'business_id':b.id,**({'kit':quote['kit']} if quote.get('kit') else {})},cost,
            cost<=manager_limits(b)['purchasing_limit'],
            f"Accept job {quote['number']}: ${quote['fee']/100:,.2f} fee, {quote['minutes']/60:g} hours, ${cost/100:,.2f} material commitment; collection follows completion by 14 days.")

    def morale_penalty(self,emp):
        data=review(self.w,emp)
        if not data['overdue']:return 0
        return min(20,3+((date.fromisoformat(self.w.date)-date.fromisoformat(data['due'])).days//30)*2)

    def view(self,b):
        record,emp=self.director(b.id,False);_,acting=self.actor(b)
        from .routine_management import ready_property_care
        manager_queue=ready_property_care(self.w)
        source=coverage(self.w).get(b.id,(None,None))[1]
        from .leadership_activity import activity_view
        recent=activity_view(self.w,b.id,status='completed',limit=3)
        from .leadership_pay import quote
        pay_quotes={}
        for candidate in self.w.employments:
            if candidate.status!='active' or not self.controlled(candidate.employer):continue
            assigned=prospective(self.w,candidate,b)
            existing=next((r for r in self.s.get('directors',[]) if r['active'] and r['employment_id']==candidate.id),{})
            pay_quotes[candidate.id]=quote(self.w,candidate,existing.get('role','director'),assigned)
        from .manager_defaults import director_limit
        local_manager=next((e for e in self.rules.staff(b.id) if self.rules.position(e.position_id).role in ('manager','property_manager')),None)
        return dict(default_director_limit=director_limit(b),local_manager_id=local_manager.id if local_manager else '',
            managing_director=bool(emp and emp.employer==b.id and self.rules.position(emp.position_id).role in ('manager','property_manager')),
            manager_policy=manager_limits(b),pay_quotes=pay_quotes,recent_actions=recent,director_source=source,
            inherited_from=next((c.name for c in self.w.businesses if c.id==source and c.id!=b.id),None),
            director_explicit=bool(record and b.id in record['business_ids']),director_workload=workload(self.w,emp) if emp else None,
            director=record,director_name=self.rules.person(emp.person_id).name if emp else None,employer=next((c.name for c in self.w.businesses if emp and c.id==emp.employer),None),active_name=self.rules.person(acting.person_id).name if acting else None,requests=[r for r in self.s.get('management_requests',[]) if r['status']=='open' and r['business_id']==b.id and r['id'] not in manager_queue])
