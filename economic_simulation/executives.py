"""Optional employee executives allocate approved resources and service priorities."""
import copy
from datetime import date
from .campaign import Campaign,integer
from .domain import Engine,RuleError
from .authority import Authority,cash_forecast


def records(world):
    """Promoted directors keep their original scope and authority record."""
    return [*world.systems.get('executives',{}).values(),
            *(r for r in world.systems.get('directors',[]) if r.get('role') in ('home_office_director','division_vp','corporate_services_vp'))]


class Executives(Campaign):
    def action(self,args):
        from .business_rules import BusinessRules
        rules=BusinessRules(self.e);emp=rules.contract(args.get('employment_id',''))
        if emp.status!='active':raise RuleError('Appoint an active employee.')
        role=args.get('role','home_office_director')
        if role not in ('home_office_director','division_vp','corporate_services_vp'):raise RuleError('Choose a supported executive role.')
        scope=sorted({bid.strip() for bid in str(args.get('business_ids','')).split(',') if bid.strip()})
        if not scope or len(scope)>8:raise RuleError('Assign between one and eight businesses.')
        for bid in scope:self.require(bid)
        if any(r['active'] and r['business_ids'] and r['employment_id']==emp.id for r in self.s.get('directors',[])):
            raise RuleError('Remove the director assignment before appointing this employee as an executive; oversight time cannot be counted twice.')
        if len(scope)*30+180>emp.weekly_hours*60//max(1,len(emp.days)):raise RuleError('This scope exceeds the executive’s scheduled capacity.')
        if any(a['active'] and a['employment_id']==emp.id for a in self.s['assignments']):raise RuleError('End shared assignments before assigning executive time.')
        record=dict(employment_id=emp.id,role=role,business_ids=scope,employer=emp.employer,
            authority_key='executive:'+emp.id,active=True,appointed=self.w.date,limit=integer(args.get('limit',1000000),0,1000000000))
        self.require(emp.employer)
        from .leadership_pay import quote,apply
        from .leadership_history import duties,record_change
        previous=duties(self.w,emp)
        pay_detail=apply(rules,emp,quote(self.w,emp,role,scope))
        self.s.setdefault('executives',{})[emp.id]=record
        record_change(rules,emp,previous)
        return pay_detail+' Executive appointed as an employee. Their existing employer and primary reporting line remain; oversight consumes scheduled time. Save an authority contract before resource allocation.'

    def reserved(self,emp):
        record=self.s.get('executives',{}).get(emp.id)
        return len(record['business_ids'])*30 if record and record['active'] and date.fromisoformat(self.w.date).weekday() in emp.days else 0

    def tick(self):
        from .leadership import Leadership
        leadership=Leadership(self.e);authority=Authority(self.e)
        for record in records(self.w):
            emp=next((e for e in self.w.employments if e.id==record['employment_id']),None)
            if not record['active'] or not leadership.available(emp):continue
            owner=leadership.rules.company(emp.employer)
            key=record['authority_key'];contract=authority.contracts().get(key)
            if not contract and key.startswith('director:'):
                grants=authority.grants(owner,record);contract=grants[0][1] if grants else None
            if not contract:continue
            objective=contract['objective']
            if record['role'] in ('home_office_director','corporate_services_vp'):
                changed=[]
                for task in self.s.get('service_tasks',[]):
                    if task['provider'] not in record['business_ids'] or task['status'] not in ('queued','working'):continue
                    provider=leadership.rules.company(task['provider'])
                    grants=authority.grants(owner,record)
                    if not grants or any(provider.id not in grant['businesses'] or provider.region not in grant['regions'] or grant['actions'].get('purchasing')!='allow' for _,grant in grants):continue
                    before=task['priority']
                    if objective=='preserve_cash' and task['department'] in ('finance','legal','accounting'):task['priority']=1
                    elif objective=='growth' and task['department'] in ('hr','it','marketing','training'):task['priority']=1
                    if task['priority']!=before:changed.append(task['id'])
                if changed:
                    detail='Prioritized service tasks '+', '.join(changed)+' for '+objective.replace('_',' ')+'. Delivery still requires qualified staff time.'
                    authority.record(owner,record,emp,'service_priority',0,0,detail,outcome=detail)
                    self.e.event('Executive service priorities updated',leadership.rules.person(emp.person_id).name+': '+detail)
            if date.fromisoformat(self.w.date).weekday()!=0:continue
            if owner.id not in contract['businesses']:continue
            candidates=[b for b in self.w.businesses if b.id in record['business_ids'] and b.owner==owner.id and b.status=='operating']
            candidates.sort(key=lambda b:cash_forecast(self.w,b.id,14)['available'])
            for b in candidates:
                cash=cash_forecast(self.w,b.id,14)
                needed=max(0,-cash['available'])
                if objective=='growth' and b.authority.get('operating_policy',{}).get('growth')=='auto':needed=max(needed,max(500000,b.equipment//4)-cash['available'])
                if needed<=0:continue
                args=dict(business_id=b.id,amount=needed)
                try:
                    if needed>leadership.budget(record):raise RuleError('The allocation exceeds this executive’s remaining daily resource limit.')
                    preview=Engine(copy.deepcopy(self.w));preview.action('fund_business',args,'executive-preview');preview.validate()
                    refusal=authority.check(owner,record,'fund_business',args,needed,preview.world)
                    if refusal:raise RuleError(refusal)
                    self.e.action('fund_business',args,key+':'+b.id+':'+self.w.date)
                    record['spent']+=needed
                    authority.record(owner,record,emp,'fund_business',needed,needed,'Approved resource allocation to '+b.name)
                    self.e.event('Executive resources allocated',b.name+f' received ${needed/100:,.2f} from its actual parent account. This is capital, not profit.')
                except RuleError as error:
                    leadership.request(owner,'vp-funding:'+b.id,'fund_business',args,needed,'Recommended working capital for '+b.name+'. '+str(error))
