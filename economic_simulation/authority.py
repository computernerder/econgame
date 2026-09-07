"""Delegation contracts and conservative, cash-only commitment forecasts.

Forecasts are read models, not journal entries. Paid project budgets and loan
proceeds must never be counted again as spending capacity or future expense.
"""
from datetime import date, timedelta
from .campaign import Campaign, integer
from .domain import Engine, RuleError, daily_share, calendar_target, GAME_RULES

ACTION_GROUPS = {
    'restaurant_rota':'staffing', 'restaurant_expand':'growth',
    'recover_invoice':'contracts',
    'write_off_invoice':'contracts',
    'restock_stream':'purchasing',
    'time_off_decide':'staffing',
    'restock': 'purchasing', 'hire': 'hiring', 'hire_for_role': 'hiring',
    'recruit': 'hiring', 'annual_raise': 'compensation', 'train': 'training',
    'renew_license': 'training', 'rehabilitate': 'maintenance',
    'decide': 'maintenance', 'upgrade_business': 'growth', 'rent': 'leasing',
    'new_project': 'contracts',
    'fund_business':'growth','service_request':'purchasing','property_work':'maintenance',
    'advertise_space':'leasing','accept_tenant':'leasing','renew_property_lease':'leasing',
    'end_employment':'staffing','employment_terms':'staffing','business_policy':'pricing','start_business':'expansion','start_location':'expansion',
    'borrow':'financing','inspect_property':'maintenance','fund_flip':'property_acquisition','flip_work':'maintenance',
    'market_property':'asset_sales','accept_property_offer':'asset_sales',
    'respond_property_request':'maintenance',
    'accept_supplier_contract':'purchasing',
    'property_service':'purchasing','cancel_property_service':'purchasing',
}
GROUPS = tuple(sorted(set(ACTION_GROUPS.values())))


def labor_allowance(world,provider,roles,minutes,fallback=100):
    """Reserve known fully burdened employee rates, including a travel cushion."""
    from .workforce import Workforce
    workforce=Workforce(Engine(world));positions={p.id:p for p in world.positions}
    rate=fallback
    for emp in world.employments:
        if emp.employer!=provider or emp.status not in ('active','joining') or positions[emp.position_id].role not in roles:continue
        policy=workforce.effective(provider,emp)[0]
        overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
        wages=emp.salary+overtime+emp.compensation.get('shift_premium',0)
        monthly=wages+wages*GAME_RULES['tax']['payroll_percent']//100+workforce.benefit_cost(emp,policy)
        scheduled=max(1,emp.weekly_hours*60//len(emp.days))
        rate=max(rate,(monthly*125+28*scheduled*100-1)//(28*scheduled*100))
    return minutes*rate


def cash_forecast(world, entity, days=30):
    """Known obligations plus scheduled operating cost, without assumed sales.

    Receivables are displayed separately: a customer's promise is not liquidity.
    Existing deposits are protected even when their return date is unknown.
    """
    from .workforce import Workforce
    from .finance_rules import debt_accounts
    start = date.fromisoformat(world.date)
    end = start + timedelta(days=days)
    accounts = world.accounts[entity]
    rows = []
    def add(kind, amount, due, detail):
        if amount > 0:
            rows.append(dict(kind=kind, amount=amount, due=due, detail=detail))
    loan_keys = {key for loan in world.systems.get('loans', [])
                 if loan['entity'] == entity for key in debt_accounts(loan)}
    for key, value in sorted(accounts.items()):
        if value >= 0 or not key.startswith('liability:') or key in loan_keys:
            continue
        # Bank deposits and tenant deposits belong to customers, not the owner.
        kind = 'protected' if 'deposit' in key else 'accrued'
        add(kind, -value, world.date, key.removeprefix('liability:').replace('_', ' '))
    workforce = Workforce(Engine(world))
    staff = [e for e in world.employments if e.employer == entity and e.status in ('active', 'joining')]
    business = next((b for b in world.businesses if b.id == entity), None)
    payroll = operations = services = 0
    for offset in range(1, days + 1):
        day = start + timedelta(days=offset)
        for emp in staff:
            if emp.start_date > day.isoformat() or (emp.end_date and emp.end_date < day.isoformat()):
                continue
            policy = workforce.effective(entity, emp, on=day.isoformat())[0]
            overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
            wages = daily_share(emp.salary+overtime+emp.compensation.get('shift_premium',0), day)
            from .time_off import unpaid
            if unpaid(world,emp,day.isoformat()):wages=0
            payroll += wages + daily_share(workforce.benefit_cost(emp, policy), day)
            payroll += wages * GAME_RULES['tax']['payroll_percent'] // 100
        if business:
            operations += daily_share(business.monthly_overhead, day)
            from .restaurant import active as restaurant_active,settings as restaurant_settings,SCALES
            if restaurant_active(world,business):
                restaurant=restaurant_settings(world,business)
                operations+=daily_share(restaurant['marketing_monthly'],day)
                expansion=restaurant.get('expansion')
                if expansion and expansion['due']<=day.isoformat():
                    operations+=daily_share(SCALES[expansion['level']]['overhead']-SCALES[restaurant['level']]['overhead'],day)
            own_premises=any(p.owner==entity and p.occupant==entity and p.status=='occupied' for p in world.properties)
            active_lease=any(l['tenant']==entity and l['status']=='active' and l['end_date']>day.isoformat() for l in world.systems.get('leases',[]))
            if not own_premises and not active_lease:
                operations += daily_share(business.monthly_lease, day)
        for prop in world.properties:
            if prop.owner == entity:
                operations += daily_share(prop.upkeep, day)
        for lease in world.systems.get('leases', []):
            if lease.get('tenant') == entity and lease['status'] == 'active':
                if lease['end_date'] > day.isoformat():
                    operations += daily_share(lease['rent'], day)
        for assignment in world.systems.get('assignments',[]):
            if not assignment['active'] or assignment['target']!=entity:continue
            emp=next((e for e in world.employments if e.id==assignment['employment_id'] and e.status in ('active','joining')),None)
            if not emp or emp.start_date>day.isoformat() or day.weekday() not in emp.days:continue
            from .time_off import absent
            if absent(world,emp,day.isoformat()):continue
            agreement=next(g for g in world.systems['agreements'] if g['id']==assignment['agreement_id'])
            policy=workforce.effective(emp.employer,emp,on=day.isoformat())[0]
            overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
            cost=daily_share(emp.salary+overtime+emp.compensation.get('shift_premium',0),day)+daily_share(workforce.benefit_cost(emp,policy),day)
            allocated=cost*assignment['minutes']//(emp.weekly_hours*60//len(emp.days))
            services+=allocated*(100+agreement['markup'])//100
    add('forecast', payroll, end.isoformat(), 'Contracted wages, scheduled overtime, shift premiums, benefits and employer tax')
    for pid,progress in world.systems.get('flip_progress',{}).items():
        if progress['entity']==entity and progress['phase']!='sold':
            prop=next(p for p in world.properties if p.id==pid)
            holding=sum(daily_share(prop.upkeep,start+timedelta(days=n)) for n in range(1,days+1))
            operations-=min(holding,progress.get('holding_remaining',0),progress['reserve'])
    add('forecast', operations, end.isoformat(), 'Scheduled overhead, rent and property holding costs, less funded holding reserves')
    add('forecast', services, end.isoformat(), 'Assigned shared-service charges (internal; eliminated in consolidated profit)')
    for loan in world.systems.get('loans', []):
        if loan['entity'] != entity or loan['status'] != 'active':
            continue
        due = date.fromisoformat(loan['next_due'])
        overdue=loan.get('arrears',0)
        add('debt',overdue,world.date,'Overdue loan payment '+loan['id'])
        principal = max(0,loan['principal']-loan.get('overdue_principal',0)); remaining = loan['remaining']
        interest = max(0,loan['interest_due']-max(0,overdue-loan.get('overdue_principal',0)))
        previous = start
        while due <= end and principal:
            elapsed = max(0, (due - previous).days)
            interest += (principal * loan['rate_bps'] * elapsed + 3650000 - 1) // 3650000
            payment = (principal + remaining - 1) // max(1, remaining)
            add('debt', payment + interest, max(start, due).isoformat(), 'Scheduled loan payment ' + loan['id'])
            principal -= payment; remaining = max(1, remaining - 1); interest = 0
            previous = due; due = calendar_target(due, 'month')
    # Contract materials are required to finish accepted work, even before billing.
    from .revenue_kits import state as kit_state,commitment as kit_commitment,CATALOG,settings as kit_settings
    if business and kit_state(world,business):
        add('committed',kit_commitment(world,business),end.isoformat(),'Materials to finish accepted revenue-stream contracts')
        tools=sum(q['monthly'] for key,q in CATALOG[business.industry].items() if key in kit_settings(world,business))
        add('committed',(tools*days+29)//30,end.isoformat(),'Installed revenue-kit upkeep and tools')
    if business and business.project_active and business.material_hourly_cost and not kit_state(world,business):
        from .project_portfolio import remaining as project_remaining
        remaining = project_remaining(business)
        materials=(remaining * business.material_hourly_cost + 59) // 60
        if business.industry=='factory':materials=max(0,materials//2-world.systems.get('industry_state',{}).get(entity,{}).get('finished_cost',0))
        add('committed', materials,
            end.isoformat(), 'Materials to finish the accepted project (full remaining commitment)')
    for job in world.systems.get('property_work',[]):
        if job['owner']==entity and job['provider'] not in ('outside',entity) and job['status']=='working':
            if not job.get('flip_funded'):
                add('committed',labor_allowance(world,job['provider'],('maintenance','tradesperson','builder','engineer','electrician','plumber','hvac_technician'),job['remaining']),end.isoformat(),'Remaining internal contractor labor: '+job['id'])
    for task in world.systems.get('service_tasks',[]):
        if task['recipient']==entity and task['provider'] not in ('outside',entity) and task['mode']!='outside' and task['status'] in ('queued','working'):
            fallback=1 if task.get('product')=='property_representation' and 'labor_remaining' in task else 150
            add('committed',labor_allowance(world,task['provider'],(task['department'],),max(task['remaining'],task.get('labor_remaining',0)),fallback),end.isoformat(),'Conservative remaining internal service allowance: '+task['id'])
    for covenant in world.systems.get('property_covenants',[]):
        if covenant['owner']!=entity or covenant['status']!='open':continue
        from .property_operations import PropertyOperations,systems_for
        prop=next(p for p in world.properties if p.id==covenant['property_id'])
        if systems_for(world,prop)[covenant['system']]['condition']>=covenant['target']:continue
        # Small preventive jobs do not fund the full inherited repair obligation.
        # A booked replacement carries its own reserve; callbacks are reassessed at completion.
        if any(j['property_id']==prop.id and j['system']==covenant['system'] and j['kind']=='replacement' and j['status']=='working' for j in world.systems.get('property_work',[])):continue
        quote=PropertyOperations(Engine(world)).quote(prop,covenant['system'],'replacement')
        add('committed',quote['total'],covenant['due'],'Disclosed property work covenant: '+covenant['id'])
    for unit,record in world.systems.get('operating_locations',{}).items():
        if record['company']==entity:
            forecast=cash_forecast(world,unit,days)
            already_called=max(0,-accounts.get('liability:intercompany:'+unit,0))
            add('committed',max(0,-forecast['available']-already_called),end.isoformat(),'Shared legal obligations of location '+unit)
    total = sum(r['amount'] for r in rows)
    receivables = sum(v for k, v in accounts.items() if k.startswith(('asset:receivable', 'asset:rent_receivable')))
    return dict(cash=world.cash(entity), obligations=total, available=world.cash(entity)-total,
                days=days, through=end.isoformat(), rows=sorted(rows, key=lambda r:r['due']),
                receivables=receivables)


class Authority(Campaign):
    def contracts(self):
        return self.s.get('authority_contracts', {})

    def grants(self,b,record=None):
        """Default duties inherit every explicit parent restriction, without setup."""
        key=self.key(b,record)
        if key in self.contracts():return self.chain(key)
        from .manager_defaults import limits,staffed,contract,director_contract
        if record and key.startswith('director:'):return [(key,director_contract(self.w,record,b))]
        if record or not limits(b)['enabled'] or not staffed(self.w,b):return []
        grant=contract(self.w,b)
        from .director_scope import coverage
        parent=coverage(self.w).get(b.id,(None,None))[0]
        parent_key='director:'+parent['employment_id'] if parent else ''
        if parent_key in self.contracts():
            grant['parent']=parent_key
            return [(key,grant),*self.chain(parent_key)]
        return [(key,grant)]

    def key(self, business, record):
        return record.get('authority_key','director:'+record['employment_id']) if record else 'manager:' + business.id

    def chain(self, key):
        result = []; seen = set()
        while key:
            if key in seen:
                raise RuleError('Delegation cannot contain a cycle.')
            seen.add(key)
            contract = self.contracts().get(key)
            if not contract:
                raise RuleError('The parent authority contract no longer exists.')
            result.append((key, contract)); key = contract.get('parent')
        return result

    def spent(self, key):
        return sum(r['commitment'] for r in self.s.get('authority_audit', [])
                   if r['date'][:7] == self.w.date[:7] and key in r['charged_to'])

    def set_contract(self, args):
        from .leadership import Leadership
        key = str(args.get('target', ''))
        if key.startswith('manager:'):
            bid = self.require(key.removeprefix('manager:'))
            if not any(b.id == bid for b in self.w.businesses):
                raise RuleError('Choose an operating business manager.')
            scope = {bid}
        elif key.startswith('executive:'):
            record=self.s.get('executives',{}).get(key.removeprefix('executive:'))
            if not record or not record['active']:raise RuleError('Appoint this executive first.')
            scope=set(record['business_ids'])|{record['employer']}
        elif key.startswith('director:'):
            record = next((r for r in self.s.get('directors', []) if r['active'] and
                           r['employment_id'] == key.removeprefix('director:')), None)
            if not record:
                raise RuleError('Appoint this director before granting authority.')
            from .director_scope import assigned
            scope = set(assigned(self.w,record))
        else:
            raise RuleError('Choose a manager or appointed director.')
        for bid in scope: self.require(bid)
        def selections(name, default):
            value = args.get(name, default)
            if not isinstance(value,(str,list,tuple)):
                raise RuleError('Choose a list of businesses or regions.')
            return sorted({str(item).strip() for item in (value.split(',') if isinstance(value,str) else value)} - {''})
        old = self.contracts().get(key, {})
        contract = dict(parent=args.get('parent', old.get('parent')) or None,
                        businesses=selections('businesses', old.get('businesses',sorted(scope))),
                        regions=selections('regions', old.get('regions',sorted({b.region for b in self.w.businesses if b.id in scope}))),
                        objective=args.get('objective', old.get('objective', 'balanced')))
        if not set(contract['businesses']) <= scope:
            raise RuleError('Authority must stay inside the leader’s assigned businesses.')
        for field, default, maximum in [('transaction_limit',150000,1000000000),
                ('period_limit',3000000,1000000000), ('cash_reserve',0,1000000000),
                ('horizon',30,90), ('headcount_limit',10,100), ('salary_limit',500000,1000000000),
                ('project_limit',10000000,1000000000)]:
            contract[field] = integer(args.get(field, old.get(field, default)), 1 if field == 'horizon' else 0, maximum)
        if contract['objective'] not in ('balanced','growth','preserve_cash'):
            raise RuleError('Choose a supported leadership objective.')
        contract['actions'] = {}
        for group in GROUPS:
            mode = args.get(group, old.get('actions', {}).get(group, 'approval' if group in ('staffing','pricing','expansion','financing','property_acquisition','asset_sales') else 'allow'))
            if mode not in ('allow','approval','prohibit'):
                raise RuleError('Choose allow, approval or prohibit for each action.')
            contract['actions'][group] = mode
        if contract['parent']:
            rank = {'allow':0,'approval':1,'prohibit':2}
            for ancestor, parent in self.chain(contract['parent']):
                if ancestor == key: raise RuleError('Delegation cannot contain a cycle.')
                if not set(contract['businesses']) <= set(parent['businesses']) or not set(contract['regions']) <= set(parent['regions']):
                    raise RuleError('Subordinate organizational and geographic scope exceeds the parent.')
                if any(contract[f] > parent[f] for f in ('transaction_limit','period_limit','headcount_limit','salary_limit','project_limit')):
                    raise RuleError('Subordinate limits cannot exceed parent authority.')
                if contract['cash_reserve'] < parent['cash_reserve'] or contract['horizon'] < parent['horizon']:
                    raise RuleError('Subordinates must preserve the parent’s reserve and forecast horizon.')
                if any(rank[contract['actions'][g]] < rank[parent['actions'].get(g,'approval')] for g in GROUPS):
                    raise RuleError('Subordinate permissions cannot exceed parent authority.')
        contract['updated'] = self.w.date
        self.s.setdefault('authority_contracts', {})[key] = contract
        self.e.event('Authority contract updated', key + ': scope, cumulative commitments and cash obligations will be checked before each delegated action.')
        return 'Authority saved. Existing spending still counts this month; parent restrictions are checked live.'

    def check(self, b, record, action, args, commitment, preview=None):
        key = self.key(b, record)
        from .director_scope import coverage
        effective=coverage(self.w).get(b.id,(None,None))[0]
        if record and key.startswith('director:') and (not effective or effective['employment_id']!=record['employment_id']):
            return 'This director no longer oversees the business under the current ownership hierarchy.'
        routine=action in ('recover_invoice','property_service','write_off_invoice') or action=='service_request' and args.get('matter')=='collection'
        if routine:
            from .routine_management import policy
            settings=policy(self.w,b)
            if action=='recover_invoice' and args.get('method')=='agency' and commitment>settings['collection_limit']:
                return 'The full contingency fee exceeds the business collection limit.'
            if action=='write_off_invoice' and commitment>settings['write_off_limit']:
                return 'The remaining balance exceeds the business write-off limit.'
            used=sum(r['commitment'] for r in self.s.get('authority_audit',[]) if r['business_id']==b.id and r['date'][:7]==self.w.date[:7] and r['action'] in ('recover_invoice','property_service','write_off_invoice','service_request'))
            if commitment and used+commitment>policy(self.w,b)['period_limit']:return 'The complete commitment exceeds the routine monthly budget.'
        from .manager_defaults import action_limit
        grants=self.grants(b,record)
        implicit=key not in self.contracts() and bool(grants)
        if implicit:
            cap=record['limit'] if record else action_limit(b,action,args)
            if action not in ('hire','hire_for_role','annual_raise','employment_terms','new_project') and commitment>cap:
                return 'The complete commitment exceeds the manager’s routine purchase limit.'
            if action=='new_project' and commitment>cap:
                return 'Project materials exceed the manager’s routine purchase limit.'
        elif key not in self.contracts():
            if routine:
                overseer=effective if effective and 'director:'+effective['employment_id'] in self.contracts() else None
                if overseer:return 'Save a manager authority contract under the director’s restrictions before delegating this action.'
                if args.get('entity',b.id)!=b.id:return 'The invoice is outside the manager’s business.'
                if args.get('property_id'):
                    prop=self.e.get_property(args['property_id'])
                    if prop.owner!=b.id or prop.region!=b.region:return 'This property is outside the business manager’s ownership or county; grant explicit scope first.'
                cap=record['limit'] if record else b.authority.get('purchasing_limit',0)
                if commitment>cap:return 'The whole routine commitment exceeds the delegated purchase limit.'
                if commitment and cash_forecast(preview or self.w,b.id,30)['available']<b.authority.get('operating_policy',{}).get('cash_reserve',0):return 'Routine work would consume cash needed for known obligations and reserves.'
                return None

            if action in ('borrow','start_business','start_location','fund_flip','flip_work','market_property','accept_property_offer','accept_tenant','renew_property_lease','employment_terms','end_employment','business_policy','service_request','property_work','respond_property_request','advertise_space','accept_supplier_contract','property_service','cancel_property_service'):
                return 'Save an explicit authority contract before delegating this action.'
            overseer=effective if effective and 'director:'+effective['employment_id'] in self.contracts() else None
            if overseer:
                return 'The covering manager needs an explicit authority contract; a director’s absence does not remove their controls.'
            return None
        group = ACTION_GROUPS.get(action)
        if not group: return 'This strategic action requires the player.'
        if action in ('accept_tenant','renew_property_lease'):
            template=self.s.get('legal_templates',{}).get(b.id,{}).get('routine_lease',{})
            if template.get('expires','')<self.w.date:return 'Legal must approve a current routine lease template before delegated execution.'
        after = preview or self.w
        contracts=grants
        for _, contract in contracts:
            targets={args[k] for k in ('business_id','entity','recipient') if args.get(k)}
            if action=='cancel_property_service':
                job=next((j for j in self.s.get('property_service_jobs',[]) if j['id']==args.get('job_id')),None)
                if job:
                    targets.add(job['owner'])
                    if self.e.get_property(job['property_id']).region not in contract['regions']:return 'The service property is outside delegated geography.'
            if args.get('employment_id'):
                employee=next((e for e in after.employments if e.id==args['employment_id']),None)
                if employee:targets.add(employee.employer)
            if args.get('position_id'):
                position=next((p for p in after.positions if p.id==args['position_id']),None)
                if position:targets.add(position.business_id)
            if args.get('property_id'):
                prop=self.e.get_property(args['property_id'])
                if prop.owner:targets.add(prop.owner)
            if action=='service_request' and args.get('target_id'):
                prop=next((p for p in self.w.properties if p.id==args['target_id']),None)
                if prop and prop.region not in contract['regions']:return 'The service target is outside delegated geography.'
            if not targets<=set(contract['businesses']):return 'The affected operation is outside delegated organizational scope.'
            region=args.get('region',b.region)
            if args.get('property_id'):region=self.e.get_property(args['property_id']).region
            if b.id not in contract['businesses'] or region not in contract['regions']:
                return 'The business is outside the organizational or geographic scope.'
            mode = contract['actions'].get(group,'approval')
            if mode != 'allow': return 'Policy ' + ('prohibits this action.' if mode == 'prohibit' else 'requires player approval.')
            if commitment > contract['transaction_limit']:
                return 'The complete commitment exceeds the transaction limit.'
            # Count all children against the same parent period, even across locations.
        for ancestor, contract in contracts:
            if action=='new_project':
                project=next(item for item in after.businesses if item.id==b.id)
                from .project_portfolio import jobs
                newest=max(jobs(project),key=lambda j:j['number'])
                if newest['fee']>contract['project_limit']:
                    return 'The project contract value exceeds the approved project limit.'
            if self.spent(ancestor) + commitment > contract['period_limit']:
                return 'Cumulative monthly commitments exceed ' + ancestor + ' authority.'
            if action in ('hire','hire_for_role'):
                staff = [e for e in after.employments if e.employer in contract['businesses'] and e.status in ('active','joining')]
                if len(staff) > contract['headcount_limit']: return 'The scope-wide headcount limit includes incoming employees.'
                if args.get('amount',0) > contract['salary_limit']: return 'The compensation band does not permit this offer.'
            if action in ('annual_raise','employment_terms'):
                employee = next(e for e in after.employments if e.id == args['employment_id'])
                if employee.salary > contract['salary_limit']: return 'The raise exceeds the compensation band.'
            forecast = cash_forecast(after, b.id, contract['horizon'])
            # Agency fees are deducted only from recovered money. Keep their
            # full contingent commitment in authority limits without requiring
            # cash up front under the default grant. Explicit grants still apply.
            funded_recovery=action=='recover_invoice' and args.get('method')=='agency' and implicit and ancestor==key
            free_action=commitment==0 and ((implicit and ancestor==key) or action=='recover_invoice')
            if not (free_action or funded_recovery) and forecast['available'] < contract['cash_reserve']:
                return f"Known obligations leave ${forecast['available']/100:,.2f}; the reserve requires ${contract['cash_reserve']/100:,.2f}. Customer collections are not assumed."
            if contract['objective'] == 'preserve_cash' and group in ('growth','hiring','expansion','property_acquisition'):
                return 'Cash-preservation objective requires approval for growth or additional hiring.'
        return None

    def record(self, b, record, employee, action, commitment, cash_cost, detail, outcome="", charge_authority=True):
        key = self.key(b, record)
        charged = [ancestor for ancestor, _ in self.grants(b,record)] or [key]
        from .leadership_activity import actor_snapshot
        attribution=actor_snapshot(self.w,employee,record)
        if not employee:attribution.update(actor_name='Business automation',actor_role='Automatic policy')
        self.s.setdefault('authority_audit', []).append(dict(date=self.w.date, **attribution, outcome=outcome,
            business_id=b.id, action=action, commitment=commitment, cash_cost=cash_cost,
            charged_to=charged if charge_authority else [], detail=detail))

    def view(self, b, record=None):
        key = self.key(b, record)
        contract = self.contracts().get(key)
        grants=self.grants(b,record)
        defaults=grants[0][1] if not contract and grants else None
        forecast = cash_forecast(self.w, b.id, (contract or defaults or {}).get('horizon',30))
        return dict(key=key, contract=contract, defaults=defaults, forecast=forecast, spent=self.spent(key),
                    audit=[r for r in self.s.get('authority_audit', []) if r['business_id']==b.id][-10:])

    def guardrails(self):
        from .leadership import Leadership
        leaders=Leadership(self.e)
        from .director_scope import overloaded
        for emp,load in overloaded(self.w):
            self.e.event('Director workload exceeded',leaders.rules.person(emp.person_id).name+f": {load['count']} businesses including inherited subsidiaries need {load['minutes']} oversight minutes per working day. Assign another director to a branch or change inheritance; maximum {load['maximum']} businesses and scheduled hours still apply.",True)
        for b in self.w.businesses:
            if not self.controlled(b.id): continue
            record,_=leaders.director(b.id,False)
            keys={'manager:'+b.id,self.key(b,record)}
            contracts=[c for key in sorted(keys) if key in self.contracts() for _,c in self.chain(key)]
            for contract in contracts:
                forecast=cash_forecast(self.w,b.id,contract['horizon'])
                if forecast['available']<contract['cash_reserve']:
                    self.e.event('Delegated cash reserve breached',b.name+': known obligations exceed the cash available above your reserve. Review funding or reduce commitments.',True)
                    break
