"""Specific work products delivered through the finite service office queue."""
from datetime import date, timedelta
from .campaign import Campaign
from .domain import RuleError
from .simulation_support import stable_roll


# Effort is qualified provider minutes. Projects never appoint or hire automatically.
PRODUCTS = {
    'property_representation': ('real_estate_agent', 'Prepare property closing in house', 960),
    'role_search': ('hr', 'Recruit for a selected role', 720),
    'assessment': ('hr', 'Assess a candidate', 240),
    'onboarding': ('hr', 'Onboard an employee', 480),
    'succession': ('hr', 'Prepare a succession shortlist', 960),
    'pos_deployment': ('it', 'Deploy checkout systems', 1440),
    'inventory_integration': ('it', 'Integrate inventory planning', 1440),
    'system_support': ('it', 'Maintain deployed systems', 480),
}


class ServiceProducts(Campaign):
    def prepare(self, task, args):
        from .commercial_work import CommercialWork
        if CommercialWork(self.e).prepare(task,args):return
        product = args.get('product', '')
        if not product:
            return
        if product not in PRODUCTS or PRODUCTS[product][0] != task['department']:
            raise RuleError('Select a work product belonging to the delivering department.')
        from .business_rules import BusinessRules
        from .business_models import INDUSTRY_ROLES
        from .industries import SALES
        rules = BusinessRules(self.e)
        if product=='property_representation':
            p=self.e.get_property(task['target_id'])
            if task['mode']!='internal':raise RuleError('Use an in-house licensed agent for representation; ordinary closing quotes already include outside brokerage.')
            if p.owner and p.owner!=task['recipient']:raise RuleError('Representation must be for this property owner or a prospective buyer.')
            if any(t.get('product')==product and t['recipient']==task['recipient'] and t['target_id']==p.id and t['status'] in ('queued','working') for t in self.s.get('service_tasks',[])):raise RuleError('Representation is already queued for this transaction.')
            from .internal_property_services import agent_work_minutes
            provider=rules.company(task['provider'])
            recipient=next((b for b in self.w.businesses if b.id==task['recipient']),None)
            task.update(product=product,effort=960,remaining=960,labor_remaining=agent_work_minutes(self.w,provider,recipient,p))
            return
        b = rules.company(task['recipient'])
        if b.status != 'operating':
            raise RuleError('Specific service projects require an operating recipient.')
        role = args.get('role', 'manager')
        if product in ('role_search', 'assessment', 'succession') and role not in INDUSTRY_ROLES[b.industry]:
            raise RuleError('Select a role used by this business.')
        target = task['target_id']
        if product == 'assessment' and not rules.person(target).candidate:
            raise RuleError('Select an available candidate for assessment.')
        if product == 'onboarding':
            emp = rules.contract(target)
            if emp.employer != b.id or emp.status != 'active':
                raise RuleError('Select an active employee at the receiving business.')
            if any(t.get('product') == product and t['target_id'] == target and t['status'] != 'cancelled'
                   for t in self.s.get('service_tasks', [])):
                raise RuleError('This employee already has an onboarding project.')
            task.update(participant_required=120, participant_done=0)
        if product in ('pos_deployment', 'inventory_integration'):
            if b.industry not in SALES:
                raise RuleError('Checkout and inventory integration require an inventory sales business.')
            if product in self.s.get('deployed_systems', {}).get(b.id, {}):
                raise RuleError('This system is installed. Request system support to maintain it.')
            if any(t.get('product') == product and t['recipient'] == b.id and t['status'] in ('queued', 'working')
                   for t in self.s.get('service_tasks', [])):
                raise RuleError('This deployment is already queued.')
        if product == 'system_support' and not self.s.get('deployed_systems', {}).get(b.id):
            raise RuleError('Deploy a system before requesting its maintenance.')
        task.update(product=product, role=role, effort=PRODUCTS[product][2], remaining=PRODUCTS[product][2])

    def participant_minutes(self, emp, available):
        """Reserve paid trainee time once per day, from their actual scheduled shift."""
        tasks = sorted((t for t in self.s.get('service_tasks', []) if t.get('product') == 'onboarding'
                        and t['target_id'] == emp.id and t['status'] in ('queued', 'working')),
                       key=lambda t: (t['priority'], t['due'], t['id']))
        total = 0
        for task in tasks:
            if task.get('participant_date') == self.w.date:
                continue
            used = min(max(0, available - total), 60, task['participant_required'] - task['participant_done'])
            task['participant_done'] += used
            task['participant_date'] = self.w.date
            total += used
        return total

    def ready(self, task):
        if task.get('product') != 'onboarding':
            return True
        emp = next((e for e in self.w.employments if e.id == task['target_id']), None)
        return not emp or emp.status != 'active' or task['participant_done'] >= task['participant_required']

    def estimate(self, person, skill, quality, key):
        uncertainty = max(3, (100 - quality) // 3)
        center = max(0, min(100, person.skills.get(skill, 30) + stable_roll(self.w, key, uncertainty * 2 + 1) - uncertainty))
        return max(0, center - uncertainty), min(100, center + uncertainty)

    def finish(self, task, quality):
        from .commercial_work import CommercialWork
        if CommercialWork(self.e).finish(task,quality):return True
        product = task.get('product')
        if not product:
            return False
        from .business_rules import BusinessRules
        if product=='property_representation':
            task['expires']=(date.fromisoformat(self.w.date)+timedelta(days=90)).isoformat()
            task['outcome']='Closing representation prepared. One purchase or sale for this client within 90 days reduces brokerage by 70%; legal and title expenses remain. Staff time and allocated costs are recorded.'
            return True
        from .business_models import ROLE_SKILLS
        from .specialists import LICENSES
        rules = BusinessRules(self.e)
        b = rules.company(task['recipient'], owned=False)
        if b.status != 'operating' or not self.controlled(b.id):
            task['outcome'] = 'Recipient no longer available. Completed work and costs retained; no deployment or appointment made.'
            return True
        role = task['role']; skill = ROLE_SKILLS.get(role, 'leadership')
        if product == 'role_search':
            applicants = []
            for _ in range(1 + quality // 35):
                rules.make_person(role, candidate=True)
                person = self.w.people[-1]
                person.home_region = b.region
                person.demonstrated=[]
                applicants.append(person.id)
            task['applicants'] = applicants
            task['outcome'] = f'{len(applicants)} ordinary applicants sourced for {role}. Qualifications, availability and pay expectations still govern hiring.'
        elif product == 'assessment':
            person = rules.person(task['target_id'])
            if not person.candidate:
                task['outcome'] = 'Candidate is no longer available; no assessment was represented as a job offer.'
                return True
            low, high = self.estimate(person, skill, quality, task['id'])
            task['assessment'] = dict(person_id=person.id, skill=skill, low=low, high=high,
                                      qualifications=list(person.qualifications), licenses=dict(person.licenses))
            person.observations.append(dict(date=self.w.date, source='HR assessment', confidence='Estimated',
                detail=f'{skill}: {low}–{high}. Credentials checked; assessment is uncertain and does not guarantee performance.'))
            task['outcome'] = f'{person.name}: estimated {skill} {low}–{high}; credentials recorded. No offer made.'
        elif product == 'onboarding':
            emp = next((e for e in self.w.employments if e.id == task['target_id']), None)
            if not emp or emp.status != 'active' or emp.employer != b.id:
                task['outcome'] = 'Employee left before onboarding finished; incurred time and costs remain.'
                return True
            person = rules.person(emp.person_id)
            person.trust = min(100, person.trust + quality // 15)
            person.burnout = max(0, person.burnout - quality // 15)
            emp.probation_until = min(emp.probation_until, self.w.date) if emp.probation_until else None
            rules.record(person.id, 'Completed paid onboarding with two hours of employee participation and HR delivery.')
            task['outcome'] = 'Onboarding completed with 120 paid employee minutes. Trust improved and onboarding stress reduced.'
        elif product == 'succession':
            candidates = []
            license_name = LICENSES.get(role)
            for emp in rules.staff(b.id):
                person = rules.person(emp.person_id)
                if rules.position(emp.position_id).role == role:
                    continue
                low, high = self.estimate(person, skill, quality, task['id'] + ':' + person.id)
                eligible = (not license_name or person.licenses.get(license_name, '') >= self.w.date)
                if role == 'engineer':
                    eligible = eligible and any('Engineering' in q for q in person.qualifications)
                candidates.append(dict(employment_id=emp.id, person_id=person.id, low=low, high=high,
                    eligible=eligible, notice=person.notice_on, development='Credential renewal or qualification required' if not eligible else 'Develop role skills' if low < 55 else 'Interview for a vacancy'))
            candidates.sort(key=lambda c: (not c['eligible'], bool(c['notice']), -c['low'], c['employment_id']))
            task['shortlist'] = candidates[:5]
            task['outcome'] = f'Succession review for {role}: {len(candidates[:5])} internal candidates with estimated readiness and credential gaps. Promotion remains a separate authorized offer.'
        elif product in ('pos_deployment', 'inventory_integration'):
            self.s.setdefault('deployed_systems', {}).setdefault(b.id, {})[product] = dict(
                source=task['id'], installed=self.w.date, condition=100, quality=quality, last_used='', last_support=self.w.date)
            task['outcome'] = 'System deployed. Its effect uses actual checkout labor or inventory demand history; condition wears with use and support consumes new work.'
        else:
            for system in self.s.get('deployed_systems', {}).get(b.id, {}).values():
                system['condition'] = min(100, system['condition'] + max(10, quality))
                system['last_support'] = self.w.date
            task['outcome'] = 'Installed systems serviced. Their recorded condition recovered; future use still causes wear.'
        return True

    def operate(self, b, buckets):
        if date.fromisoformat(self.w.date).weekday() >= 5:
            return
        for product, system in self.s.get('deployed_systems', {}).get(b.id, {}).items():
            if system['condition'] <= 0 or system['last_used'] == self.w.date:
                continue
            if product == 'pos_deployment':
                from .industries import SALES
                role = SALES[b.industry][0]
                gain = system['quality'] * system['condition'] // 800
                buckets[role] = [v * (100 + gain) // 100 for v in buckets.get(role, [])]
            system['condition'] -= 1; system['last_used'] = self.w.date
            if system['condition'] in (20, 0):
                self.e.event('Deployed system needs support', b.name + ': ' + product.replace('_', ' ') +
                             f' condition is {system["condition"]}/100. Request IT system support.', system['condition'] == 0)

    def stock_target(self, b):
        from .restaurant import active,expected,settings
        if active(self.w,b):
            from datetime import timedelta
            today=date.fromisoformat(self.w.date)
            return max(expected(self.w,b,today+timedelta(days=i)) for i in range(7))*settings(self.w,b)['stock_days']
        system = self.s.get('deployed_systems', {}).get(b.id, {}).get('inventory_integration')
        if not system or system['condition'] < 20:
            return b.daily_demand * 5
        history = [r for r in b.history[-14:] if r.get('demand', 0) > 0]
        demand = sum(r['demand'] for r in history) // len(history) if history else b.daily_demand
        # Smaller batches reduce working capital and expiry exposure; no demand or stock is invented.
        return max(1, demand * 2)
