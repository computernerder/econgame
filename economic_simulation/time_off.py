"""Dated leave requests, reserved entitlements, approval and actual lost capacity."""
from datetime import date, timedelta
from .campaign import Campaign, integer, flag
from .domain import RuleError

KINDS={'vacation':'Vacation','sick':'Sick leave','floating':'Floating holiday','parental':'Parental leave','unpaid':'Unpaid leave'}
BANKS={'vacation':'leave_balance','sick':'sick_balance','floating':'floating_balance'}


def days_between(start,end):
    day=date.fromisoformat(start);last=date.fromisoformat(end)
    while day<=last:
        yield day
        day+=timedelta(days=1)


def requests(world,emp=None):
    return [r for r in world.systems.get('time_off_requests',[]) if emp is None or r['employment_id']==emp.id]


def active_request(world,emp,on=None):
    on=on or world.date
    return next((r for r in requests(world,emp) if r['status']=='approved' and r['start']<=on<=r['end']),None)


def absent(world,emp,on=None):
    on=on or world.date
    return bool((emp.leave_until or '')>=on or (emp.absence_until or '')>=on or active_request(world,emp,on))


def unpaid(world,emp,on=None):
    r=active_request(world,emp,on)
    return bool(r and r['kind']=='unpaid')


def scheduled(world,emp,start,end):
    from .workforce import Workforce
    from .domain import Engine
    wf=Workforce(Engine(world))
    return [d.isoformat() for d in days_between(start,end) if d.weekday() in emp.days
            and not (wf.effective(emp.employer,emp,on=d.isoformat())[0]['paid_holidays'] and (d.month,d.day) in ((1,1),(7,4),(12,25)))]


def reserved(world,emp,kind,exclude=''):
    return sum(sum(d>=world.date and d not in r['used_dates'] for d in r['work_dates']) for r in requests(world,emp)
               if r['status']=='approved' and r['kind']==kind and r['id']!=exclude)


def balances(world,emp):
    return [dict(kind=kind,label=KINDS[kind],balance=getattr(emp,attr),reserved=reserved(world,emp,kind),
                 available=max(0,getattr(emp,attr)-reserved(world,emp,kind))) for kind,attr in BANKS.items()]


def blockers(world):
    from .domain import Engine
    controlled=Campaign(Engine(world)).controlled
    active={e.id for e in world.employments if e.status=='active'}
    return [r for r in requests(world) if r['status']=='pending' and r['employment_id'] in active and controlled(r['entity']) and review_status(world,r)['state']=='player']


def policy(world,bid):
    return {'auto_approve':True,'max_days':5,'max_absent_percent':25,**world.systems.get('time_off_policies',{}).get(bid,{})}


def review_reason(world,r,require_available=True):
    from .domain import Engine
    from .leadership import Leadership
    from .employee_reporting import supervisor
    from .authority import Authority
    from .manager_defaults import limits
    leader=Leadership(Engine(world));emp=leader.rules.contract(r['employment_id'])
    business=leader.rules.company(emp.employer);pol=policy(world,emp.employer)
    if r['start']<=world.date:return 'The requested start date has passed; choose new dates.',None,None
    r={**r,'work_dates':scheduled(world,emp,r['start'],r['end'])}
    if not r['work_dates']:return 'The dates no longer include scheduled work; choose new dates.',None,None
    try:TimeOff(leader.e).check_balance(emp,r)
    except RuleError as error:return str(error),None,None
    if not limits(business)['enabled']:return 'Manager delegation is disabled. Review this request or enable daily management.',None,None
    if not pol['auto_approve']:return 'The time-off policy requires player review.',None,None
    if r['kind'] not in BANKS or len(r['work_dates'])>pol['max_days']:
        return 'The request exceeds the manager’s permitted leave type or duration.',None,None
    impact=coverage(world,emp,r)
    if impact['role_gap']:return 'Qualified coverage for this role would be missing on at least one day.',None,None
    if impact['max_absent_percent']>pol['max_absent_percent']:
        return 'The request exceeds the permitted share of staff absent at once.',None,None
    record,manager=leader.actor(business,'time_off_decide',dict(employment_id=emp.id))
    if emp.supervisor_id or not manager or manager.id==emp.id:
        # Preserve a named primary supervisor, including cross-company reporting.
        manager=supervisor(world,emp)
        inherited,_=leader.director(business.id,False)
        record=inherited if manager and inherited and inherited['employment_id']==manager.id else None
    if not manager and not emp.supervisor_id:
        # Remember the responsible employee while they are off duty. Temporary
        # absence need not turn a future routine request into a player decision.
        manager=next((e for e in leader.rules.staff(business.id) if e.person_id!=emp.person_id and
                      leader.rules.position(e.position_id).role in ('manager','property_manager')),None)
        inherited,director=leader.director(business.id,False)
        if not manager:record,manager=inherited,director
        elif inherited and manager.id==inherited['employment_id']:record=inherited
    if not manager or manager.person_id==emp.person_id:
        return 'No available authorized supervisor can approve this request; employees cannot approve their own leave.',record,manager
    reason=Authority(leader.e).check(business,record,'time_off_decide',dict(employment_id=emp.id,request_id=r['id']),0,world)
    if not reason and require_available and not leader.available(manager):
        return 'The responsible supervisor is off duty today.',record,manager
    return reason or '',record,manager


def review_status(world,r):
    """A read-only distinction between manager work and player exceptions."""
    from copy import copy
    from .domain import Engine
    from .leadership import Leadership
    reason,record,manager=review_reason(world,r,require_available=False)
    name=next((p.name for p in world.people if manager and p.id==manager.person_id),'')
    result=dict(state='player',reason=reason,reviewer=name,review_on='',
                policy_url='/?page=employee&employment_id='+r['employment_id']+'&scope='+r['entity']+'#time-off-policy')
    if reason:return result
    # The preview owns its date. Forecasting a review never changes the live
    # clock, requests, authority, leave banks or random state.
    preview=copy(world);leader=Leadership(Engine(preview))
    for day in days_between(world.date,r['start']):
        if day.isoformat()>=r['start']:break
        preview.date=day.isoformat()
        if leader.available(manager):
            result.update(state='manager',review_on=preview.date,
                reason=name+' will review this routine request '+('on the next daily review' if preview.date==world.date else 'on '+preview.date)+'. No player decision is needed; coverage and authority are rechecked before approval.')
            return result
    result['reason']=name+' is unavailable before the requested leave starts. Review it yourself, change the dates, or arrange an authorized supervisor.'
    return result


def check_legacy(world,emp,days,kind):
    start=(date.fromisoformat(world.date)+timedelta(days=1)).isoformat()
    end=(date.fromisoformat(world.date)+timedelta(days=days)).isoformat()
    if max(emp.leave_until or '',emp.absence_until or '')>=start or any(r['status'] in ('pending','approved') and r['start']<=end and r['end']>=start for r in requests(world,emp)):
        raise RuleError('This overlaps an existing time-off request or approved absence. Review the employee time-off calendar.')
    attr=BANKS.get(kind)
    used=sum(d.weekday() in emp.days for d in days_between(start,end))
    if attr and used>getattr(emp,attr)-reserved(world,emp,kind):raise RuleError('Insufficient available leave after existing reservations.')


def coverage(world,emp,request):
    from .specialists import LICENSES
    position=next(p for p in world.positions if p.id==emp.position_id)
    peers=[e for e in world.employments if e.employer==emp.employer and e.status=='active']
    worst=0;role_gap=False
    def qualified(peer,on):
        pos=next(p for p in world.positions if p.id==peer.position_id)
        person=next(p for p in world.people if p.id==peer.person_id)
        required=pos.required_license or LICENSES.get(pos.role)
        return pos.role==position.role and (not required or person.licenses.get(required,'')>=on)
    for value in request['work_dates']:
        scheduled_peers=[e for e in peers if date.fromisoformat(value).weekday() in e.days]
        off=[e for e in scheduled_peers if e.id==emp.id or absent(world,e,value)]
        worst=max(worst,len(off)*100//max(1,len(scheduled_peers)))
        role_gap=role_gap or not any(e.id!=emp.id and not absent(world,e,value) and
            qualified(e,value) for e in scheduled_peers)
    return dict(hours=round(len(request['work_dates'])*emp.weekly_hours/max(1,len(emp.days)),1),
                max_absent_percent=worst,role_gap=role_gap)


class TimeOff(Campaign):
    def employee(self,eid):
        from .business_rules import BusinessRules
        rules=BusinessRules(self.e);emp=rules.contract(eid);rules.company(emp.employer)
        if emp.status!='active':raise RuleError('Choose an active employee for time off.')
        return emp

    def action(self,action,args,source):
        if action=='time_off_policy':
            bid=self.require(args.get('business_id',''))
            self.s.setdefault('time_off_policies',{})[bid]=dict(auto_approve=flag(args.get('auto_approve')),
                max_days=integer(args.get('max_days',5),1,30),max_absent_percent=integer(args.get('max_absent_percent',25),0,100))
            return 'Time-off approval policy saved. Managers cannot approve their own leave or bypass a coverage exception.'
        if action=='time_off_request':
            emp=self.employee(args.get('employment_id',''));kind=args.get('kind','vacation')
            if kind not in KINDS:raise RuleError('Choose a supported time-off type.')
            try:start=date.fromisoformat(args.get('start',''));end=date.fromisoformat(args.get('end',''))
            except (ValueError,TypeError):raise RuleError('Enter valid start and end dates.')
            today=date.fromisoformat(self.w.date)
            if not today<start<=today+timedelta(days=365) or not start<=end<=start+timedelta(days=89):
                raise RuleError('Time off must start tomorrow or later within one year and last at most 90 calendar days.')
            if max(emp.leave_until or '',emp.absence_until or '')>=start.isoformat():raise RuleError('This overlaps existing approved leave.')
            if any(r['status'] in ('pending','approved') and r['start']<=end.isoformat() and r['end']>=start.isoformat() for r in requests(self.w,emp)):
                raise RuleError('This overlaps another pending or approved request.')
            work=scheduled(self.w,emp,start.isoformat(),end.isoformat())
            if not work:raise RuleError('Choose a period with at least one scheduled working day.')
            r=dict(id=self.uid('timeoff'),employment_id=emp.id,entity=emp.employer,kind=kind,start=start.isoformat(),end=end.isoformat(),
                   work_dates=work,used_dates=[],status='pending',created=self.w.date,reason=str(args.get('reason',''))[:250],
                   submitted_by=args.get('_submitted_by','Player'),reviewer='',resolution='',history=[])
            self.check_balance(emp,r)
            self.s.setdefault('time_off_requests',[]).append(r)
            review=review_status(self.w,r)
            self.e.event('Time-off approval needed' if review['state']=='player' else 'Time-off request with manager',
                         self.person_name(emp)+': '+KINDS[kind]+' requested '+r['start']+' through '+r['end']+'. '+review['reason'],
                         review['state']=='player',request_id=r['id'])
            return f'Request submitted for {len(work)} working days ({coverage(self.w,emp,r)["hours"]:g} scheduled hours). '+review['reason']
        r=next((r for r in requests(self.w) if r['id']==args.get('request_id')),None)
        if not r:raise RuleError('Choose an existing time-off request.')
        self.require(r['entity'])
        if action=='time_off_cancel':
            if r['status'] not in ('pending','approved'):raise RuleError('Only pending or approved leave can be cancelled.')
            if r['status']=='approved' and r['start']<=self.w.date:raise RuleError('Leave already underway cannot be cancelled retroactively.')
            r.update(status='cancelled',resolution=self.w.date,reviewer='Player')
            r['history'].append(dict(date=self.w.date,action='Cancelled; unused reserved days released.',actor='Player'))
            self.e.event('Time off cancelled',r['id']+': unused reservations released; no payroll history changed.')
            return 'Request cancelled. Reserved days are available again; no leave or wages were charged.'
        if action!='time_off_decide':raise RuleError('Unknown time-off action.')
        return self.decide(r,args.get('choice','approve'),'Player')

    def person_name(self,emp):return next(p.name for p in self.w.people if p.id==emp.person_id)

    def check_balance(self,emp,r):
        attr=BANKS.get(r['kind'])
        if attr and len(r['work_dates'])>getattr(emp,attr)-reserved(self.w,emp,r['kind'],r['id']):
            raise RuleError('Insufficient available '+KINDS[r['kind']].lower()+' days after existing reservations. Shorten the request or choose unpaid leave.')
        if r['kind']=='parental' and any(x['kind']=='parental' and x['id']!=r['id'] and x['status'] in ('approved','completed') and x['start'][:4]==r['start'][:4] for x in requests(self.w,emp)):
            raise RuleError('Parental leave is already approved for this employee in that year.')
        person=next(p for p in self.w.people if p.id==emp.person_id)
        if r['kind']=='parental' and any(h['event'].startswith('Parental leave approved through') and h['date'][:4]==r['start'][:4] for h in person.history):
            raise RuleError('Parental leave was already used under the existing agreement this year.')

    def decide(self,r,choice,reviewer):
        if r['status']!='pending':raise RuleError('This request is no longer awaiting approval.')
        if choice not in ('approve','decline'):raise RuleError('Choose approve or decline.')
        emp=self.employee(r['employment_id'])
        if choice=='approve':
            if r['start']<=self.w.date:raise RuleError('The requested start date has passed. Decline it and request new future dates.')
            r['work_dates']=scheduled(self.w,emp,r['start'],r['end']);self.check_balance(emp,r)
            if not r['work_dates']:raise RuleError('These dates no longer include scheduled working days. Submit new dates.')
        r.update(status='approved' if choice=='approve' else 'declined',reviewer=reviewer,resolution=self.w.date)
        r['history'].append(dict(date=self.w.date,action=r['status'],actor=reviewer))
        person=next(p for p in self.w.people if p.id==emp.person_id)
        detail=f'{KINDS[r["kind"]]} {r["status"]}: {r["start"]} to {r["end"]}; reviewed by {reviewer}.'
        person.history.append(dict(date=self.w.date,event=detail))
        self.e.event('Time-off decision',self.person_name(emp)+': '+detail)
        impact=coverage(self.w,emp,r)
        return detail+f' {impact["hours"]:g} scheduled hours affected; up to {impact["max_absent_percent"]}% of the team absent.'+(' Same-role coverage is missing on at least one day.' if impact['role_gap'] else '')+(' Paid days are reserved now and used only on scheduled days off.' if choice=='approve' and r['kind'] in BANKS else '')

    def tick(self):
        from .business_rules import BusinessRules
        from .employee_reporting import reconcile
        from .simulation_support import stable_roll
        reconcile(self.e);rules=BusinessRules(self.e)
        for r in requests(self.w):
            emp=next(e for e in self.w.employments if e.id==r['employment_id'])
            if r['status'] in ('pending','approved') and (emp.status!='active' or not self.controlled(emp.employer)):
                r.update(status='cancelled',resolution=self.w.date,reviewer='Employment ended or left owned group');continue
            if r['status']=='pending' and r['start']<=self.w.date:
                r.update(status='expired',resolution=self.w.date,reviewer='No approval by start date')
                self.e.event('Time-off request expired',self.person_name(emp)+': no absence was authorized. Request new future dates.');continue
            if r['status']=='approved':
                if self.w.date in r['work_dates'] and self.w.date not in r['used_dates'] and scheduled(self.w,emp,self.w.date,self.w.date):
                    attr=BANKS.get(r['kind'])
                    if attr:setattr(emp,attr,max(0,getattr(emp,attr)-1))
                    r['used_dates'].append(self.w.date)
                if self.w.date>r['end']:r['status']='completed'
        # Requests are deterministic and infrequent; no new random economic draws.
        today=date.fromisoformat(self.w.date)
        if today.day==1:
            for emp in self.w.employments:
                if emp.status!='active' or not self.controlled(emp.employer) or emp.leave_balance-reserved(self.w,emp,'vacation')<3:continue
                if any(r['status'] in ('pending','approved') for r in requests(self.w,emp)):continue
                if stable_roll(self.w,emp.id+':leave-request:'+self.w.date,100)>=12:continue
                start=today+timedelta(days=14)
                try:self.action('time_off_request',dict(employment_id=emp.id,kind='vacation',start=start.isoformat(),end=(start+timedelta(days=2)).isoformat(),reason='Requested rest and personal time.',_submitted_by=self.person_name(emp)),'employee-request')
                except RuleError:pass # An overlapping legacy absence or exhausted entitlement does not create a request.
        self.review_pending()
        if blockers(self.w):self.e.pause_reasons.append(dict(title='Time-off approval needed',financial_amount=None))
        else:self.e.pause_reasons[:]=[r for r in self.e.pause_reasons if r['title']!='Time-off approval needed']

    def review_pending(self):
        from .business_rules import BusinessRules
        rules=BusinessRules(self.e)
        active={emp.id for emp in self.w.employments if emp.status=='active' and self.controlled(emp.employer)}
        for r in requests(self.w):
            if r['status']!='pending' or r['employment_id'] not in active:continue
            reason,record,manager=review_reason(self.w,r)
            if reason:continue
            business=rules.company(r['entity'])
            try:outcome=self.decide(r,'approve',self.person_name(manager))
            except RuleError:continue
            from .authority import Authority
            Authority(self.e).record(business,record,manager,'time_off_decide',0,0,outcome)
