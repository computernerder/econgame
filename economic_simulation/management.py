"""Portfolio-wide leadership directory and operational policy settings."""
from datetime import date,timedelta
from .positions import open_positions
from .campaign import Campaign,integer,flag
from .domain import Engine,RuleError
from .business_models import INDUSTRY_ROLES
from .industries import SALES

HIRING={'freeze':'Hiring freeze','vacancies':'Fill existing vacancies','target':'Fill vacancies up to staff target','grow':'Create roles up to staff target'}
GROWTH={'off':'Hold current size','review':'Propose equipment growth for approval','auto':'Expand equipment within limits'}


def policy(b,world=None):
    defaults=dict(hiring='target',hiring_role=INDUSTRY_ROLES[b.industry][1] if len(INDUSTRY_ROLES[b.industry])>1 else INDUSTRY_ROLES[b.industry][0],growth='off',growth_target=120,growth_budget=0,cash_reserve=0,training=True,rentals=True,jobs=b.auto_projects,stock=b.auto_restock)
    if world:
        from .director_scope import coverage
        record=coverage(world).get(b.id,(None,None))[0]
        if record:defaults.update(growth='auto',growth_target=120 if b.industry in ('engineering','trades','construction') else 160,growth_budget=record['limit']*4)
    return {**defaults,**b.authority.get('operating_policy',{})}


def growth_status(world,b):
    p=policy(b,world);cost=max(500000,b.equipment//4)
    spent=sum(x.get('cost',0) for x in world.systems['plans'] if x['kind']=='upgrade' and x.get('entity')==b.id and (x.get('created') or (date.fromisoformat(x['due'])-timedelta(days=21)).isoformat())[:7]==world.date[:7])
    reserve=max(p['cash_reserve'],sum(e.salary for e in world.employments if e.employer==b.id and e.status in ('active','joining'))//4)
    cutoff=(date.fromisoformat(world.date)-timedelta(days=30)).isoformat()
    profit=-sum(v for day,accounts in b.financial_days.items() if cutoff<=day<world.date for key,v in accounts.items() if key.startswith(('income:','expense:')))
    default_growth='growth' not in b.authority.get('operating_policy',{})
    history=[day for day in b.history if cutoff<=day['date']<world.date]
    busy=[day for day in history if day.get('capacity',day.get('qualified_capacity',0))>0]
    utilized=bool(busy) and sum(day.get('output',0) for day in busy)*100>=85*sum(day.get('capacity',day.get('qualified_capacity',0)) for day in busy)
    reason='Ready for next weekly leadership review'
    if p['growth']=='off':reason='Growth disabled'
    elif b.industry not in set(SALES)|{'engineering','trades','construction','factory','logistics','cleaning','landscaping','security'}:reason='This industry needs a specialist growth project'
    elif b.status!='operating':reason='Business must be operating'
    elif b.capacity_percent>=min(200,p['growth_target']):reason='Capacity target reached'
    elif any(x['kind']=='upgrade' and x.get('entity')==b.id and x['status']=='active' for x in world.systems['plans']):reason='Equipment expansion in progress'
    elif any(x['kind']=='business_sale' and x['status']=='active' and b.id in x.get('entities',[]) for x in world.systems['plans']):reason='Sale is pending'
    elif profit<=0:reason='Waiting for positive profit over the last 30 days'
    elif default_growth and len(history)<14:reason='Director is gathering 14 operating days before expansion'
    elif default_growth and not utilized:reason='Director is waiting for sustained use of at least 85% of existing capacity'
    elif cost>max(0,p['growth_budget']-spent):reason='Monthly growth budget is insufficient'
    elif world.cash(b.id)-cost<reserve:reason='Preserving cash and payroll reserve'
    return dict(ready=reason=='Ready for next weekly leadership review',reason=reason,cost=cost,reserve=reserve,spent=spent,profit=profit,operating_days=len(history),utilized=utilized)


class Management(Campaign):
    def action(self,args):
        from .business_rules import BusinessRules
        rules=BusinessRules(self.e);target=args.get('target','')
        if not isinstance(target,str):raise RuleError('Choose a business or director.')
        if target.startswith('director:'):
            employment=target.split(':',1)[1]
            director=next((d for d in self.s.get('directors',[]) if d['active'] and d['employment_id']==employment),None)
            employee=next((e for e in self.w.employments if e.id==employment and e.status=='active'),None)
            if not director or not employee:raise RuleError('Choose an active employee director.')
            self.require(employee.employer)
            from .director_scope import assigned
            businesses=[rules.company(bid) for bid in assigned(self.w,director)]
        else:businesses=[rules.company(target)]
        if not businesses:raise RuleError('This director has no assigned businesses.')
        changes={}
        for key,options in [('hiring',HIRING),('growth',GROWTH)]:
            if args.get(key,'')!='':
                if args[key] not in options:raise RuleError('Choose a supported '+key+' policy.')
                changes[key]=args[key]
        for key,low,high in [('growth_target',100,200),('growth_budget',0,1000000000),('cash_reserve',0,1000000000)]:
            if key in args:changes[key]=integer(args[key],low,high)
        for key in ('training','rentals','jobs','stock'):
            if key in args:changes[key]=flag(args[key])
        if args.get('hiring_role'):
            if any(args['hiring_role'] not in INDUSTRY_ROLES[b.industry] for b in businesses):raise RuleError('The hiring role must be supported by every selected business.')
            changes['hiring_role']=args['hiring_role']
        target_staff=integer(args['staffing_target'],0,100) if 'staffing_target' in args else None
        for b in businesses:
            # Only submitted choices are overrides; unrelated defaults stay live.
            b.authority['operating_policy']={**b.authority.get('operating_policy',{}),**changes}
            if target_staff is not None:b.authority['staffing_target']=target_staff
            p=policy(b,self.w);b.auto_restock=p['stock'];b.auto_projects=p['jobs']
            self.e.event('Management policy updated',b.name+': '+HIRING[p['hiring']]+'; '+GROWTH[p['growth']]+'. Manager and director follow this business policy within their authority.')
        return f'Policies updated for {len(businesses)} business(es). Authority limits, payroll and existing commitments are preserved.'

    def overview(self,search=''):
        from .leadership import Leadership
        from .business_views import entity_names
        leadership=Leadership(self.e);names=entity_names(self.w)
        rows=[];directory={}
        for b in sorted((b for b in self.w.businesses if self.controlled(b.id)),key=lambda b:b.name.casefold()):
            manager_staff=[e for e in self.w.employments if e.employer==b.id and e.status=='active' and leadership.rules.position(e.position_id).role in ('manager','property_manager')]
            record,director=leadership.director(b.id,False)
            from .director_scope import coverage
            inherited=coverage(self.w).get(b.id,(None,None))[1]
            manager_names=[]
            for employee in manager_staff+([director] if director and director.id not in {e.id for e in manager_staff} else []):
                person=leadership.rules.person(employee.person_id)
                entry=directory.setdefault(employee.id,dict(id=employee.id,name=person.name,employer=names.get(employee.employer,employee.employer),roles=set(),businesses=[],director=False,limit=None))
                if director and employee.id==director.id:
                    from .leadership_history import LABELS
                    entry.update(director=True,limit=record['limit']);entry['roles'].add(LABELS[record.get('role','director')])
                if employee in manager_staff:entry['roles'].add('Manager');manager_names.append(person.name)
                if b.name not in entry['businesses']:entry['businesses'].append(b.name)
            rows.append(dict(id=b.id,name=b.name,managers=manager_names,director=leadership.rules.person(director.person_id).name if director else None,director_limit=record['limit'] if record else None,enabled=b.authority.get('enabled',True),active=leadership.view(b)['active_name'],policy=policy(b,self.w),growth=growth_status(self.w,b),target=b.authority.get('staffing_target',len(open_positions(self.w,b.id))),roles=INDUSTRY_ROLES[b.industry]))
            rows[-1]['inherited_from']=names.get(inherited) if inherited and inherited!=b.id else None
        people=sorted(directory.values(),key=lambda x:x['name'].casefold())
        if search:
            q=search.casefold();rows=[r for r in rows if q in ' '.join([r['name'],*r['managers'],r['director'] or '']).casefold()]
            people=[p for p in people if q in ' '.join([p['name'],p['employer'],*p['businesses']]).casefold()]
        from .authority import Authority,GROUPS
        authority=Authority(self.e)
        for row in rows:
            b=leadership.rules.company(row['id'])
            director_record,_=leadership.director(b.id,False)
            oversight={r['employment_id'] for r in self.s.get('directors',[]) if r['active'] and r['business_ids']}
            oversight.update(r['employment_id'] for r in self.s.get('executives',{}).values() if r['active'])
            local=any(e.employer==b.id and e.status=='active' and e.id not in oversight and leadership.rules.position(e.position_id).role in ('manager','property_manager') for e in self.w.employments)
            row['authority']=authority.view(b,None if local else director_record)
            row['director_authority']=authority.view(b,director_record) if director_record and local else None
            from .routine_management_views import controls
            row['routine_form']=controls(self.w,b)
        return dict(rows=rows,people=people,hiring=HIRING,growth=GROWTH,business_count=len(rows),director_count=sum(p['director'] for p in people),manager_count=sum('Manager' in p['roles'] for p in people),authority_groups=GROUPS,contracts=authority.contracts())
