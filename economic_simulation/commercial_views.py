"""Contract disclosures, supplier quotes and actual commitments."""
from .campaign_views import choices,field,hidden,form,table,money
from .business_views import entity_names
from .commercial_work import PRODUCTS


def commercial_view(world,scope):
    names=entity_names(world);accounts=choices(names);properties={p.id:p for p in world.properties}
    listings=choices({p.id:p.name for p in world.properties if p.status=='market' and p.owner is None})
    providers=choices({'outside':'Outside specialists',**{b.id:b.name for b in world.businesses if b.id in names and b.status=='operating'}})
    view=dict(page='commercial_contracts',title='Contracts and purchasing',intro='Review disclosed obligations, obtain consent and compare outside-service agreements. Discounts require actual purchased capacity; unused credit can become a loss.',forms=[],tables=[],metrics=[],notes=[],links=[])
    for product,(department,title,effort) in PRODUCTS.items():
        inputs=[hidden('department',department),hidden('product',product),field('recipient','Paying account / intended buyer',scope,'select',accounts),field('provider','Service provider','outside','select',providers),field('mode','Delivery','outside','select',choices({'outside':'Outside','internal':'Internal','mixed':'Mixed'}))]
        if product=='supplier_tender':
            from .service_office import DEPARTMENTS
            inputs.append(field('service_department','Service to purchase','legal','select',choices({r:r.upper() if r in ('hr','it') else r.title() for r in DEPARTMENTS})))
        else:inputs.append(field('target_id','Property','','select',listings))
        guidance='Compare the cost of this purchasing work with expected usage and quoted savings.' if product=='supplier_tender' else 'Review precedes consent; a counterparty can refuse.'
        view['forms'].append(form('service_request',title,f'{effort//60} provider hours. Standard outside reservation {money(effort*150)}; eligible prepaid agreements supply whole tasks when enough credit remains. '+guidance,inputs))
    offers=[o for o in world.systems.get('supplier_offers',[]) if o['buyer'] in names]
    view['forms'].append(form('accept_supplier_contract','Purchase a quoted service agreement','Full block price is paid now. Unassigned credit expires after 60 days, with no cash refund. Assigned work shares the agreement’s daily capacity. Tasks use standard pricing when no block can fund the whole task.',[
        field('entity','Purchasing account',scope,'select',accounts),field('offer_id','Quote','','select',choices({o['id']:names[o['buyer']]+' / '+o['supplier']+' / '+o['department']+' / '+money(o['minutes']*o['rate']) for o in offers if o['status']=='open' and o['valid_until']>=world.date}))]))
    terms=world.systems.get('transaction_terms',{})
    view['tables'].append(table('Disclosed property terms',['Property','Transfer consent','Original closing fee','Roof covenant','Missed deadline charge'],[(properties[pid].name,'Required for each buyer',money(t['original_fee']),str(t['roof_days'])+' days to roof '+str(t['roof_target']) if t['roof_required'] else 'None',money(t['breach_charge']) if t['roof_required'] else 'None') for pid,t in terms.items() if t['consent_required'] and properties[pid].status=='market'],'Disclosures exist before review. Ordinary listings retain their existing purchase rules.'))
    tasks=world.systems.get('service_tasks',[])
    view['tables'].append(table('Legal reviews and consent',['Task / property','Buyer','Status','Actual expense','Future concession','Work product'],[(t['id']+' / '+properties[t['target_id']].name,names.get(t['recipient'],t['recipient']),t['status'],money(t['internal_cost']+t['outside_cost']),money(t['improvement']),t['outcome']) for t in tasks if t.get('product') in ('transaction_review','transfer_consent')]))
    view['tables'].append(table('Supplier responses',['Supplier / department','Account','Hourly rate / standard','Block price / hours','Daily shared hours','Status / valid through'],[(o['supplier']+' / '+o['department'],names[o['buyer']],money(o['rate']*60)+' / '+money(o['original_rate']*60),money(o['minutes']*o['rate'])+' / '+str(o['minutes']//60),o['daily_capacity']//60,o['status']+' / '+o['valid_until']) for o in offers]))
    view['tables'].append(table('Purchased service capacity',['Supplier / department','Account','Available minutes / credit','Assigned project reserve','Delivered expense','Expired unused cost','Expires / status'],[(c['supplier']+' / '+c['department'],names.get(c['buyer'],c['buyer']),str(c['available'])+' / '+money(c['credit']),money(sum(t.get('prepaid',0) for t in tasks if t.get('supplier_contract')==c['id'])),money(c['expense']),money(c['expired_cost']),c['expires']+' / '+c['status']) for c in world.systems.get('supplier_contracts',[])]))
    view['tables'].append(table('Inherited work obligations',['Property','Responsible account','Required system / condition','Due','Breach charge','Status'],[(properties[c['property_id']].name,names.get(c['owner'],c['owner']),c['system']+' / '+str(c['target']),c['due'],money(c['charge']),c['status']) for c in world.systems.get('property_covenants',[])]))
    view['links']=[dict(label='Service queue and cancellations',url='/?page=home_office&scope='+scope),dict(label='Book property work',url='/?page=property_workbench&scope='+scope)]
    return view
