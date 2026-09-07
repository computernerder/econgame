"""A bounded fictional regional economy, observed trends and delayed civic outcomes."""
from __future__ import annotations
from datetime import date,timedelta
from .campaign import Campaign,integer,flag
from .domain import GAME_RULES,RuleError,daily_share
from .business_rules import BusinessRules


def bounded(value,low=0,high=100):return max(low,min(high,value))


class Economy(Campaign):
    def region(self,name):
        region=next((r for r in self.s['regions'] if r['id']==name),None)
        if not region:raise RuleError('Choose an available region.')
        return region

    def action(self,action,args,command_id):
        entity=self.require(args.get('entity','personal'))
        if action=='civic_project':
            region=self.region(args.get('region','Rutland County'));kind=args.get('kind','scholarships')
            if kind not in GAME_RULES['civic']:raise RuleError('Choose an available community project.')
            if sum(p['region']==region['id'] and p['status']=='active' for p in self.s['civic'])>=3:raise RuleError('The region can implement at most three civic projects at once.')
            spec=GAME_RULES['civic'][kind];year=self.w.date[:4]
            cofund_used=sum(p.get('cofund',0) for p in self.s['civic'] if p['region']==region['id'] and p['created'][:4]==year)
            cofund=min(spec['cost']//5,max(0,1000000-cofund_used)) if flag(args.get('cofund',True)) else 0
            cost=spec['cost']-cofund
            self.e.post(entity,command_id,'Regional '+kind+' funding',{'asset:cash':-cost,'expense:civic':cost})
            project=dict(id=self.uid('civic'),kind=kind,region=region['id'],entity=entity,created=self.w.date,due=(date.fromisoformat(self.w.date)+timedelta(days=spec['days'])).isoformat(),cost=cost,cofund=cofund,status='active',driver=spec['driver'],gain=spec['gain'],outcome=None)
            self.s['civic'].append(project)
            return f'Project funded for ${cost/100:,.2f}, with ${cofund/100:,.2f} public co-funding. Evaluation is due {project["due"]}; benefits are delayed and shared with the region.'
        if action=='insurance':
            b=BusinessRules(self.e).company(args.get('business_id',''));tier=args.get('tier','basic')
            if tier not in ('none','basic','comprehensive'):raise RuleError('Choose an insurance plan.')
            prices={'none':(0,0,0),'basic':(5000,20000,500000),'comprehensive':(12000,10000,1500000)}
            premium,deductible,limit=prices[tier]
            b.insurance=dict(tier=tier,premium=premium,deductible=deductible,limit=limit,effective=self.w.date)
            return f'{tier.title()} insurance begins today: ${premium/100:,.2f}/month, ${deductible/100:,.2f} deductible, ${limit/100:,.2f} per-incident limit. Claims settle after 30 days; basic coverage excludes fraud.'
        raise RuleError('Unknown regional action.')

    def demand_factor(self,b):
        region=self.region(b.region)
        competitor=next((c for c in self.s['competitors'] if c['region']==b.region and c['status']=='operating'),None)
        pressure=95 if competitor and competitor['reputation']>70 else 100
        return bounded(region['demand']*self.s['cycle']*pressure//10000,55,155)

    def tick(self,today):
        stop=False
        for b in self.w.businesses:
            if b.owner and b.insurance.get('premium'):
                premium=daily_share(b.insurance['premium'],today)
                self.e.post(b.id,f'insurance-premium:{b.id}:{self.w.date}','Commercial insurance premium',{'expense:insurance':premium,'liability:payable':-premium})
        for claim in self.s['claims']:
            if claim['status']=='pending' and claim['due']<=self.w.date:
                self.e.post(claim['entity'],'insurance-claim:'+claim['id'],'Insurance settlement for recorded loss',{'asset:cash':claim['amount'],'income:insurance':-claim['amount']});claim['status']='paid'
        for project in self.s['civic']:
            if project['status']=='active' and project['due']<=self.w.date:
                region=self.region(project['region']);previous=sum(p['region']==region['id'] and p['kind']==project['kind'] and p['status']=='complete' for p in self.s['civic'])
                base=abs(project['gain']);gain=max(1,base//(1+previous//3))*self.roll('projects',60,110)//100
                if project['gain']<0:gain=-gain
                key=project['driver'];before=region[key];region[key]=bounded(region[key]+gain,50 if key=='rent' else 0,150 if key=='rent' else 100)
                project.update(status='complete',outcome=dict(before=before,after=region[key],measured_date=self.w.date,confidence='Moderate; other regional changes also contribute'))
                self.e.event('Civic project evaluated',project['kind'].title()+' in '+region['id']+' completed. '+key.title()+f' moved from {before} to {region[key]}; improvements are shared with other employers.',True);stop=True
        if today.day!=1:return stop
        month=today.year*12+today.month
        # One correlated cycle, with persistent bounded regional variation.
        phase=month%96;cycle=90+phase//2 if phase<48 else 114-(phase-48)//2
        self.s['cycle']=bounded(cycle+self.roll('economy',-2,2),85,115)
        self.s['inflation']=self.s['inflation']*10017//10000
        self.s['interest_bps']=bounded(500+(self.s['cycle']-100)*8,300,900)
        for region in self.s['regions']:
            observed={k:region[k] for k in ('income','wages','demand','employment','education','infrastructure','crime','rent')}
            region['history'].append(dict(date=(today-timedelta(days=1)).isoformat(),values=observed,confidence='±3 index points; published with one-month lag'))
            region['history']=region['history'][-360:]
            region['demand']=bounded(region['demand']+self.roll('economy',-2,2),75,135)
            region['wages']=bounded(region['wages']+self.roll('economy',-1,1),80,140)
            region['crime']=bounded(region['crime']+self.roll('economy',-1,1),5,65)
            region['employment']=bounded(region['employment']+self.roll('economy',-1,1),75,99)
            graduates=max(1,region['population']*region['education']//1200000);region['graduates']+=graduates
            region['unemployed']=region['population']*(100-region['employment'])//100
            region['underemployed']=region['population']*(110-region['employment'])//400
            region['cohort_population']=max(0,region['population']-sum(p.home_region==region['id'] for p in self.w.people))
        for p in self.w.properties:
            if p.status in ('sold','expired'):continue
            region=self.region(p.region)
            change=bounded((region['rent']-100)//10+self.roll('economy',-1,2),-3,4)
            p.full_value=p.full_value*(1000+change)//1000
            if p.status=='market':p.asking=p.value*94//100
        self.competitors(today)
        for b in self.w.businesses:
            if not self.controlled(b.id) or b.status!='operating':continue
            region=self.region(b.region)
            from .workforce import Workforce
            security=Workforce(self.e).effective(b.id)[0]['security']
            risk=max(1,region['crime']//4-security*2)
            if self.roll('crime',1,100)>risk:continue
            kind=('theft','vandalism','fraud','safety_disruption')[self.roll('crime',0,3)]
            loss=0;props=[p for p in self.w.properties if p.owner==b.id]
            if kind=='theft' and b.inventory_units:
                units=min(b.inventory_units,self.roll('crime',1,8));loss=units*b.unit_cost;b.inventory_units-=units
                self.e.post(b.id,f'incident:{b.id}:{self.w.date}','Recorded inventory theft',{'asset:inventory':-loss,'expense:shrinkage':loss})
            elif kind=='vandalism' and props:
                p=props[0];p.condition=max(0,p.condition-5);loss=25000
                self.e.post(b.id,f'incident:{b.id}:{self.w.date}','Vandalism cleanup obligation',{'expense:incident':loss,'liability:payable':-loss})
            else:
                loss=min(self.w.cash(b.id),self.roll('crime',10000,70000))
                if loss:self.e.post(b.id,f'incident:{b.id}:{self.w.date}',kind.replace('_',' ').title()+' loss',{'asset:cash':-loss,'expense:incident':loss})
                if kind=='safety_disruption':b.disrupted_until=(today+timedelta(days=2)).isoformat()
            for emp in BusinessRules(self.e).staff(b.id):
                person=BusinessRules(self.e).person(emp.person_id);person.trust=max(0,person.trust-3)
            insurance=b.insurance
            insured=insurance.get('tier') in ('basic','comprehensive') and (kind!='fraud' or insurance['tier']=='comprehensive')
            covered=min(max(0,loss-insurance.get('deductible',0)),insurance.get('limit',0)) if insured else 0
            if covered:self.s['claims'].append(dict(id=self.uid('claim'),entity=b.id,kind=kind,loss=loss,amount=covered,due=(today+timedelta(days=30)).isoformat(),status='pending'))
            self.decision('incident:'+b.id+':'+self.w.date,'Recorded '+kind.replace('_',' '),f'{b.name} recorded a ${loss/100:,.2f} loss. Security and regional conditions affect risk; no individual guilt is inferred. Pending insurance settlement ${covered/100:,.2f}.',b.id,days=7,financial_amount=None if kind=='safety_disruption' else loss);stop=True
        return stop

    def competitors(self,today):
        if not self.s['competitors']:
            for region in self.s['regions']:
                from .world_names import business_name
                label=business_name(self.w,'competitor:'+region['id'],'retail')
                self.s['competitors'].append(dict(id=self.uid('competitor'),name=label,region=region['id'],cash=2500000,inventory=500000,staff=8,capacity=120,reputation=60,wage=250000,status='operating',history=[],capital=3000000,profit=0))
        for firm in self.s['competitors']:
            if firm['status']!='operating':continue
            region=self.region(firm['region']);revenue=min(firm['capacity']*2200*20,region['demand']*2200*20);stock=revenue//2
            wages=firm['staff']*firm['wage'];overhead=200000
            available=firm['cash']+revenue;expense=stock+wages+overhead
            if expense>available:
                firm['staff']=max(0,firm['staff']-1);expense=min(available,expense)
            profit=revenue-expense;firm['cash']+=profit;firm['profit']+=profit
            firm['history'].append(dict(date=self.w.date,revenue=revenue,expense=expense,cash=firm['cash'],staff=firm['staff']));firm['history']=firm['history'][-360:]
            if firm['cash']>5000000 and firm['staff']<20:
                cost=1000000;firm['cash']-=cost;firm['inventory']+=cost;firm['capacity']+=10;firm['staff']+=1
            if firm['cash']==0 and firm['staff']==0:firm['status']='closed'
            firm['reputation']=bounded(firm['reputation']+self.roll('competitors',-1,1),30,90)
            if firm['cash']+firm['inventory']!=firm['capital']+firm['profit']:raise RuleError('Competitor aggregate assets do not reconcile.')
