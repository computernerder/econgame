"""Display names only. Stored identifiers and command arguments stay unchanged."""
import re


def name_catalog(world):
    names = {b.id:b.name for b in world.businesses}
    names.update({p.id:p.name for p in world.properties})
    names.update({p.id:p.name for p in world.people})
    names.update({e.id:names.get(e.person_id,'Employee') for e in world.employments})
    names.update(personal='Personal portfolio')
    from .holding_company import name
    names['company'] = name(world)
    for number,task in enumerate(world.systems.get('service_tasks',[]),1):
        work=task.get('product') or task.get('department','service')
        label=work.upper() if work in ('hr','it') else work.replace('_',' ').title()
        target=names.get(task.get('target_id'))
        names[task['id']]=label+' for '+names.get(task['recipient'],task['recipient'])+(' · '+target if target else '')+' · '+task.get('created','')+' · request '+str(number)
    return names


def text_label(world, value):
    text = str(value)
    names = world if isinstance(world,dict) else name_catalog(world)
    if text.lower() in names:
        return names[text.lower()]
    def care(match):
        return 'property care invoice for ' + names.get(match[1].lower(), 'the business') + ' dated ' + match[2]
    text = re.sub(r'care-invoice:(business-\d+):(\d{4}-\d{2}-\d{2})', care, text, flags=re.I)
    # Longest first and exact token boundaries avoid business-2 matching business-23.
    tokens = [k for k in sorted(names,key=len,reverse=True) if k not in ('personal','company')]
    if tokens:
        pattern = r'(?<![\w-])(' + '|'.join(re.escape(k) for k in tokens) + r')(?![\w-])'
        text = re.sub(pattern, lambda m:names[m[0].lower()], text, flags=re.I)
    text = re.sub(r'\bwarranty-(\d+)\b', r'Warranty claim #\1', text, flags=re.I)
    return text


def account_label(world, value):
    # Format account segments separately so proper names retain their spelling.
    return ' / '.join(text_label(world, part) if re.search(r'\w+-\d+',part)
                      else part.replace('_',' ').title() for part in value.split(':'))
