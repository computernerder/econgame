"""Disclosed fictional covenants precede legal review and bind actual purchases."""
from datetime import date,timedelta
from .campaign import Campaign
from .domain import RuleError
from .simulation_support import stable_roll


class TransactionLegal(Campaign):
    def terms(self,p):
        from .property_operations import systems_for
        return self.s.get('transaction_terms',{}).get(p.id) or dict(property_id=p.id,
            disclosed=self.w.date,consent_required=p.id.startswith('covenant-'),
            original_fee=100000,roof_required=systems_for(self.w,p)['roof']['condition']<50,
            roof_target=50,roof_days=90,breach_charge=100000,approved_for={},reviews={})

    def initialize(self):
        if not self.s.get('covenant_listings_seeded'):
            import copy
            regions=set()
            for original in self.w.properties[:]:
                if original.category!='industrial' or original.status!='market' or original.owner is not None or original.region in regions:continue
                regions.add(original.region)
                from .world_names import property_name
                p=copy.deepcopy(original);p.id='covenant-'+original.id;p.name=property_name(self.w,p.id,p.category,p.kind)
                p.condition=min(35,p.condition);p.asking=p.value*90//100
                p.description='Discounted industrial property: buyer-specific transfer consent and a disclosed 90-day roof-work covenant. Review terms before committing.'
                self.w.properties.append(p)
            self.s['covenant_listings_seeded']=True
        for p in self.w.properties:
            if p.status=='market' and p.owner is None:
                self.s.setdefault('transaction_terms',{}).setdefault(p.id,self.terms(p))

    def prepare(self,task):
        p=self.e.get_property(task['target_id'])
        if p.owner is not None or p.status!='market':raise RuleError('Select a listed property for transaction work.')
        terms=self.s.get('transaction_terms',{}).get(p.id)
        if not terms:raise RuleError('This new listing has not published its contract disclosure yet. Advance a day before commissioning review.')
        task['terms_snapshot']={k:v for k,v in terms.items() if k not in ('approved_for','reviews')}
        task['original_offer']=p.asking
        if task['product']=='transfer_consent':
            if not terms['consent_required']:raise RuleError('This listing has no transfer-consent restriction.')
            if task['recipient'] not in terms['reviews']:raise RuleError('Complete this buyer’s transaction review before applying for consent.')
            if any(t.get('product')=='transfer_consent' and t['target_id']==p.id and t['recipient']==task['recipient'] and t['status']!='cancelled' and not (t.get('requires_specialist') and task['mode']=='outside') for t in self.s.get('service_tasks',[])):
                raise RuleError('This buyer already has a consent application. Counterparty decisions cannot be rerolled.')

    def finish(self,task,quality):
        p=self.e.get_property(task['target_id']);terms=self.s['transaction_terms'][p.id]
        if p.owner is not None or p.status!='market':
            task['outcome']='Listing no longer available. Completed work remains an expense; no consent was obtained.';return
        buyer=task['recipient']
        from .property_operations import PropertyOperations,systems_for
        roof=systems_for(self.w,p)['roof']['condition']
        if task['product']=='transaction_review':
            quote=PropertyOperations(self.e).quote(p,'roof','replacement')
            uncertainty=max(5,(100-quality)//2)
            findings=dict(date=self.w.date,consent_required=terms['consent_required'],original_fee=terms['original_fee'],
                roof_required=terms['consent_required'] and terms['roof_required'],roof_condition=roof,
                estimate_low=quote['total']*(100-uncertainty)//100,estimate_high=quote['total']*(100+uncertainty)//100,
                breach_charge=terms['breach_charge'],due_days=terms['roof_days'],source=task['id'])
            terms['reviews'][buyer]=findings;task['findings']=findings
            task['outcome']='Reviewed the existing disclosure: '+('buyer-specific transfer consent required; ' if terms['consent_required'] else 'no transfer-consent restriction; ')+('roof work covenant applies within 90 days of closing.' if findings['roof_required'] else 'no inherited roof-work covenant.')
            if findings['roof_required']:
                task['outcome']+=f' Roof condition {roof}/100. Estimated replacement ${findings["estimate_low"]/100:,.2f}–${findings["estimate_high"]/100:,.2f}; confirm the repair quote before booking.'
            return
        if p.category=='industrial' and p.value>50000000 and task['mode']!='outside':
            task['requires_specialist']=True
            task['outcome']='This industrial consent requires outside specialist counsel. Restriction remains unresolved; commission an outside consent application.';return
        if stable_roll(self.w,'consent:'+p.id+':'+buyer)>=min(95,quality):
            task['outcome']='Counterparty refused transfer consent for this buyer; the purchase remains blocked.';return
        fee=terms['original_fee']*(100-min(30,quality//3))//100
        terms['approved_for'][buyer]=dict(date=self.w.date,fee=fee,source=task['id'])
        task['improvement']=terms['original_fee']-fee
        task['outcome']=f'Buyer-specific transfer consent obtained. Original closing fee ${terms["original_fee"]/100:,.2f}, agreed ${fee/100:,.2f}. The concession is a future transaction cost reduction, not cash. Roof covenants remain binding.'

    def closing_fee(self,p,buyer=None):
        terms=self.terms(p)
        if not terms['consent_required']:return 0
        return terms['approved_for'].get(buyer,{}).get('fee',terms['original_fee'])

    def check_purchase(self,p,buyer):
        terms=self.terms(p)
        if terms['consent_required'] and buyer not in terms['approved_for']:
            raise RuleError('Disclosed transfer consent is required for this buyer. Complete legal transaction review and consent work before purchase.')

    def acquired(self,p,buyer):
        terms=self.terms(p)
        if terms['consent_required'] and terms['roof_required']:
            self.s.setdefault('property_covenants',[]).append(dict(id=self.uid('covenant'),property_id=p.id,owner=buyer,
                system='roof',target=terms['roof_target'],due=(date.fromisoformat(self.w.date)+timedelta(days=terms['roof_days'])).isoformat(),
                charge=terms['breach_charge'],status='open',created=self.w.date))

    def tick(self):
        from .property_operations import systems_for
        self.initialize()
        for covenant in self.s.get('property_covenants',[]):
            if covenant['status']!='open':continue
            p=self.e.get_property(covenant['property_id'])
            if systems_for(self.w,p)[covenant['system']]['condition']>=covenant['target']:
                covenant.update(status='satisfied',resolved=self.w.date)
                self.e.event('Property covenant satisfied',p.name+': actual roof condition now meets the disclosed covenant.');continue
            if covenant['due']<self.w.date:
                self.e.post(covenant['owner'],covenant['id']+':breach','Disclosed roof covenant charge',{'expense:contract_breach':covenant['charge'],'liability:payable':-covenant['charge']})
                covenant.update(status='breached',resolved=self.w.date)
                self.e.event('Property covenant breached',p.name+': the disclosed roof deadline was missed. The agreed charge is now payable; repair work is still needed.',True,financial_amount=covenant['charge'])
            elif not covenant.get('warned') and covenant['due']<=(date.fromisoformat(self.w.date)+timedelta(days=14)).isoformat():
                covenant['warned']=True
                self.e.event('Property covenant deadline approaching',p.name+': complete the disclosed roof obligation by '+covenant['due']+'.',True)
