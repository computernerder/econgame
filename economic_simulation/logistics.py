"""Finite freight capacity shared by group clients and outside customers."""
import math
from .campaign import Campaign
from .industries import SALES,PROJECTS

EXTERNAL_RATE=30000
FUEL_PER_DELIVERY=5000
LOAD_SIZE={'retail':100,'restaurant':100,'grocery':100,'gas_station':1000,'boutique':50,'car_dealership':1}


def corporate_root(world,business):
    from .domain import Engine
    campaign=Campaign(Engine(world))
    if not campaign.controlled(business.id):return None
    by_id={b.id:b for b in world.businesses}
    root=business.id;parent=business.owner;seen={root}
    while parent not in (None,'personal') and parent not in seen:
        seen.add(parent);root=parent
        parent=by_id[parent].owner if parent in by_id else 'personal'
    return root


def providers(world,business):
    root=corporate_root(world,business)
    return [b for b in world.businesses if root and b.id!=business.id and b.industry=='logistics' and b.status=='operating' and corporate_root(world,b)==root]


def freight_capacity(b,buckets,management=100):
    minutes=sum(min(buckets.get('driver',[0]*24)[h]//30,buckets.get('dispatcher',[0]*24)[h]//10) for h in range(24))
    return min(b.fleet_vehicles*8,minutes*management*b.capacity_percent//10000)


def required_deliveries(b):
    if b.industry in SALES:return math.ceil(b.last_day.get('output',0)/LOAD_SIZE[b.industry])
    if b.industry in PROJECTS and b.industry!='engineering':return math.ceil(b.last_day.get('project_minutes',0)/600)
    return 0


def group_benefits(world,b):
    from .finance_rules import Finance
    from .domain import Engine
    banks=Finance(Engine(world)).owned_banks(b.id) if Campaign(Engine(world)).controlled(b.id) else []
    return dict(banks=[dict(id=x.id,name=x.name,parent_bank=x.id in ancestors(world,b)) for x in banks],
                transport=[dict(id=x.id,name=x.name) for x in providers(world,b)],
                transport_user=b.industry in SALES or b.industry in PROJECTS and b.industry!='engineering')


def ancestors(world,b):
    by_id={x.id:x for x in world.businesses};result=set();parent=b.owner
    while parent in by_id and parent not in result:
        result.add(parent);parent=by_id[parent].owner
    return result


def settle_transport(rules,today):
    w,e=rules.w,rules.e
    active=[b for b in w.businesses if b.last_day.get('date')==w.date and b.status in ('operating','independent')]
    if any(b.last_day.get('transport_settled') for b in active):return False
    stop=False
    fleet=[b for b in active if b.industry=='logistics']
    remaining={b.id:b.last_day.get('freight_capacity',0) for b in fleet}
    per_cost={}
    for b in fleet:
        fixed=sum(v for k,v in b.financial_days.get(w.date,{}).items() if k in ('expense:wages','expense:benefits','expense:payroll_tax','expense:operations','expense:premises_rent','expense:holding') or k.startswith(('expense:internal_rent:','expense:internal_services:','income:internal_services:')))
        fuel_cost=FUEL_PER_DELIVERY*(100-b.last_day.get('specialists',{}).get('logistics_percent',0))//100
        per_cost[b.id]=fuel_cost+math.ceil(max(0,fixed)/max(1,remaining[b.id]))
        b.last_day.update(internal_deliveries=0,external_deliveries=0,freight_unit_cost=per_cost[b.id])
    for client in sorted(active,key=lambda b:b.id):
        demand=required_deliveries(client)
        if not demand:continue
        unmet=demand;cost=0;internal=0;used=[]
        outside_rate=EXTERNAL_RATE*(100-client.last_day.get('specialists',{}).get('logistics_percent',0))//100
        for carrier in sorted(providers(w,client),key=lambda b:(per_cost.get(b.id,10**12),b.id)):
            if carrier.id not in remaining:continue
            distance=1 if carrier.region==client.region else 2
            unit_cost=per_cost[carrier.id]*distance
            if unit_cost>=outside_rate:continue
            quantity=min(unmet,remaining[carrier.id]//distance)
            if not quantity:continue
            charge=quantity*unit_cost;paid=min(charge,w.cash(client.id));owed=charge-paid
            source=f'group-freight:{client.id}:{carrier.id}:{w.date}'
            e.post(client.id,source,'Group transport at allocated cost',{'expense:internal_transport:'+carrier.id:charge,'asset:cash':-paid,'liability:intercompany:'+carrier.id:-owed})
            e.post(carrier.id,source,'Group transport cost reimbursement',{'income:internal_transport:'+client.id:-charge,'asset:cash':paid,'asset:intercompany:'+client.id:owed})
            remaining[carrier.id]-=quantity*distance
            carrier.last_day['internal_deliveries']+=quantity*distance
            carrier.last_day.setdefault('group_clients',[]).append(dict(id=client.id,name=client.name,deliveries=quantity,capacity_used=quantity*distance,charge=charge))
            cost+=charge;internal+=quantity;unmet-=quantity;used.append(carrier.name)
            if not unmet:break
        if unmet:
            charge=unmet*outside_rate;cost+=charge
            client.last_day.setdefault('specialists',{})['freight_savings']=unmet*(EXTERNAL_RATE-outside_rate)
            e.post(client.id,f'outside-freight:{client.id}:{w.date}','Outside carrier transport',{'expense:transport':charge,'liability:payable':-charge})
        client.last_day.update(transport_deliveries=demand,transport_internal=internal,transport_cost=cost,transport_savings=demand*EXTERNAL_RATE-cost,transport_providers=used)
    from .economy import Economy
    for carrier in fleet:
        external=min(remaining[carrier.id],max(0,carrier.daily_demand*Economy(e).demand_factor(carrier)*(100+carrier.last_day.get('specialists',{}).get('marketing_percent',0))//10000))
        if external:
            charge=external*EXTERNAL_RATE
            e.post(carrier.id,f'freight-sales:{carrier.id}:{w.date}','Outside customer freight delivered',{'asset:cash':charge,'income:freight_sales':-charge})
        used=carrier.last_day['internal_deliveries']+external
        if used:
            fuel_cost=FUEL_PER_DELIVERY*(100-carrier.last_day.get('specialists',{}).get('logistics_percent',0))//100
            carrier.last_day.setdefault('specialists',{})['fuel_savings']=used*(FUEL_PER_DELIVERY-fuel_cost)
            e.post(carrier.id,f'freight-fuel:{carrier.id}:{w.date}','Fuel and vehicle running costs',{'expense:freight_running':used*fuel_cost,'liability:payable':-used*fuel_cost})
        carrier.last_day.update(external_deliveries=external,output=used,freight_unused=max(0,remaining[carrier.id]-external))
        if today.weekday()==4 or carrier.payroll_overdue:
            owed=-w.accounts[carrier.id].get('liability:payroll',0)
            paid=min(owed,w.cash(carrier.id))
            if paid:e.post(carrier.id,f'payday:{carrier.id}:{w.date}','Payday: earned wages and benefits',{'asset:cash':-paid,'liability:payroll':paid})
            carrier.payroll_overdue=paid<owed
            if carrier.payroll_overdue:
                e.event('Payroll needs funding',carrier.name+' could not pay its full payroll. Add capital; unpaid wages reduce morale.',True,financial_amount=owed-paid)
                if Campaign(e).controlled(carrier.id):stop=True
    # Transport settles after all operations, so each worker's paid time is used once.
    for b in active:
        b.last_day['transport_settled']=True
        accounts=b.financial_days.get(w.date,{})
        streams={k[7:]:-v for k,v in accounts.items() if k.startswith('income:')}
        expense=sum(v for k,v in accounts.items() if k.startswith('expense:'))
        b.last_day.update(streams=streams,revenue=sum(streams.values()),expenses=expense,profit=sum(streams.values())-expense)
        if b.history and b.history[-1]['date']==w.date:b.history[-1].update(b.last_day)

    return stop
