"""Visible policies for daily manager work, shared by the relevant screens."""
from .routine_management import policy
from .campaign_views import form,field,hidden,money


def controls(world,b):
    from .manager_defaults import limits
    p=policy(world,b)
    result=form('routine_management_policy','Routine care and collections · '+b.name,
        'Hiring a manager enables routine work by default; change only the policies you want to override. The routine purchase ceiling is '+money(limits(b)['purchasing_limit'])+' and the contingency collection-fee ceiling is '+money(p['collection_limit'])+'. Agency fees come from recovered cash. Paid legal work uses the operating account; exhausted small balances can be written off within the limit below. Monthly commitments and any parent authority restrictions still apply.',
        [hidden('business_id',b.id)]+
        [field(key,label,p[key],'checkbox') for key,label in (
            ('collections','Automatically follow up overdue customer invoices'),
            ('agency','Allow contingency agency after reminders and installments fail'),
            ('legal_collections','Arrange paid legal collection when the balance justifies its cost'),
            ('write_off','Resolve exhausted small balances within the write-off limit'),
            ('property_care','Manage routine care of this business’s properties'),
            ('renew_services','Renew completed cleaning, grounds and security plans'),
            ('prefer_owned','Prefer a qualified owned provider with available capacity'))]+
        [field('collection_limit_dollars','Maximum contingency collection fee ($)',p['collection_limit']/100,'number',minimum=0),
         field('write_off_limit_dollars','Maximum exhausted balance to write off ($)',p['write_off_limit']/100,'number',minimum=0),
         field('period_limit_dollars','Monthly routine commitments ($)',p['period_limit']/100,'number',minimum=0),
         field('care_threshold','Book cleaning or grounds work below condition',p['care_threshold'],'number',minimum=20,maximum=85),
         field('visits','Visits in a new care plan',p['visits'],'number',minimum=1,maximum=20)],button='Review manager policies →')
    result['anchor']='routine-policy-'+b.id
    return result
