"""Pause preferences affect time advancement, never accounting or event retention."""
DEFAULTS = dict(pause_routine=False,financial_pause_threshold=100000)
ROUTINE = {'Renovation complete','Tenant moved in','Sale completed','Business acquisition completed',
           'Training completed','Professional credential renewed','Recruitment applicants arrived',
           'New business opened','Business expansion complete','Company sale completed',
           'Integration phase completed','Space conversion completed','Civic project evaluated',
           'Property work completed','New employee started','Restaurant expansion completed',
           'Building ready for occupancy','Property sale closed','Financial recovery',
           'Operating assets liquidated','Optional succession completed'}
REQUIRED = {'Owner approval needed','Time-off approval needed','Delegated cash reserve breached',
            'Director workload exceeded','Business closed','Campaign insolvency','Payroll needs funding',
            'Personal cash threshold reached'}


def preferences(settings):
    """New defaults apply to missing preferences; explicit saved choices stay binding."""
    return {**DEFAULTS,**settings}


def resume_target(world):
    from datetime import date
    target=world.systems.get('time_skip',{}).get('target','')
    try:return target if date.fromisoformat(target)>date.fromisoformat(world.date) else ''
    except (TypeError,ValueError):return ''


def allowed(settings,reason):
    settings=preferences(settings)
    title=reason.get('title','')
    if title in REQUIRED:
        return True
    routine=title in ROUTINE or title.endswith(' project completed')
    if routine and not settings.get('pause_routine',True):return False
    amount=reason.get('financial_amount')
    threshold=settings.get('financial_pause_threshold',0)
    return amount is None or threshold==0 or abs(amount)>=threshold


def should_pause(engine,fallback=False):
    settings=engine.world.systems.get('settings',{})
    def unresolved(reason):
        if reason.get('handled_by'):return False
        for field,key in [('decision_id','decisions'),('management_id','management_requests')]:
            if reason.get(field):
                record=next((r for r in engine.world.systems.get(key,[]) if r['id']==reason[field]),None)
                if record and record['status']!='open':return False
                if record and record.get('source','').startswith('opening-staff:'):
                    from .expansion import opening_staff
                    b=next((b for b in engine.world.businesses if b.id==record['entity']),None)
                    if not b or b.status!='developing' or not opening_staff(engine.world,b)['missing']:return False
        return True
    # The aggregate legacy boolean can outlive an issue handled during the day.
    # Only an identifiable, unresolved reason may interrupt the player.
    reasons=engine.pause_reasons
    if not reasons and fallback:
        reasons=[r for r in engine.events if r.get('date')==engine.world.date and r.get('important') and not r.get('pause_suppressed')]
    accepted=[r for r in reasons if unresolved(r) and allowed(settings,r)]
    accepted.sort(key=lambda r:(r['title'] not in REQUIRED,r.get('id',0)))
    for event in engine.events:
        if event.get('important') and (event.get('date')==engine.world.date or event in reasons):
            event['pause_suppressed']=not (unresolved(event) and allowed(settings,event))
    engine.pause_details=[dict(title=r['title'],detail=r.get('detail',''),financial_amount=r.get('financial_amount')) for r in accepted[:5]]
    engine.pause_reason_text=accepted[0]['title'] if accepted else ''
    return bool(accepted)
