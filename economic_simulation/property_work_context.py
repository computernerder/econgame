"""Read-only system condition context alongside the property work controls."""
from .property_scale_views import detail
from .property_operations import PropertyOperations
from .domain import Engine
from .money_display import money


def attach(form,world):
    fields={f['name']:f for f in form['fields']}
    properties={p.id:p for p in world.properties}
    operations=PropertyOperations(Engine(world))
    contexts={}
    for option in fields['property_id']['options']:
        p=properties[option['value']]
        systems=[] if p.category=='land' else detail(world,p.id)['systems']
        for row in systems:
            license=row['license']
            row['credential']='Licensed '+('HVAC' if license=='hvac' else license)+' contractor' if license!='General qualified work' else license
            jobs=[j for j in world.systems.get('property_work',[]) if j['property_id']==p.id and j['system']==row['key'] and j['status']=='working']
            row['work']='; '.join(j['kind'].replace('_',' ').title()+' underway · '+format(j['remaining']/60,'.1f')+' hours remaining' for j in jobs)
            row['option']=row['name']+' · '+str(row['condition'])+'/100'+(' · Work underway' if jobs else '')
        repairable=[row for row in systems if row['condition']<100 and not row['work']]
        quotes=[operations.quote(p,row['key'],'repair') for row in repairable]
        repair_summary=str(len(quotes))+' systems below 100 without work underway. '
        summaries={provider:repair_summary+money(sum(q['total'] if provider=='outside' else q['materials'] for q in quotes))+' paid now. '+
            ('Outside labor included.' if provider=='outside' else 'Internal labor costs are charged as delivered.') for provider in ('outside','internal')}
        contexts[p.id]=dict(name=p.name,date=world.date,systems=systems,
            repair_count=len(quotes) if p.status!='building' else 0,repair_summary=summaries,
            empty='Empty lot: no building systems. Use Build on an empty lot.' if p.category=='land' else '')
    selected=fields['property_id']['value']
    if selected not in contexts:selected=next(iter(contexts),'')
    fields['property_id']['value']=selected
    current=contexts.get(selected,dict(name='',date=world.date,systems=[],repair_count=0,repair_summary={},empty='Choose an owned building to see its current system conditions.'))
    labels={r['key']:r['option'] for r in current['systems']}
    for option in fields['system']['options']:
        option['label']=labels.get(option['value'],option['label'])
    form.update(work_properties=contexts,work_current=current,work_system=fields['system']['value'])
