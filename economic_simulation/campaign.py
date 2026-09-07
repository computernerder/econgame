"""Shared campaign records, deterministic subsystem randomness and decision inbox."""
from __future__ import annotations
import copy
import random
from datetime import date, timedelta
from .domain import GAME_RULES, Engine, RuleError, tuples


def integer(value, low=0, high=1_000_000_000):
    if isinstance(value,bool) or not isinstance(value,(int,str)):
        raise RuleError('Enter a whole number.')
    try:value=int(value)
    except ValueError:raise RuleError('Enter a whole number.')
    if not low<=value<=high:raise RuleError(f'Enter a value between {low:,} and {high:,}.')
    return value


def flag(value):return value in (True,'true','on','1')


class Campaign:
    def __init__(self, engine: Engine):
        self.e=engine;self.w=engine.world;self.s=self.w.systems

    def initialize(self):
        if self.s:return
        self.s.update(version=1,next_id=1,streams={},policies=[],assignments=[],agreements=[],offices=[],decisions=[],loans=[],leases=[],civic=[],brands=[],franchises=[],plans=[],tax_returns=[],annual=[],research=[],regions=copy.deepcopy(GAME_RULES['regions']),owner_skills={'maintenance':30,'leadership':45},owner_work=None,settings={'difficulty':'forgiving','succession':False,'mode':'entrepreneur','modified':False,'stop_cash':0,'digest_only':False},inflation=10000,interest_bps=600,cycle=100,competitors=[],tax_carry={},period_bases={},score_history=[],ownership_history=[],claims=[])
        self.s['period_bases']={entity:{'year':date.fromisoformat(self.w.date).year,'profit':-sum(v for k,v in accounts.items() if k.startswith(('income:','expense:')) and k not in ('income:dividends','expense:income_tax')),'tax':0,'paid':0} for entity,accounts in self.w.accounts.items()}
        for region in self.s['regions']:
            region.update(history=[],graduates=0,unemployed=region['population']*(100-region['employment'])//100,underemployed=region['population']//20)
        from .expansion import Expansion
        Expansion(self.e).seed_group()
        for i,b in enumerate(self.w.businesses):
            b.reputation=55+i*3
        for p in self.w.people:
            for skill in ('finance','technology','legal'):p.skills.setdefault(skill,30)
            p.home_region=self.s['regions'][int(p.id.rsplit('-',1)[-1])%len(self.s['regions'])]['id']
            p.labor_state='unemployed' if p.candidate else 'employed'

    def uid(self,kind):
        value=f'{kind}-{self.s["next_id"]}';self.s['next_id']+=1;return value

    def roll(self,stream,low,high):
        seeds={'workforce':1701,'economy':2701,'crime':3701,'projects':4701,'competitors':5701}
        rng=random.Random(self.w.seed+seeds[stream])
        if stream in self.s['streams']:rng.setstate(tuples(self.s['streams'][stream]))
        value=rng.randint(low,high);self.s['streams'][stream]=rng.getstate();return value

    def parent(self,entity):
        if entity=='personal':return None
        if entity=='company':
            from .holding_company import exists
            return 'personal' if exists(self.w) else None
        b=next((b for b in self.w.businesses if b.id==entity),None)
        return b.owner if b else None

    def controlled(self,entity):
        seen=set()
        while entity and entity not in seen:
            if entity=='personal':return True
            seen.add(entity);entity=self.parent(entity)
        return False

    def require(self,entity):
        if entity not in self.w.accounts or not self.controlled(entity):raise RuleError('Choose an account under your ownership.')
        return entity

    def decision(self,source,title,detail,entity='personal',options=None,days=14,cost=0,financial_amount=None):
        existing=next((d for d in self.s['decisions'] if d['source']==source),None)
        if existing:
            if existing['status']=='open':self.e.pause_reasons.append(dict(title=title,detail=detail,financial_amount=financial_amount,decision_id=existing['id']))
            return existing
        d=dict(id=self.uid('decision'),source=source,title=title,detail=detail,entity=entity,options=options or {'acknowledge':'Review and continue'},due=(date.fromisoformat(self.w.date)+timedelta(days=days)).isoformat(),cost=cost,status='open',created=self.w.date,default='Remains open; no unapproved spending or structural change.')
        self.s['decisions'].append(d);self.e.event(title,detail,True,financial_amount=financial_amount)
        self.e.events[-1]['decision_id']=d['id']
        return d

    def choose(self,args):
        d=next((d for d in self.s['decisions'] if d['id']==args.get('decision_id') and d['status']=='open'),None)
        if not d or args.get('choice') not in d['options']:raise RuleError('Choose an available response to an open decision.')
        choice=args['choice'];self.require(d['entity'])
        if choice in ('mediate','retain','repair','audit'):
            if d['cost']:self.e.post(d['entity'],'decision:'+d['id'],'Decision: '+d['title'],{'asset:cash':-d['cost'],'expense:intervention':d['cost']})
            for pid in d.get('people',[]):
                p=next(p for p in self.w.people if p.id==pid)
                p.trust=min(100,p.trust+8);p.morale=min(100,p.morale+5)
                if choice=='retain':p.notice_on=None;p.loyalty=min(100,p.loyalty+12)
            if 'property_id' in d:
                p=next(p for p in self.w.properties if p.id==d['property_id']);p.condition=min(100,p.condition+5)
        d.update(status='resolved',choice=choice,resolved=self.w.date)
        self.e.event('Decision recorded',d['title']+': '+d['options'][choice])
        return 'Decision recorded; effects and any spending appear in the history.'

    def validate(self):
        if not self.s:return
        if self.s.get('version') not in (1,2,3,4,5):raise RuleError('Unsupported campaign systems version.')
        for key in ('policies','assignments','agreements','offices','decisions','loans','leases','civic','brands','franchises','plans'):
            records=self.s[key]
            if len({r['id'] for r in records})!=len(records):raise RuleError('Duplicate '+key+' identity.')
        for region in self.s['regions']:
            for key in ('income','education','infrastructure','crime','employment'):
                if not 0<=region[key]<=100:raise RuleError('A regional index exceeded its bounds.')
