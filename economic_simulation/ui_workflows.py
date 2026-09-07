"""Read-only context and destinations for task-focused screens."""
from .business_views import entity_names
from .navigation import url


def role_label(role):
    return {'hr':'HR','it':'IT','hvac':'HVAC','hvac_technician':'HVAC technician',
            'home_office_director':'Home Office Director','division_vp':'Division VP','corporate_services_vp':'VP of Corporate Services'}.get(role,role.replace('_',' ').title())


def prepare(campaign,world,scope,property_id='',action_focus='',work_system='',department_id='',shared_team='',service_product=''):
    """Only select identifiers already present in a form's allowed options."""
    names=entity_names(world)
    prop=next((p for p in world.properties if p.id==property_id and p.owner in names),None)
    forms=campaign['forms']
    if campaign['page']=='home_office':
        from .department_views import prepare as prepare_departments
        if not prepare_departments(campaign,world,scope,department_id):action_focus=''
    if shared_team:
        from .shared_team_views import prepare as prepare_shared
        if not prepare_shared(campaign,world,shared_team,action_focus,service_product):action_focus=''
    for index,form in enumerate(forms):
        form.setdefault('anchor','task-'+form['action']+'-'+str(index))
        for field in form['fields']:
            if form['action']=='start_business' and field['name']=='name':field.update(required=True,minlength=2,maxlength=80)
            if field['name'] in ('department','role','hiring_role') and not (form['action']=='service_request' and field['name']=='department'):
                for option in field['options']:option['label']=role_label(str(option['value']))
            if prop and field['name']=='property_id' and any(o['value']==prop.id for o in field['options']):
                field['value']=prop.id
            if prop and field['name']=='system' and any(o['value']==work_system for o in field['options']):
                field['value']=work_system
        if action_focus==form['action'] and not campaign.get('focused_task') and (not shared_team or form.get('shared_selected')):
            # Property actions must not silently fall back to a different asset.
            fields=[f for f in form['fields'] if f['name']=='property_id']
            if property_id and (not prop or not fields or not any(f['value']==prop.id for f in fields)):
                continue
            if prop:
                for field in fields:
                    field['options']=[option for option in field['options'] if option['value']==prop.id]
                    field['label']='Selected property'
            form['expanded']=True
            campaign['focused_task']=form
    for form in forms:
        if form['action']=='property_work':
            from .property_work_context import attach
            attach(form,world)
        from .form_context import attach as attach_context
        attach_context(form,world)
    if campaign['page']=='property_workbench' and property_id:
        if prop:
            campaign['property_context']=dict(name=prop.name,id=prop.id,owner=names[prop.owner],cash=world.cash(prop.owner),
                url=url('property',prop.owner,property_id=prop.id))
        if not prop or (action_focus and not campaign.get('focused_task')):
            campaign['notes'].insert(0,'This property is not available for the selected action. Return to the property to check its current status; no work has been booked.')
    if campaign['page']=='home_office':
        priority={'Service work queue and digest':0,'Departments and queue capacity':1}
        campaign['tables'].sort(key=lambda t:priority.get(t['title'],2))
        for form in forms:
            if form['action']=='department_configure':form['expanded']=action_focus=='department_configure' or (not action_focus and not campaign['department_rows'] and not department_id)
        campaign['task_links']=[dict(label=label,url=url('home_office',scope,action_focus=action)+'#task-focus')
            for action,label in [('service_request','Request service'),('department_configure','Add / configure department'),('outsource_service','Outsource work'),('service_priority','Change priority')]]
    if campaign.get('focused_task'):
        task=campaign['focused_task']
        campaign['forms']=[f for f in forms if f is not task]
    if campaign['page']=='home_office':
        campaign['forms']=[f for f in campaign['forms'] if f['action']!='department_configure']
