from .domain import Engine
"""Forms and reports for the expansion systems; commands remain in the engine."""
from .campaign_views import field, hidden, choices, form, table, money
from .domain import GAME_RULES, Engine
from .business_views import business_context, entity_names
from .expansion import Expansion


def populate(view, world, page, scope, campaign, owned, names):
    s = world.systems
    forms, tables = view['forms'], view['tables']
    business_options = choices({b.id: b.name for b in owned})
    regions = choices({r['id']: r['id'] for r in s['regions']})
    props = [p for p in world.properties if p.owner == scope and p.status not in ('sold', 'expired')]
    account = [hidden('entity', scope)]

    def select(name, label, options, value=''):
        return field(name, label, value, 'select', options)

    def dollars(name, label, value, minimum=0):
        return field(name + '_dollars', label + ' ($)', value / 100, 'number', minimum=minimum / 100)

    def number(name, label, value, lo, hi):
        return field(name, label, value, 'number', minimum=lo, maximum=hi)

    if page == 'expansion':
        view.update(title='Open and develop businesses', intro='Fund a new operation, hire its team, and follow its opening plan. Reserves pay costs while work is underway.')
        from .holding_company import exists
        if not exists(world):
            forms.append(form('create_holding_company', 'Create a holding company', 'Optional: a separate company for owning property and subsidiaries. Starts empty, with no staff or automatic transfer of funds.', [field('name','Company name')]))
        rules = Expansion(Engine(world))
        tables.append(table('Opening budgets', ['Industry', 'Deposit', 'Equipment', 'Stock', 'Sunk costs', 'Reserve', 'Total', 'Days'], [
            (k.replace('_', ' ').title(), *(money(q[x]) for x in ('deposit', 'fitout', 'inventory', 'expense', 'reserve', 'total')), q['days'])
            for k in GAME_RULES['startup'] for q in [rules.opening_quote(k)]]))
        forms.append(form('start_business', 'Start a business', 'Budget includes the default cash reserve shown above. Staffing and permits may delay opening.', account + [
            field('name', 'Business name'), select('industry', 'Industry', choices({k: k.replace('_', ' ').title() for k in GAME_RULES['startup']})), select('region', 'County', regions)]))
        for b in owned:
            base = [hidden('business_id', b.id)]
            if b.status == 'developing':
                forms.append(form('cancel_opening', 'Cancel opening · ' + b.name, 'Sell setup assets at a discount and settle obligations before returning remaining funds.', base))
            else:
                forms.append(form('upgrade_business', 'Expand equipment · ' + b.name, 'Adds 20 percentage points of capacity after 21 days. The review shows the actual cost.', base))
                forms.append(form('integration', 'Integration · ' + b.name, 'Choose a 30-day program. Shared services still need agreements and assigned people.', base + [select('mode', 'Program', choices({k: k.replace('_', ' ').title() for k in ('autonomy', 'shared_services', 'rebrand', 'leadership_review')}))]))
                forms.append(form('sell_business', 'Sell company · ' + b.name, 'Transfers the whole subsidiary group after 14 days. Review the offer before agreeing.', base))
        market = [b for b in world.businesses if b.status == 'market' and not b.market_parent]
        if market:
            forms.append(form('due_diligence', 'Investigate an acquisition', 'Spend $500 on a dated report before committing to an acquisition.', account + [select('business_id', 'Target', choices({b.id: b.name for b in market}))]))
        tables.append(table('Development plans', ['Company', 'Plan', 'Phase', 'Due', 'Status'], [(names.get(p.get('entity'), p.get('entity')), p['kind'], p.get('phase', p.get('report', '')), p.get('due', ''), p['status']) for p in reversed(s['plans'])][:100]))

    elif page == 'financing':
        view.update(title='Loans and taxes', intro='Borrowing adds cash and a repayment obligation. All rates and tax rules belong to this fictional game economy.')
        from .finance_rules import Finance
        banks=Finance(Engine(world)).owned_banks(scope)
        if banks:view['notes'].append('Owner-bank loans: 2 percentage points lower APR (minimum 1%), unsecured borrowing up to 75% of equity instead of 50%, and property-backed borrowing up to 80% of value instead of 70%. Existing debt and the bank’s lending cash reserve still limit approval. Existing loans keep their agreed rates.')
        forms.append(form('borrow', 'Arrange financing', 'Payments include principal and accrued interest. Pledged property cannot be sold until its loan is repaid.', account + [select('lender', 'Lender', choices({**{b.id:b.name+' · owner benefits' for b in banks},'':'External lender · standard terms'})),
            dollars('amount', 'Loan amount', 1000000, 10000), number('months', 'Term in months', 60, 6, 360),
            select('property_id', 'Collateral', choices({'': 'Unsecured', **{p.id: p.name for p in props}})),
            select('guarantor', 'Owner guarantee', choices({'': 'No guarantee', **({campaign.parent(scope): names.get(campaign.parent(scope), '')} if campaign.parent(scope) else {})}))]))
        loans = [l for l in s['loans'] if l['entity'] == scope]
        tables.append(table('Loans', ['Loan', 'Lender', 'Principal', 'Interest due', 'APR', 'Next payment', 'Status'], [(l['id'], names.get(l.get('lender'),next((b.name for b in world.businesses if b.id==l.get('lender')),'External lender')), money(l['principal']), money(l['interest_due']), f"{l['rate_bps']/100:.2f}%", l['next_due'], l['status']) for l in loans]))
        for loan in loans:
            if loan['status'] != 'active':
                continue
            base = account + [hidden('loan_id', loan['id'])]
            forms.append(form('repay_loan', 'Repay · ' + loan['id'], 'Accrued interest is paid first, then principal.', base + [dollars('amount', 'Payment', loan['principal'] + loan['interest_due'], 1)]))
            if not loan.get('restructured'):
                forms.append(form('restructure_loan', 'Restructure · ' + loan['id'], 'One-time extension of 12 installments. APR increases by one point and a fee is charged.', base))
        forms.append(form('file_taxes', 'File and pay income tax', 'Pays the accrued liability plus a $100 filing cost.', account))
        if scope not in ('personal', 'company'):
            forms.append(form('tax_plan', 'Fund qualified research', 'Requires accounting or legal staff. After 90 days, eligible spending creates a limited fictional tax credit.', account + [dollars('amount', 'Research budget', 500000, 100000)]))
        tables.append(table('Tax obligations', ['Account', 'Amount owed'], [(k.replace('liability:', '').replace('_', ' '), money(-v)) for k, v in world.accounts[scope].items() if k.startswith('liability:') and 'tax' in k]))
        tables.append(table('Filed returns', ['Date', 'Tax paid', 'Filing cost'], [(r['date'], money(r['paid']), money(r['filing_cost'])) for r in s['tax_returns'] if r['entity'] == scope]))

    elif page == 'regions':
        view.update(title='Vermont counties and community', intro='Vermont’s 14 counties use simulated economic indicators, not current real-world statistics. Published county indicators lag the simulation. Community projects take time and their benefits reach other employers too.')
        for region in s['regions']:
            history = region.get('history', [])
            if history:
                observation = history[-1]
                tables.append(table(region['id'], ['Indicator', 'Published index'], [(k.title(), v) for k, v in observation['values'].items()], observation['date'] + ' · ' + observation['confidence']))
            else:
                view['notes'].append(region['id'] + ': the first regional report arrives at the next month boundary.')
        tables.append(table('Community project budgets', ['Project', 'Gross cost', 'Days to evaluation'], [(k.title(), money(v['cost']), v['days']) for k, v in GAME_RULES['civic'].items()]))
        forms.append(form('civic_project', 'Fund a community project', 'Co-funding is limited by the regional annual budget. Review shows your actual contribution.', account + [select('region', 'County', regions), select('kind', 'Project', choices({k: k.title() for k in GAME_RULES['civic']})), field('cofund', 'Request available public co-funding', True, 'checkbox')]))
        if owned:
            forms.append(form('insurance', 'Business insurance', 'Premiums accrue daily. Covered claims settle after 30 days; basic coverage excludes fraud.', account + [select('business_id', 'Business', business_options), select('tier', 'Coverage', choices({'none': 'None', 'basic': 'Basic · $50/month', 'comprehensive': 'Comprehensive · $120/month'}))]))
        tables.append(table('Community investments', ['County', 'Project', 'Your cost', 'Due', 'Status', 'Outcome'], [(p['region'], p['kind'], money(p['cost']), p['due'], p['status'], str(p.get('outcome') or 'Awaiting evaluation')) for p in s['civic']]))

    elif page == 'spaces':
        view.update(title='Spaces and leases', intro='Use the ownership selector to manage its buildings. Refundable deposits remain liabilities; rent and arrears have separate records.')
        if not props:
            view['notes'].append('Buy a property under this ownership account to configure and lease spaces.')
        for prop in props:
            base = [hidden('property_id', prop.id)]
            if prop.status == 'vacant':
                forms.append(form('configure_spaces', 'Configure spaces · ' + prop.name, 'Divide the existing usable floor area into separately leasable units.', base + [number('units', 'Number of units', 1, 1, 20)]))
                if scope == 'personal':
                    forms.append(form('self_renovate', 'Personal renovation · ' + prop.name, 'Spend four owner hours per day on one renovation at a time. Review shows the materials cost and completion date.', base))
            if prop.status == 'occupied' and prop.occupancy_use != 'personal_residence':
                forms.append(form('release_premises', 'Release premises · ' + prop.name, 'The operation resumes an external premises lease. Active headquarters must be relocated first.', base))
            for space in prop.spaces:
                if space.get('office_id') or any(l['space_id'] == space['id'] and l['status'] == 'active' for l in s['leases']):
                    continue
                unit = base + [hidden('space_id', space['id'])]
                forms.append(form('lease_space', 'Lease · ' + prop.name + ' / ' + space['name'], f"{space['area']} m² · {space['use']}. Logistics, storage, factories, trades and construction require industrial space; other businesses require commercial space.", unit + [select('tenant', 'Tenant account', choices({'external': 'Independent tenant', **{k: v for k, v in names.items() if k not in (scope, 'personal')}})), field('tenant_name', 'Tenant name', 'Independent household' if space['use']=='residential' else 'Independent business tenant'), dollars('rent', 'Monthly rent', prop.suggested_rent // max(1, len(prop.spaces)), 10000), number('months', 'Lease months', 12, 1, 120), number('deposit_months', 'Deposit months', 1, 0, 3), number('escalation_percent', 'Annual rent increase (%)', 2, 0, 8)]))
                forms.append(form('convert_space', 'Convert · ' + prop.name + ' / ' + space['name'], 'Costs $200 per square meter and takes 45 days.', unit + [select('use', 'New permitted use', choices({'commercial': 'Commercial', 'industrial': 'Industrial', 'residential': 'Residential'}))]))
        leases = [l for l in s['leases'] if l['owner'] == scope]
        tables.append(table('Lease register', ['Tenant', 'Monthly rent', 'Deposit still owed', 'Arrears', 'End date', 'Status'], [(l['tenant_name'], money(l['rent']), money(l['deposit_remaining']), money(l['arrears']), l['end_date'], l['status']) for l in leases]))
        for lease in leases:
            base = [hidden('lease_id', lease['id'])]
            if lease['status'] == 'active':
                forms.append(form('end_lease', 'End lease · ' + lease['tenant_name'], 'Early termination costs one month of rent. Deposits and unpaid rent remain recorded.', base))
                if lease['arrears'] and lease['tenant']=='external':
                    forms.append(form('lease_response', 'Resolve arrears · ' + lease['tenant_name'], 'Arrange repayment or give 30 days of possession notice.', base + [select('response', 'Response', choices({'plan': 'Payment plan', 'vacate': 'Possession notice'}))]))
            if lease['arrears'] and lease['tenant'] == 'external':
                forms.append(form('write_off_rent', 'Write off arrears · ' + lease['tenant_name'], 'Recognize uncollectible rent as a loss.', base))

    elif page == 'franchises':
        view.update(title='Brands and franchises', intro='Independent operators own their cash, employees, and trading results. Your group earns fees and royalties under the contract.')
        eligible = choices({b.id: b.name for b in owned if b.industry in ('retail', 'restaurant')})
        if eligible:
            forms.append(form('create_brand', 'Establish a brand', 'Requires 12 weeks of positive combined operating profit. Standards and training preparation cost $5,000.', [select('business_id', 'Proven business', eligible), field('name', 'Brand name'), number('royalty', 'Royalty (%)', 6, 2, 10)]))
            forms.append(form('join_franchise', 'Join an established brand', 'Costs $20,000 plus 6% of actual sales. Price standards and annual renewal apply.', [select('business_id', 'Operating company', eligible)]))
        brands = [b for b in s['brands'] if campaign.controlled(b['entity'])]
        if brands:
            forms.append(form('grant_franchise', 'Grant a territory', 'Each staffed brand manager supports up to three operators. Net launch support costs $5,000; preparation takes 30 days.', [select('brand_id', 'Brand', choices({b['id']: b['name'] for b in brands})), select('region', 'Territory', regions), field('staff_access', 'Permit shared staffing under service agreements', False, 'checkbox')]))
        contracts = [f for f in s['franchises'] if campaign.controlled(f['operator']) or campaign.controlled(f['issuer'])]
        tables.append(table('Franchise contracts', ['Operator', 'Territory', 'Royalty', 'Latest paid', 'Expiry', 'Status'], [(next(b.name for b in world.businesses if b.id == f['operator']), f['region'], str(f['royalty']) + '%', money(f.get('last_royalty', 0)), f['end_date'], f['status']) for f in contracts]))
        for contract in contracts:
            if contract['status'] == 'active':
                for action, label, description in [('franchise_audit', 'Audit', 'Spend $250 on a dated quality assessment.'), ('renew_franchise', 'Renew', 'Extend the agreement by one year for $3,000.'), ('end_franchise', 'End agreement', 'Ends brand affiliation while preserving the operating company and employment records.')]:
                    forms.append(form(action, label + ' · ' + contract['id'], description, [hidden('franchise_id', contract['id'])]))
        if not eligible and not contracts:
            view['notes'].append('Acquire or open a retail or restaurant business to join or develop a franchise.')

    elif page == 'settings':
        settings = s['settings']
        view.update(title='Campaign settings', intro='Start another campaign in a separate save, or configure this owner’s journey.')
        view['metrics'] = [('Mode', settings['mode'].title()), ('Score records', 'Modified sandbox' if settings['modified'] else 'Standard')]
        forms.append(form('settings', 'Owner and cash alerts', 'A zero cash threshold disables the alert. Succession is optional and never forced by age.', [field('succession', 'Enable optional succession', settings['succession'], 'checkbox'), dollars('stop_cash', 'Personal cash alert threshold', settings['stop_cash'])]))
        forms.append(form('settings','Time-skip interruptions','Routine completions stay in the activity log by default. Financial updates below the minimum do not pause; exactly the minimum does. Zero includes every financial event. Required approvals, unpaid payroll, breached reserves and business failure always stop time.', [dollars('financial_pause_threshold','Minimum financial event to pause',settings.get('financial_pause_threshold',100000)),field('pause_routine','Pause for routine completions',settings.get('pause_routine',False),'checkbox')]))
        if settings['succession']:
            forms.append(form('succession', 'Choose a successor', 'Costs $1,000. The portfolio, companies and employees continue under the new owner.', [field('name', 'Successor name'), number('age', 'Age', 30, 18, 80)]))
        if settings['mode'] == 'sandbox':
            forms.append(form('sandbox_funds', 'Add sandbox capital', 'Capital is added personally and the campaign remains marked as modified.', [hidden('entity', 'personal'), dollars('amount', 'Capital injection', 10000000, 10000)]))
        forms.append(form('new_campaign', 'Start a separate campaign', 'The current save is retained. Guided and Entrepreneur start on January 1, 2026 with $350,000; custom dates and capital require Sandbox.', [field('campaign_name','Game name','My new game'),field('name', 'Owner name', 'Alex Morgan'), select('mode', 'Starting mode', choices({'entrepreneur': 'Entrepreneur', 'guided': 'Guided retail start', 'sandbox': 'Sandbox'})), number('seed', 'World seed', 42, 0, 2147483647), dollars('capital', 'Starting capital', 35000000, 10000000), field('starting_date', 'Starting date', '2026-01-01', 'date')]))

    elif page == 'scorecard':
        view.update(title='Empire scorecard', intro='Wealth, profit, employment, and morale remain separate measures. Monthly snapshots retain the campaign’s sandbox label.')
        context = business_context(world, 'personal')
        people = {e['person_id'] for e in context['employees'] if e['status'] == 'active'}
        view['metrics'] = [('Total wealth', money(context['total_wealth'])), ('Lifetime group profit', money(context['group_profit'])), ('Employees', len(people)), ('Morale', context['average_morale'] if context['average_morale'] is not None else 'No employees')]
        tables.append(table('Monthly snapshots', ['Date', 'Wealth', 'Lifetime profit', 'Inflation-adjusted profit', 'Employees', 'Morale', 'Record'], [(h['date'], money(h['wealth']), money(h['profit']), money(h['real_profit']), h['employees'], h['morale'] if h['employees'] else '—', 'Sandbox' if h['modified'] else 'Standard') for h in reversed(s['score_history'])]))

    elif page == 'forecast':
        view.update(title='Operating forecast', intro='Compare lower, current, and higher demand over 1–90 days using copies of the current campaign. No live money or time is changed.')
        view['notes'].append('Scenarios continue existing commitments and management authority. They assume no new owner decisions and are not probabilities. Longer forecasts may take a moment.')
