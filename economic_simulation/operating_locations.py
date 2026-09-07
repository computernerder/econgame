"""Locations share a legal company's obligations while keeping operating books."""
from .campaign import Campaign
from .domain import RuleError


def legal_company(world,entity):
    return world.systems.get('operating_locations',{}).get(entity,{}).get('company',entity)


class OperatingLocations(Campaign):
    def action(self,args,source):
        from .business_rules import BusinessRules
        from .expansion import Expansion
        company=legal_company(self.w,self.require(args.get('entity','')))
        b=BusinessRules(self.e).company(company)
        if b.status!='operating':raise RuleError('Open another location from an operating company.')
        result=Expansion(self.e).action('start_business',dict(args,entity=company,industry=b.industry),source)
        unit=self.w.businesses[-1]
        self.s.setdefault('operating_locations',{})[unit.id]=dict(company=company,region=unit.region,opened=self.w.date,shared_obligations=0)
        self.e.event('Company location funded',unit.name+' is an operating location of '+b.name+'. Its payroll and other obligations are shared with that legal company, unlike a separate subsidiary.',True)
        return result+' This location uses separate operating books within the same legal company; it is not a liability-isolated subsidiary.'

    def settle(self):
        from .business_rules import BusinessRules
        for uid,record in self.s.get('operating_locations',{}).items():
            company=record['company'];accounts=self.w.accounts[uid]
            if not self.controlled(company):continue
            owed=sum(-value for key,value in accounts.items() if value<0 and (key in ('liability:payroll','liability:payable','liability:sales_tax','liability:income_tax') or key.startswith('liability:rent:')))
            needed=max(0,owed-self.w.cash(uid))
            support=min(needed,self.w.cash(company))
            if support:BusinessRules(self.e).action('fund_business',dict(entity=uid,amount=support),'location-funding:'+uid+':'+self.w.date)
            shortage=max(0,needed-support)
            key='liability:intercompany:'+uid;existing=min(record['shared_obligations'],max(0,-self.w.accounts[company].get(key,0)))
            change=shortage-existing
            if change:
                source='shared-location-obligation:'+uid+':'+self.w.date
                self.e.post(company,source,'Legal company obligation for its operating location',{'expense:internal_location_support:'+uid:change,key:-change})
                self.e.post(uid,source,'Shared legal company funding claim; not cash',{'asset:intercompany:'+company:change,'income:internal_location_support:'+company:-change})
            record['shared_obligations']=shortage
