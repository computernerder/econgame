"""Internal ownership transfers at carrying value, without a sale or cash movement."""
from .campaign import Campaign
from .business_rules import BusinessRules
from .business_models import investment_account
from .business_views import descendants,entity_names
from .domain import RuleError


class Ownership(Campaign):
    def transfer(self,args,command_id):
        business=BusinessRules(self.e).company(args.get('business_id',''))
        if business.id in self.s.get('operating_locations',{}):raise RuleError('A location belongs to its legal company. Transfer the company, or close the location and form a separate business; existing company obligations cannot be detached by rearranging a chart.')
        target=self.require(args.get('new_owner',''))
        old=business.owner
        if target==old:raise RuleError('This business already belongs to that owner.')
        branch=set(descendants(self.w,business.id))
        if target in branch:raise RuleError('A business cannot own itself or one of its ancestors. Choose an owner outside this branch.')
        if business.status not in ('operating','developing'):raise RuleError('Finish this acquisition before rearranging ownership.')
        if target not in ('personal','company'):
            owner=BusinessRules(self.e).company(target)
            if owner.status not in ('operating','developing'):raise RuleError('Choose an operating or developing company as the new owner.')
        # Sale plans freeze a whole ownership tree and its price until closing.
        for plan in self.s['plans']:
            if plan['kind']=='business_sale' and plan['status']=='active':
                selling=set(descendants(self.w,plan['entity']))
                if branch & selling or target in selling or old in selling:
                    raise RuleError('A sale is pending for an affected ownership branch. Finish the sale before rearranging it.')
        names=entity_names(self.w)
        investment=self.w.accounts[old].get(investment_account(business.id),0)
        goodwill=self.w.accounts[old].get('asset:goodwill:'+business.id,0)
        total=investment+goodwill
        if investment or goodwill:
            self.e.post(old,command_id+':from','Internal ownership transfer: '+business.name,
                        {investment_account(business.id):-investment,'asset:goodwill:'+business.id:-goodwill,'equity:reorganization':total})
            self.e.post(target,command_id+':to','Internal ownership received: '+business.name,
                        {investment_account(business.id):investment,'asset:goodwill:'+business.id:goodwill,'equity:reorganization':-total})
        from .leadership_history import duties,record_change
        leaders=[e for e in self.w.employments if any(r['active'] and r['employment_id']==e.id for r in self.s.get('directors',[]))]
        before={e.id:duties(self.w,e) for e in leaders}
        business.owner=target
        for employee in leaders:record_change(BusinessRules(self.e),employee,before[employee.id],'Subsidiary ownership changed: '+business.name+'.')
        business.market_parent=None
        self.s['ownership_history'].append(dict(date=self.w.date,kind='reorganization',business_id=business.id,old_owner=old,new_owner=target,carrying_value=total,entities=sorted(branch)))
        detail=f'{business.name} moved from {names[old]} to {names[target]}, with {len(branch)-1} subsidiaries. No cash changed hands. Employees, property ownership, loans, guarantees and leases remain with their existing companies. Inherited group policies now follow the new ownership path.'
        self.e.event('Business ownership rearranged',detail)
        return detail
