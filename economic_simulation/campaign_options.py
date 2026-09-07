"""Campaign options, optional succession, separate starts and deterministic forecasts."""
from __future__ import annotations
import copy
from datetime import date,timedelta
from .campaign import Campaign,integer,flag
from .domain import Engine,RuleError,new_game
from .business_views import entity_names,group_profit,own_equity


class CampaignOptions(Campaign):
    def action(self,action,args,command_id):
        if action=='settings':
            settings=self.s['settings']
            changes={}
            for key in ('succession','digest_only','pause_routine'):
                if key in args:changes[key]=flag(args[key])
            for key in ('stop_cash','financial_pause_threshold'):
                if key in args:changes[key]=integer(args[key],0,1000000000)
            settings.update(changes)
            return 'Skip and campaign preferences saved. Financial events below the minimum stay in the feed without pausing; balances and obligations are unchanged.'
        if action=='succession':
            if not self.s['settings']['succession']:raise RuleError('Enable optional succession in Campaign settings first.')
            name=str(args.get('name','')).strip();age=integer(args.get('age',30),18,80)
            if not 2<=len(name)<=80:raise RuleError('Use a successor name of 2–80 characters.')
            self.e.post('personal',command_id,'Optional succession legal and administration costs',{'asset:cash':-100000,'expense:succession':100000})
            previous=self.w.owner_name;today=date.fromisoformat(self.w.date);self.w.owner_name=name;self.w.birth_date=today.replace(year=today.year-age,day=1).isoformat()
            self.s.setdefault('owner_history',[]).append(dict(name=previous,date=self.w.date,successor=name))
            self.e.event('Optional succession completed',name+' now leads the same personal portfolio. Businesses, people, assets and liabilities retain their records.',True)
            return 'Succession completed for $1,000. Ownership and campaign continuity were preserved.'
        if action=='sandbox_funds':
            if self.s['settings']['mode']!='sandbox':raise RuleError('Capital editing is available only in a labeled sandbox campaign.')
            entity=self.require(args.get('entity','personal'));amount=integer(args.get('amount',0),10000,1000000000)
            if entity!='personal':raise RuleError('Add sandbox capital personally, then contribute it through ownership accounts.')
            self.e.post(entity,command_id,'Labeled sandbox capital injection',{'asset:cash':amount,'equity:sandbox':-amount});self.s['settings']['modified']=True
            return 'Sandbox capital added. Performance records remain explicitly marked as modified.'
        if action=='new_campaign':
            prepare_campaign(args)
            return 'A separate campaign will be created and opened. The current campaign stays saved and can be reopened from its save file.'
        raise RuleError('Unknown campaign option.')

    def tick(self,today):
        stop=False
        threshold=self.s['settings'].get('stop_cash',0)
        if threshold and self.w.cash('personal')<threshold:
            source='cash-threshold:'+self.w.date[:7]
            if not any(d['source']==source for d in self.s['decisions']):self.decision(source,'Personal cash threshold reached','Cash is below the alert threshold you configured. Review pending purchases and contributions.');stop=True
        if today.day==1:
            entities=list(entity_names(self.w));employees=[e for e in self.w.employments if e.status=='active' and e.employer in entities];people={e.person_id for e in employees}
            morale=sum(p.morale for p in self.w.people if p.id in people)//max(1,len(people))
            self.s['score_history'].append(dict(date=self.w.date,wealth=sum(own_equity(self.w,e) for e in entities),profit=group_profit(self.w,entities),real_profit=group_profit(self.w,entities)*10000//max(1,self.s['inflation']),employees=len(people),morale=morale,inflation=self.s['inflation'],modified=self.s['settings']['modified']))
            self.s['score_history']=self.s['score_history'][-360:]
        return stop


def prepare_campaign(args):
    seed=integer(args.get('seed',42),0,2147483647);mode=args.get('mode','entrepreneur');capital=integer(args.get('capital',35000000),10000000,1000000000)
    if mode not in ('guided','entrepreneur','sandbox'):raise RuleError('Choose Guided, Entrepreneur or Sandbox.')
    if mode!='sandbox' and capital!=35000000:raise RuleError('Custom starting capital belongs to Sandbox mode.')
    name=str(args.get('name','Alex Morgan')).strip()
    if not 2<=len(name)<=80:raise RuleError('Use an owner name of 2–80 characters.')
    try:starting=date.fromisoformat(args.get('starting_date','2026-01-01'))
    except ValueError:raise RuleError('Choose a valid starting date.')
    if mode!='sandbox' and starting.isoformat()!='2026-01-01':raise RuleError('Custom starting dates belong to Sandbox mode.')
    if not 2026<=starting.year<=2100:raise RuleError('Choose a fictional modern starting year from 2026–2100.')
    e=new_game(seed);delta=capital-e.world.cash('personal')
    if delta:e.post('personal','scenario-capital','Scenario starting capital',{'asset:cash':delta,'equity:capital':-delta})
    shift=(starting-date.fromisoformat(e.world.date)).days
    if shift:
        e.world.date=starting.isoformat();e.world.birth_date=starting.replace(year=starting.year-30,day=1).isoformat()
        for p in e.world.people:
            p.birth_date=(date.fromisoformat(p.birth_date)+timedelta(days=shift)).isoformat()
            p.licenses={k:(date.fromisoformat(v)+timedelta(days=shift)).isoformat() for k,v in p.licenses.items()}
        for emp in e.world.employments:emp.start_date=starting.isoformat()
        for event in e.world.events:event['date']=starting.isoformat()
        for posting in e.postings:posting['date']=starting.isoformat()
        for base in e.world.systems['period_bases'].values():base['year']=starting.year
    e.world.owner_name=name;e.world.systems['settings'].update(mode=mode,modified=mode=='sandbox')
    if mode=='guided':
        from .business_rules import BusinessRules
        b=e.world.businesses[0];rules=BusinessRules(e);q=rules.quote(b.id)
        e.action('acquire_business',{'business_id':b.id},'guided-acquisition')
        b.closing_on=e.world.date;rules.acquire(b)
        manager=next(emp for emp in e.world.employments if emp.employer==b.id and rules.position(emp.position_id).role=='manager');manager.status='ended';manager.end_date=e.world.date;rules.person(manager.person_id).candidate=True
        e.event('Guided objectives','Fill the manager vacancy, operate for twelve weeks, then review cash and employee morale. Your store begins with working capital and stock.')
    e.validate();return e


def forecast(world,days):
    days=integer(days,1,90);start_entities=list(entity_names(world));cash=sum(world.cash(e) for e in start_entities);profit=group_profit(world,start_entities)
    results=[]
    for label,factor in (('Lower demand',80),('Current demand',100),('Higher demand',120)):
        clone=copy.deepcopy(world)
        for b in clone.businesses:
            if b.id in start_entities:b.daily_demand=b.daily_demand*factor//100
        for _ in range(days):
            if clone.systems.get('campaign_outcome',{}).get('status')=='insolvent':break
            e=Engine(clone);e.advance_day();e.validate();clone=e.world
        entities=list(entity_names(clone))
        results.append(dict(scenario=label,cash=sum(clone.cash(e) for e in entities),cash_change=sum(clone.cash(e) for e in entities)-cash,profit=group_profit(clone,entities)-profit,date=clone.date))
    return dict(days=days,revision=world.revision,results=results,assumptions='Three demand scenarios, not a probability interval. Existing manager authority and commitments continue; no new owner decisions are assumed. The live campaign and its random streams were not changed.')
