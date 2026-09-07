"""Shared work intervals and reciprocal service accounting; no duplicated labor."""
from __future__ import annotations
from datetime import date
from .campaign import Campaign, integer, flag
from .domain import RuleError, daily_share
from .business_rules import BusinessRules
from .business_models import ROLE_SKILLS,INDUSTRY_ROLES
from .workforce import Workforce


class SharedServices(Campaign):
    def __init__(self,engine):super().__init__(engine);self.rules=BusinessRules(engine)

    def permitted_target(self,target):
        if self.controlled(target):return self.require(target)
        if any(f['operator']==target and f['status']=='active' and f['staff_access'] and self.controlled(f['issuer']) for f in self.s['franchises']):return target
        raise RuleError('Independent staff sharing requires an active franchise contract granting access.')

    def action(self,action,args,command_id):
        if action=='share_department_staff':
            return self.share_department(args,command_id)
        if action=='service_agreement':
            source=self.require(args.get('source',''));target=self.permitted_target(args.get('target',''))
            if source==target or source in ('personal','company') or target in ('personal','company'):raise RuleError('Choose two different operating companies.')
            markup=integer(args.get('markup',0),0,25)
            self.s['agreements'].append(dict(id=self.uid('agreement'),source=source,target=target,markup=markup,staff_access=flag(args.get('staff_access',True)),active=True,date=self.w.date,history=[]))
            return 'Service agreement signed. Only assigned time is charged; unused staff capacity stays with the employer.'
        if action=='assign_staff':
            emp=self.rules.contract(args.get('employment_id',''));target=self.permitted_target(args.get('target',''));role=args.get('role','maintenance')
            agreement=next((a for a in self.s['agreements'] if a['source']==emp.employer and a['target']==target and a['active'] and a['staff_access']),None)
            if not agreement:raise RuleError('A service agreement with staff access is required first.')
            if role not in INDUSTRY_ROLES[self.rules.company(target,owned=False).industry]:raise RuleError('The receiving operation does not use this role.')
            if any(d['active'] and d['employment_id']==emp.id and d['business_ids'] for d in self.s.get('directors',[])):raise RuleError('Remove director oversight before assigning shared-service work; leadership time is already reserved.')
            start=integer(args.get('start_minute',emp.shift_start*60),0,1439);duration=integer(args.get('minutes',120),1,720)
            if start<emp.shift_start*60 or start+duration>emp.shift_start*60+emp.weekly_hours*60//len(emp.days):raise RuleError('Shared work must fit inside the existing employment shift.')
            person=self.rules.person(emp.person_id)
            from .specialists import LICENSES
            if role in LICENSES and person.licenses.get(LICENSES[role],'')<self.w.date:raise RuleError('This specialist assignment requires a current '+LICENSES[role].replace('_',' ')+' license.')
            if role=='engineer' and not any('Engineering' in q for q in person.qualifications):raise RuleError('Shared engineering work requires an engineering qualification.')
            for a in self.s['assignments']:
                if a['active'] and a['employment_id']==emp.id and max(start,a['start_minute'])<min(start+duration,a['start_minute']+a['minutes']):raise RuleError('This interval is already assigned. Work time cannot be duplicated.')
            travel=30 if self.rules.company(emp.employer).region!=self.rules.company(target,owned=False).region else 0
            if duration<=travel:raise RuleError('The assignment must leave working time after travel.')
            self.s['assignments'].append(dict(id=self.uid('assignment'),employment_id=emp.id,source=emp.employer,target=target,role=role,start_minute=start,minutes=duration,travel=travel,agreement_id=agreement['id'],active=True,date=self.w.date,last_cost=0,last_minutes=0))
            self.rules.record(person.id,f'Assigned {duration} minutes per scheduled day to {target} as {role}, including {travel} minutes travel.')
            return 'Assignment created within existing paid time. Travel consumes capacity and shared charges replace no wages.'
        if action=='end_assignment':
            a=next((a for a in self.s['assignments'] if a['id']==args.get('assignment_id') and a['active']),None)
            if not a:raise RuleError('Choose an active assignment.')
            a['active']=False;a['end_date']=self.w.date
            return 'Assignment ended. Its employee remains employed and its history remains available.'
        if action=='headquarters':
            b=self.rules.company(args.get('business_id',''));p=next((p for p in self.w.properties if p.id==args.get('property_id') and p.owner==b.id),None)
            if not p or p.status not in ('vacant','occupied'):raise RuleError('Choose a vacant or already occupied property owned by this company.')
            if p.category!='commercial':raise RuleError('Headquarters require a commercial building.')
            if any(o['property_id']==p.id and o['active'] for o in self.s['offices']):raise RuleError('This property already has an office.')
            desks=integer(args.get('desks',20),1,200);cost=desks*80000
            self.e.post(b.id,command_id,'Headquarters fit-out',{'asset:cash':-cost,'asset:equipment':cost});b.equipment+=cost
            p.status='occupied';p.occupant=b.id;p.occupancy_use='operating'
            self.s['offices'].append(dict(id=self.uid('office'),business_id=b.id,property_id=p.id,desks=desks,active=True,date=self.w.date))
            return 'Headquarters fitted out. Staffed specialists and validated assignments provide its services; the building alone creates no bonus.'
        raise RuleError('Unknown shared-service action.')

    def share_department(self,args,command_id):
        """One reviewed decision, using the existing agreement and interval rules."""
        import copy
        from .domain import Engine
        from .shared_resources import departments,support_problem
        from .money_display import money
        department=departments(self.w).get(args.get('department_id',''))
        if not department:raise RuleError('Choose an existing internal department.')
        self.require(department['provider'])
        emp=self.rules.contract(args.get('employment_id',''))
        target=next((b for b in self.w.businesses if b.id==args.get('target','')),None)
        problem=support_problem(self.w,department,emp,target)
        if problem:raise RuleError(problem)
        try:
            hour,minute=str(args.get('start_time','08:00')).split(':')
            start=integer(hour,0,23)*60+integer(minute,0,59)
        except (ValueError,TypeError):raise RuleError('Choose a valid start time.')
        duration=integer(args.get('minutes',120),1,720)
        agreement=next((a for a in self.s['agreements'] if a['source']==emp.employer and a['target']==target.id and a['active']),None)
        if agreement and not agreement['staff_access']:raise RuleError('The existing service agreement prohibits staff access. Review shared staff agreements first.')
        agreement_args=dict(source=emp.employer,target=target.id,markup=0,staff_access=True)
        assignment_args=dict(employment_id=emp.id,target=target.id,role=department['role'],start_minute=start,minutes=duration)
        # Preflight both steps before any agreement, history or identifier changes.
        trial=SharedServices(Engine(copy.deepcopy(self.w)))
        if not agreement:trial.action('service_agreement',agreement_args,command_id)
        trial.action('assign_staff',assignment_args,command_id)
        if not agreement:self.action('service_agreement',agreement_args,command_id)
        self.action('assign_staff',assignment_args,command_id)
        markup=agreement['markup'] if agreement else 0
        policy=Workforce(self.e).effective(emp.employer,emp)[0]
        overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
        allocation=(emp.salary+overtime+emp.compensation.get('shift_premium',0)+Workforce(self.e).benefit_cost(emp,policy))*duration//max(1,emp.weekly_hours*60//len(emp.days))
        allocation=allocation*(100+markup)//100
        travel=30 if self.rules.company(emp.employer).region!=target.region else 0
        name=self.rules.person(emp.person_id).name
        return (f'{name} will support {target.name} for {duration} minutes per scheduled day from {hour.zfill(2)}:{minute.zfill(2)}, including {travel} minutes travel. '
                f'Estimated allocation up to {money(allocation)} per month at full attendance; actual daily charges depend on attendance and calendar wages. '
                f'Existing payroll is paid by the employer; the receiving business reimburses assigned time with {markup}% markup. '
                'No outside service or setup fee. Leave reduces delivery. End the assignment from the team card to return the time.')

    def outgoing_minutes(self,emp,hour):
        return sum(max(0,min((hour+1)*60,a['start_minute']+a['minutes'])-max(hour*60,a['start_minute'])) for a in self.s['assignments'] if a['active'] and a['employment_id']==emp.id)

    def incoming(self,b,today,buckets):
        for a in self.s['assignments']:
            if not a['active'] or a['target']!=b.id:continue
            emp=next((e for e in self.w.employments if e.id==a['employment_id']),None)
            if not emp or emp.status!='active' or today.weekday() not in emp.days:continue
            p=self.rules.person(emp.person_id);policy,absent=Workforce(self.e).before_work(emp,p,today)
            if absent or (emp.leave_until and emp.leave_until>=self.w.date):continue
            role=a['role']
            from .specialists import LICENSES
            if role in LICENSES and p.licenses.get(LICENSES[role],'')<self.w.date:continue
            quality=max(20,min(115,55+p.skills.get(ROLE_SKILLS[role],30)//2+(p.engagement-50)//5-p.burnout//3))
            start=a['start_minute']+a['travel'];end=a['start_minute']+a['minutes']
            if p.training_until:end=max(start,end-60)
            if p.education:end=max(start,end-120)
            for hour in range(24):
                minutes=max(0,min(end,(hour+1)*60)-max(start,hour*60))
                buckets.setdefault(role,[0]*24)[hour]+=minutes*quality//100

    def settle(self,today):
        for a in self.s['assignments']:
            if not a['active']:continue
            emp=next((e for e in self.w.employments if e.id==a['employment_id']),None)
            if not emp or emp.status!='active':a['active']=False;continue
            if today.weekday() not in emp.days:continue
            p=self.rules.person(emp.person_id);wf=Workforce(self.e);policy,absent=wf.before_work(emp,p,today)
            if absent or (emp.leave_until and emp.leave_until>=self.w.date):a['last_cost']=0;a['last_minutes']=0;continue
            agreement=next(g for g in self.s['agreements'] if g['id']==a['agreement_id'])
            # Actual calendar-day employer cost allocated by the reserved shift fraction.
            overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
            cost=daily_share(emp.salary+overtime+emp.compensation.get('shift_premium',0),today)+daily_share(wf.benefit_cost(emp,policy),today)
            allocated=cost*a['minutes']//(emp.weekly_hours*60//len(emp.days));charge=allocated*(100+agreement['markup'])//100
            a['last_cost']=charge;a['last_minutes']=a['minutes']-a['travel']
            if charge:
                paid=min(charge,self.w.cash(a['target']));owed=charge-paid
                source='shared:'+a['id']+':'+self.w.date
                self.e.post(a['target'],source,'Shared staff cost allocation',{'expense:internal_services:'+a['source']:charge,'asset:cash':-paid,'liability:intercompany:'+a['source']:-owed})
                self.e.post(a['source'],source,'Shared staff cost reimbursement',{'income:internal_services:'+a['target']:-charge,'asset:cash':paid,'asset:intercompany:'+a['target']:owed})
        for debtor,accounts in list(self.w.accounts.items()):
            for key,value in list(accounts.items()):
                if key.startswith('liability:intercompany:') and value<0:
                    creditor=key.split(':',2)[2];paid=min(-value,self.w.cash(debtor))
                    if paid:
                        source=f'intercompany-settle:{debtor}:{creditor}:{self.w.date}'
                        self.e.post(debtor,source,'Settle internal balance',{'asset:cash':-paid,key:paid})
                        self.e.post(creditor,source,'Collect internal balance',{'asset:cash':paid,'asset:intercompany:'+debtor:-paid})

    def validate(self):
        for a in self.s.get('assignments',[]):
            if not a['active']:continue
            emp=next((e for e in self.w.employments if e.id==a['employment_id']),None)
            if not emp:raise RuleError('Shared assignment lost its employment record.')
            if emp.status not in ('active','joining'):continue
            if a['start_minute']<emp.shift_start*60 or a['start_minute']+a['minutes']>emp.shift_start*60+emp.weekly_hours*60//len(emp.days):raise RuleError('Existing shared assignments no longer fit this schedule. End or revise them first.')
        for entity,accounts in self.w.accounts.items():
            for key,value in accounts.items():
                if key.startswith('asset:intercompany:'):
                    target=key.split(':',2)[2]
                    if value!=-self.w.accounts[target].get('liability:intercompany:'+entity,0):raise RuleError('Reciprocal internal balances do not reconcile.')
