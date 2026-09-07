"""Stable job quotes; accepted fees and required effort remain fixed."""
import random
from .domain import RuleError
from .industries import PROJECTS


def next_offer(world, business, kit_key=None):
    fee=business.contract_base_fee or business.contract_fee
    minutes=business.contract_base_minutes or business.contract_minutes
    if fee<=0 or minutes<=0:
        raise RuleError('This project business needs a positive contract fee and work budget.')
    number=max([business.project_number]+[j['number'] for j in business.parallel_projects]+[j['number'] for j in business.project_history])+1
    rng=random.Random(f'engineering:{world.seed}:{business.id}:{number}')
    size=rng.choice((75,100,125,150))
    effort=max(60,minutes*size//6000*60)
    rate_percent=rng.randint(90,115)
    from .revenue_kits import quote
    return quote(world,business,dict(number=number,minutes=effort,fee=max(100,fee*effort*rate_percent//(minutes*100)),rate_percent=rate_percent,size=size),kit_key)


def accept(rules,business,automatic=False,kit_key=None):
    if business.industry not in PROJECTS:
        raise RuleError('Choose a project business.')
    if business.status not in ('operating','independent'):
        raise RuleError('Open this business before accepting jobs.')
    quote=next_offer(rules.w,business,kit_key)
    from .project_portfolio import acceptance_reason
    reason=acceptance_reason(rules.w,business,quote)
    if reason:raise RuleError(reason)
    business.contract_base_fee=business.contract_base_fee or business.contract_fee
    business.contract_base_minutes=business.contract_base_minutes or business.contract_minutes
    if business.project_active:
        business.parallel_projects.append(dict(number=quote['number'],fee=quote['fee'],minutes=quote['minutes'],progress=0,earned=0))
    else:
        business.contract_fee=quote['fee'];business.contract_minutes=quote['minutes']
        business.project_number=quote['number']
        business.project_progress=business.project_earned=0
        business.project_active=True
    from .revenue_kits import remember
    remember(rules.w,business,quote)
    detail=f"{quote.get('label',business.industry.title())}: {business.name} {'automatically accepted' if automatic else 'accepted'} job {quote['number']}: ${quote['fee']/100:,.2f} for {quote['minutes']/60:g} qualified hours. Work earns the fee; payment follows invoicing by {30 if business.industry=='factory' else 14} days."
    rules.e.event(business.industry.replace('_',' ').title()+' contract accepted',detail)
    return detail
