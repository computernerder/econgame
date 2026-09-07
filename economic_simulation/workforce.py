"""Dated policy inheritance, compensation, career decisions and employee lifecycle."""
from __future__ import annotations
from datetime import date,timedelta
from .positions import open_positions, position_open
from .campaign import Campaign, integer, flag
from .domain import GAME_RULES, RuleError, daily_share
from .business_models import BENEFITS,ROLE_PAY,ROLE_SKILLS,INDUSTRY_ROLES
from .business_rules import BusinessRules

BOOL_FIELDS={'vision','life','disability','paid_holidays'}
LIMITS={'employer_share':(0,100),'retirement_percent':(0,20),'vacation_days':(0,60),'sick_days':(0,30),'floating_holidays':(0,12),'remote_days':(0,5),'commission_percent':(0,20),'profit_share_percent':(0,20),'overtime_limit':(40,60),'security':(0,3)}


class Workforce(Campaign):
    def __init__(self,engine):
        super().__init__(engine);self.rules=BusinessRules(engine)

    def effective(self,entity,employment=None,on=None):
        on=on or self.w.date;chain=[];cursor=entity
        while cursor:
            if cursor in chain:raise RuleError('Ownership cycle in policy resolution.')
            chain.append(cursor);cursor=self.parent(cursor)
        values=dict(GAME_RULES['policies']);sources={k:'Ruleset default' for k in values};locked=set()
        for scope in reversed(chain):
            local={};local_locks=set()
            for policy in sorted((p for p in self.s['policies'] if p['scope']==scope and p['effective']<=on),key=lambda p:(p['effective'],p['version'])):
                if policy.get('reset'):local={};local_locks=set()
                else:local.update(policy['values']);local_locks=set(policy['locked'])
            for key,value in local.items():
                if key not in locked:values[key]=value;sources[key]=scope
            locked.update(local_locks)
        if employment:
            for key,value in employment.policy_overrides.items():
                if key not in locked:values[key]=value;sources[key]='Individual agreement'
        return values,sources,locked

    def benefit_cost(self,emp,policy):
        b=self.rules.company(emp.employer,owned=False)
        plan=GAME_RULES['medical'][policy['medical']]
        # Enrollment is a gameplay choice. No private household or medical detail is exposed.
        medical=plan['premium']*policy['employer_share']//100
        extras=GAME_RULES['dental'][policy['dental']]+(1200 if policy['vision'] else 0)+(1000 if policy['life'] else 0)+(1800 if policy['disability'] else 0)
        extras+=sum(policy[k] for k in ('health_account','education','transport','childcare','meals'))
        extras+=emp.salary*policy['retirement_percent']//100
        return BENEFITS[b.benefits]+medical+extras

    def action(self,action,args,command_id):
        if action in ('policy_set','policy_reset'):
            scope=self.require(args.get('entity','personal'));today=date.fromisoformat(self.w.date)
            try:effective=date.fromisoformat(args.get('effective') or (today+timedelta(days=7)).isoformat())
            except ValueError:raise RuleError('Enter a valid policy start date.')
            if not today<=effective<=today+timedelta(days=365):raise RuleError('Schedule a policy within the next year.')
            parent=self.parent(scope);locked=self.effective(parent,on=effective.isoformat())[2] if parent else set()
            values={};reset=action=='policy_reset'
            for key,value in args.items():
                if key not in GAME_RULES['policies']:continue
                if key in locked:raise RuleError('The parent has locked '+key.replace('_',' ')+'.')
                if reset:continue
                if key=='medical':
                    if value not in GAME_RULES['medical']:raise RuleError('Choose a medical plan.')
                elif key=='dental':
                    if value not in GAME_RULES['dental']:raise RuleError('Choose a dental plan.')
                elif key in BOOL_FIELDS:value=flag(value)
                else:value=integer(value,*LIMITS.get(key,(0,200000)))
                values[key]=value
            # A reset is a dated replacement of this scope's overrides, not deletion of history.
            version=1+sum(p['scope']==scope for p in self.s['policies'])
            previous=[p for p in self.s['policies'] if p['scope']==scope and p['effective']<=effective.isoformat()]
            current={}
            for p in previous:current.update(p['values'])
            if reset:
                inherited=self.effective(parent,on=effective.isoformat())[0] if parent else GAME_RULES['policies']
                values={}
            locks=args.get('locked',[])
            if isinstance(locks,str):locks=[k.strip() for k in locks.split(',') if k.strip()]
            if any(k not in GAME_RULES['policies'] for k in locks):raise RuleError('Unknown locked policy field.')
            self.s['policies'].append(dict(id=self.uid('policy'),scope=scope,version=version,effective=effective.isoformat(),values=values,locked=locks,creator='Personal owner',reset=reset))
            self.e.event('Policy rollout scheduled',f'{scope}: version {version} takes effect {effective}. Earlier payroll stays unchanged.')
            return f'Policy version {version} scheduled for {effective}; {len(values)} fields affected.'
        if action=='delegation':
            b=self.rules.company(args.get('business_id',''))
            from .manager_defaults import limits
            previous=b.authority;defaults=limits(b)
            b.authority=dict(previous,auto_raises=flag(args.get('auto_raises',previous.get('auto_raises',True))),annual_raise_percent=integer(args.get('annual_raise_percent',previous.get('annual_raise_percent',3)),1,20),enabled=flag(args.get('enabled',defaults['enabled'])),salary_limit=integer(args.get('salary_limit',defaults['salary_limit'])),training_budget=integer(args.get('training_budget',defaults['training_budget'])),purchasing_limit=integer(args.get('purchasing_limit',defaults['purchasing_limit'])),staffing_target=integer(args.get('staffing_target',previous.get('staffing_target',len(open_positions(self.w,b.id)))),0,100),overtime_cap=integer(args.get('overtime_cap',defaults['overtime_cap']),40,60),spent=previous.get('spent',0) if previous.get('period')==self.w.date[:7] else 0,period=self.w.date[:7])
            return 'Manager authority recorded. Available managers handle staffing, stock, jobs, training, credential renewals, rentals and annual raises within the limits; exceptions appear in the inbox.'
        if action=='screen_candidate':
            b=self.rules.company(args.get('business_id',''));person=self.rules.person(args.get('person_id',''))
            if not person.candidate:raise RuleError('Choose an available candidate.')
            role=args.get('role','manager')
            if role not in INDUSTRY_ROLES[b.industry]:raise RuleError('Choose a role used by this company.')
            from .specialists import available,consume
            supported=available(self.w,b.id,'hr')>=120
            if supported:consume(self.w,b.id,'hr',120)
            cost=2500 if supported else 10000
            self.e.post(b.id,command_id,'Candidate screening',{'asset:cash':-cost,'expense:recruitment':cost})
            skill=ROLE_SKILLS[role];band=5 if supported else 10;estimate=person.skills.get(skill,30)//band*band
            self.s.setdefault('hr_screenings',[]).append(dict(entity=b.id,person_id=person.id,date=self.w.date,minutes=120 if supported else 0,cost=cost,low=estimate,high=min(100,estimate+band)))
            person.observations.append(dict(date=self.w.date,source='Recruitment interview',confidence='Moderate',detail=f'{skill.title()} estimate {estimate}–{min(100,estimate+band)}; qualifications and license dates checked.'))
            return f'Interview suggests {skill} in the {estimate}–{min(100,estimate+band)} range. The estimate is recorded; on-the-job demonstration is still required.'
        if action=='recruit':
            b=self.rules.company(args.get('business_id',''));channel=args.get('channel','local')
            if channel not in ('local','specialist','referral'):raise RuleError('Choose a recruitment channel.')
            role=args.get('role','cashier')
            if role not in INDUSTRY_ROLES[b.industry]:raise RuleError('Choose a role used by this business.')
            cost={'local':20000,'specialist':65000,'referral':35000}[channel]
            from .specialists import available,consume
            supported=available(self.w,b.id,'hr')>=240
            if supported:consume(self.w,b.id,'hr',240);cost=max(0,cost-15000)
            self.e.post(b.id,command_id,'Recruitment campaign',{'asset:cash':-cost,'expense:recruitment':cost})
            self.s['plans'].append(dict(id=self.uid('recruit'),kind='recruitment',entity=b.id,role=role,channel=channel,hr_minutes=240 if supported else 0,cost=cost,applicants_count=5 if supported else 3,due=(date.fromisoformat(self.w.date)+timedelta(days=(3 if channel=='referral' else 7)-(2 if supported else 0))).isoformat(),status='active'))
            return 'Recruitment is underway. Applicants arrive after the advertised lead time.'
        emp=self.rules.contract(args.get('employment_id',''));person=self.rules.person(emp.person_id);b=self.rules.company(emp.employer)
        if action=='reporting':
            from .employee_reporting import change
            return change(self.rules,emp,args.get('reports_to'))
        if action=='promote':
            target=self.rules.position(args.get('position_id',''))
            if not position_open(self.w,target):raise RuleError('This vacancy has been removed. Choose an open position.')
            if target.business_id!=b.id:raise RuleError('Promotion must be into a position in this business. Use a new employment for transfers.')
            if any(e.position_id==target.id and e.status in ('active','joining') for e in self.w.employments):raise RuleError('Choose a vacant position.')
            if target.role=='engineer' and not any('Engineering' in q for q in person.qualifications):raise RuleError('This role requires an engineering qualification.')
            from .specialists import LICENSES
            license_name=target.required_license or LICENSES.get(target.role)
            if license_name and person.licenses.get(license_name,'')<self.w.date:raise RuleError('Promotion requires a current license for the target position.')
            salary=integer(args.get('amount',emp.salary),10000,100000000)
            if salary<ROLE_PAY[target.role]*emp.weekly_hours*80//4000:raise RuleError('The promotion offer is below the role minimum.')
            if salary>emp.salary:
                from .leadership import mark_review
                mark_review(self.w,emp)
            previous=emp.position_id;emp.position_id=target.id;emp.salary=salary;emp.worked_days=0
            emp.probation_until=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat()
            person.loyalty=min(100,person.loyalty+6)
            self.rules.record(person.id,f'Promoted from {previous} to {target.role}; leadership ability must be demonstrated separately.')
            peers=[self.rules.person(e.person_id) for e in self.rules.staff(b.id) if e.id!=emp.id and self.rules.person(e.person_id).ambition==person.ambition]
            if peers:
                peer=peers[0];peer.relationships[person.id]='promotion rivalry';peer.morale=max(0,peer.morale-4)
                d=self.decision('promotion:'+command_id,'Promotion expectations',f'{peer.name} also wanted advancement. A development conversation may help.',b.id,{'mediate':'Fund mentoring and mediation','acknowledge':'Explain the decision without a funded program'},cost=25000);d['people']=[peer.id,person.id]
            return 'Promotion accepted. The old position is vacant; a 30-day onboarding period begins.'
        if action=='compensation':
            previous_pay=emp.salary
            mode=args.get('pay_basis','salary')
            if mode not in ('salary','hourly'):raise RuleError('Choose salary or hourly pay.')
            rate=integer(args.get('hourly_rate',0),0,50000)
            if mode=='hourly':
                if rate<1000:raise RuleError('The fictional ruleset minimum hourly wage is $10.')
                emp.salary=rate*emp.weekly_hours*52//12
            emp.compensation=dict(pay_basis=mode,hourly_rate=rate,shift_premium=integer(args.get('shift_premium',0),0,50000),commission_percent=integer(args.get('commission_percent',0),0,20),profit_share_percent=integer(args.get('profit_share_percent',0),0,20),bonus=integer(args.get('bonus',0),0,1000000))
            if emp.salary>previous_pay:
                from .leadership import mark_review
                mark_review(self.w,emp)
            bonus=emp.compensation['bonus']
            if bonus:self.e.post(b.id,command_id,'One-time employee bonus',{'asset:cash':-bonus,'expense:bonus':bonus})
            self.rules.record(person.id,'Compensation package changed prospectively; one-time bonus paid if offered.')
            return 'Compensation updated. Hourly pay uses scheduled hours; variable incentives are settled from actual monthly results.'
        if action=='renew_license':
            license_name=args.get('license','professional_engineer')
            if license_name not in ('professional_engineer','food_safety','legal_practice','accounting','security_guard','real_estate','electrical','plumbing','hvac'):raise RuleError('Choose a recognized license.')
            if license_name in ('electrical','plumbing','hvac') and not any('trade' in q.lower() for q in person.qualifications):raise RuleError('A trade qualification is required before a licensed trade course.')
            if license_name=='professional_engineer' and not any('Engineering' in q for q in person.qualifications):raise RuleError('An engineering degree is required for this professional license.')
            self.e.post(b.id,command_id,'Credential renewal',{'asset:cash':-25000,'expense:education':25000})
            self.s['plans'].append(dict(id=self.uid('license'),kind='license',person_id=person.id,license=license_name,due=(date.fromisoformat(self.w.date)+timedelta(days=30)).isoformat(),status='active'))
            return 'Credential course and renewal funded. Completion takes 30 days; licensed coverage remains unavailable until valid.'
        if action=='education':
            if person.education:raise RuleError('This person is already studying.')
            course=args.get('course','certificate')
            options={'certificate':(90,120000,'Industry certification'),'trade':(365,400000,'Trade qualification'),'associate':(730,800000,'Associate degree'),'bachelor':(1460,1800000,'Bachelor of Engineering'),'master':(730,1200000,'Master of Engineering'),'doctorate':(1095,1600000,'Doctorate in Engineering')}
            if course not in options:raise RuleError('Choose an offered course.')
            days,cost,title=options[course]
            self.e.post(b.id,command_id,'Employee education sponsorship',{'asset:cash':-cost,'expense:education':cost})
            person.education=dict(course=course,title=title,skill=args.get('skill','engineering'),due=(date.fromisoformat(self.w.date)+timedelta(days=days)).isoformat())
            if person.education['skill'] not in person.skills:raise RuleError('Choose an existing skill discipline.')
            return f'Study funded through {person.education["due"]}. Two scheduled hours per working day are reserved for study.'
        if action=='review_employee':
            self.e.post(b.id,command_id,'Employee development review',{'asset:cash':-10000,'expense:reviews':10000})
            role=self.rules.position(emp.position_id).role;skill=ROLE_SKILLS[role]
            person.observations.append(dict(date=self.w.date,source='Development review',confidence='Moderate',detail=f'Current role {skill}: {person.skills[skill]//10*10}–{min(100,person.skills[skill]//10*10+10)}. Morale {person.morale}; burnout {person.burnout}; manager trust {person.trust}.'))
            person.trust=min(100,person.trust+2)
            return 'Review recorded with a bounded skill estimate and known workplace concerns.'
        if action=='special_leave':
            kind=args.get('kind','sick');days=integer(args.get('days',1),1,90)
            if kind not in ('sick','parental','floating'):raise RuleError('Choose sick, parental or floating leave.')
            from .time_off import check_legacy
            check_legacy(self.w,emp,days,kind)
            used=sum((date.fromisoformat(self.w.date)+timedelta(days=i)).weekday() in emp.days for i in range(1,days+1))
            if kind=='sick':
                if used>emp.sick_balance:raise RuleError('Not enough paid sick days remain.')
                emp.sick_balance-=used
            elif kind=='floating':
                if used>emp.floating_balance:raise RuleError('Not enough floating holidays remain.')
                emp.floating_balance-=used
            elif any('Parental leave' in h['event'] and h['date'][:4]==self.w.date[:4] for h in person.history):raise RuleError('This fictional parental leave entitlement was already used this year.')
            emp.absence_until=(date.fromisoformat(self.w.date)+timedelta(days=days)).isoformat()
            self.rules.record(person.id,f'{kind.title()} leave approved through {emp.absence_until}; contractual pay continues.')
            return 'Leave approved. Scheduled coverage is removed for the approved dates.'
        raise RuleError('Unknown workforce decision.')

    def start_day(self):
        stop=False;today=date.fromisoformat(self.w.date)
        for plan in self.s['plans']:
            if plan['kind']=='license' and plan['status']=='active' and plan['due']<=self.w.date:
                self.rules.person(plan['person_id']).licenses[plan['license']]=(today+timedelta(days=1095)).isoformat();plan['status']='complete'
                self.e.event('Professional credential renewed',plan['license'].replace('_',' ').title()+' is valid for three simulated years.',True);stop=True
            if plan['kind']=='recruitment' and plan['status']=='active' and plan['due']<=self.w.date:
                applicants=[self.rules.make_person(plan['role'],candidate=True).id for _ in range(plan.get('applicants_count',3))]
                plan['applicants']=applicants
                plan['status']='complete';self.e.event('Recruitment applicants arrived',str(len(applicants))+' applicants are available in People. Qualifications and observed skills are visible; assessments can improve uncertain estimates.',True);stop=True
        for emp in self.w.employments:
            if emp.status=='active' and self.controlled(emp.employer) and today.month==1 and today.day==1:
                from .time_off import reserved
                policy=self.effective(emp.employer,emp)[0];emp.sick_balance=max(policy['sick_days'],reserved(self.w,emp,'sick'));emp.floating_balance=max(policy['floating_holidays'],reserved(self.w,emp,'floating'))
        for person in self.w.people:
            if person.education and person.education['due']<=self.w.date:
                course=person.education;person.qualifications.append(course['title']);skill=course['skill'];person.skills[skill]=min(100,person.skills[skill]+12)
                person.education={};person.loyalty=min(100,person.loyalty+10)
                self.rules.record(person.id,'Completed '+course['title']+'. A degree is recorded; role-specific ability still requires demonstration.')
            born=date.fromisoformat(person.birth_date);age=today.year-born.year-((today.month,today.day)<(born.month,born.day))
            active=[e for e in self.w.employments if e.person_id==person.id and e.status=='active' and self.controlled(e.employer)]
            if age>=67 and active and not person.notice_on:
                person.notice_on=(today+timedelta(days=90)).isoformat()
                d=self.decision('retirement:'+person.id,'Retirement notice',f'{person.name} plans to retire on {person.notice_on}. Recruit or promote a successor.',active[0].employer);d['people']=[person.id];stop=True
            if person.notice_on and person.notice_on<=self.w.date:
                for emp in active:emp.status='retired' if age>=67 else 'resigned';emp.end_date=self.w.date
                person.labor_state='retired' if age>=67 else 'unemployed';person.candidate=age<67;person.notice_on=None
                self.rules.record(person.id,'Employment ended after notice; career records retained.')
                self.e.event('Employee departure',person.name+' completed their notice. Vacant roles need coverage.',True);stop=True
        from .leadership import Leadership
        Leadership(self.e).start_day()
        return stop

    def before_work(self,emp,person,today):
        values,sources,locked=self.effective(emp.employer,emp)
        emp.enrollment=dict(plan=values['medical'],employer_share=values['employer_share'],monthly_employer_cost=self.benefit_cost(emp,values),effective=self.w.date)
        from .time_off import absent as is_absent
        absent=is_absent(self.w,emp,today.isoformat())
        holiday=values['paid_holidays'] and (today.month,today.day) in ((1,1),(7,4),(12,25))
        return values, absent or holiday

    def after_day(self):
        today=date.fromisoformat(self.w.date);stop=False
        for b in self.w.businesses:
            if not self.controlled(b.id):continue
            staff=self.rules.staff(b.id)
            if staff:
                target=sum((self.rules.person(e.person_id).trust+self.rules.person(e.person_id).morale)//2 for e in staff)//len(staff)
                b.culture+=max(-1,min(1,target-b.culture))
            if today.day==1 and staff:
                month=(today-timedelta(days=1)).isoformat()[:7]
                financial={}
                for day,balances in b.financial_days.items():
                    if day.startswith(month):
                        for key,value in balances.items():financial[key]=financial.get(key,0)+value
                revenue=-sum(v for k,v in financial.items() if k.startswith('income:') and not k.startswith('income:internal_') and k!='income:dividends')
                profit=-sum(v for k,v in financial.items() if k.startswith(('income:','expense:')))
                rates=[]
                for emp in staff:
                    pol=self.effective(b.id,emp)[0]
                    rates.append((emp,emp.compensation.get('commission_percent',pol['commission_percent']),emp.compensation.get('profit_share_percent',pol['profit_share_percent'])))
                commission_total=sum(x[1] for x in rates);share_total=sum(x[2] for x in rates)
                for emp,commission,share in rates:
                    incentive=max(0,revenue)*commission*min(20,commission_total)//max(1,commission_total*100)+max(0,profit)*share*min(20,share_total)//max(1,share_total*100)
                    if incentive:self.e.post(b.id,f'incentive:{emp.id}:{month}','Monthly commission and profit sharing',{'expense:incentives':incentive,'liability:payroll':-incentive})
                refunds=max(0,revenue)*min(20,commission_total)//2000
                if refunds:self.e.post(b.id,f'incentive-quality:{b.id}:{month}','Commission-related returns and quality allowance',{'expense:returns':refunds,'liability:payable':-refunds})
            for emp in staff:
                person=self.rules.person(emp.person_id)
                if today.weekday()==6:
                    person.loyalty=max(0,min(100,person.loyalty+(1 if person.morale>=70 and person.trust>=60 else -2 if person.morale<40 else 0)))
                    person.trust=max(0,min(100,person.trust+(-3 if b.payroll_overdue else 1 if person.morale>=65 else -1)))
                if today.day==1:
                    person.observations.append(dict(date=self.w.date,source='Monthly workplace check-in',confidence='Moderate',detail=f'Morale {person.morale}; trust {person.trust}; loyalty {person.loyalty}; burnout {person.burnout}. Pay fairness, workload, benefits and management drive these changes.'))
                    person.observations=person.observations[-36:]
                    if person.morale<40 and person.loyalty<50 and not person.notice_on and self.roll('workforce',1,100)<=min(35,50-person.morale):
                        person.notice_on=(today+timedelta(days=30)).isoformat()
                        d=self.decision('retention:'+person.id+':'+self.w.date,'Employee considering departure',f'{person.name} reported low satisfaction and plans to leave after notice. A retention payment and review may help, but workload still matters.',b.id,{'retain':'Fund retention and development','acknowledge':'Accept the notice and recruit'},cost=emp.salary//2);d['people']=[person.id];stop=True
            if today.day==1 and len(staff)>1 and b.culture<50 and self.roll('workforce',1,100)<=20:
                first,second=[self.rules.person(e.person_id) for e in staff[:2]]
                first.relationships[second.id]='resource conflict'
                d=self.decision('conflict:'+b.id+':'+self.w.date,'Team resource conflict',f'{first.name} and {second.name} raised competing workload requests after low trust and culture reports.',b.id,{'mediate':'Fund mediation','acknowledge':'Record the concern without funding'},cost=30000);d['people']=[first.id,second.id];stop=True
        return stop
