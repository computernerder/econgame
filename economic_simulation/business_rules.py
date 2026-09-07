"""Acquisitions, workforce decisions, and distinct industry operating models."""
from __future__ import annotations

import calendar
import random
from datetime import date, timedelta

from .positions import open_positions, position_open
from .industries import SALES, PROJECTS, sales_capacity, project_capacity
from .business_models import BENEFITS, INDUSTRY_ROLES, ROLE_PAY, ROLE_SKILLS, Business, Employment, Person, Position, investment_account
from .domain import BUSINESS_CONTENT, Engine, Property, RuleError, calendar_target, daily_share, tuples

NAMES = ["Jordan Chen", "Morgan Ellis", "Taylor Brooks", "Casey Rivera", "Sam Patel", "Avery Martin", "Riley Park", "Jamie Clarke", "Cameron Reed", "Drew Bennett", "Robin Shah", "Quinn Foster", "Alex Kim", "Emery Lewis", "Reese Walker", "Skyler Hayes", "Dakota Lane", "Parker Cole", "Blair Davis", "Sage Turner"]


def weekday_share(amount, today):
    days = [d for d in range(1, calendar.monthrange(today.year, today.month)[1]+1) if date(today.year,today.month,d).weekday()<5]
    if today.day not in days:
        return 0
    index = days.index(today.day)
    return amount*(index+1)//len(days)-amount*index//len(days)


def whole_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RuleError("Use whole numbers for quantities, hours and prices.")
    try:
        return int(value)
    except ValueError:
        raise RuleError("Use whole numbers for quantities, hours and prices.")


class BusinessRules:
    def __init__(self, engine: Engine):
        self.e = engine
        self.w = engine.world

    def roll(self, low: int, high: int) -> int:
        rng = random.Random(self.w.seed + 7391)
        if self.w.business_rng_state is not None:
            rng.setstate(tuples(self.w.business_rng_state))
        value = rng.randint(low, high)
        self.w.business_rng_state = rng.getstate()
        return value

    def company(self, business_id: str, owned: bool = True) -> Business:
        business = next((b for b in self.w.businesses if b.id == business_id), None)
        from .campaign import Campaign
        if not business or (owned and not Campaign(self.e if hasattr(self,'e') else Engine(self.w)).controlled(business_id)):
            raise RuleError("Choose a business you own.")
        return business

    def person(self, person_id: str) -> Person:
        person = next((p for p in self.w.people if p.id == person_id), None)
        if not person:
            raise RuleError("That person is not available.")
        return person

    def position(self, position_id: str) -> Position:
        pos = next((p for p in self.w.positions if p.id == position_id), None)
        if not pos:
            raise RuleError("That position is not available.")
        return pos

    def contract(self, employment_id: str) -> Employment:
        emp = next((e for e in self.w.employments if e.id == employment_id), None)
        if not emp or emp.employer not in self.w.accounts or emp.status not in ("active", "joining"):
            raise RuleError("Choose a current employment in an owned business.")
        return emp

    def staff(self, bid: str, include_joining: bool = False) -> list[Employment]:
        statuses = ("active", "joining") if include_joining else ("active",)
        return [e for e in self.w.employments if e.employer == bid and e.status in statuses]

    def parent(self, entity: str) -> str:
        return "personal" if entity == "company" else self.company(entity,owned=False).owner

    def skill(self, role: str) -> str:
        return ROLE_SKILLS[role]

    def make_person(self, role: str, candidate: bool = False) -> Person:
        number = self.w.next_person_id
        self.w.next_person_id += 1
        skill = self.skill(role)
        skills = {key: self.roll(25, 65) for key in sorted(set(ROLE_SKILLS.values()))}
        skills[skill] = self.roll(62, 88)
        qualifications = ["High school diploma"]
        if role == "engineer": qualifications += ["Bachelor of Electrical Engineering"]
        if role == "technician": qualifications += ["Engineering technology diploma"]
        if role == "chef": qualifications += ["Culinary certificate"]
        if role in ("manager", "property_manager"): qualifications += ["Bachelor of Business Administration"]
        if role == "maintenance": qualifications += ["Building maintenance certificate"]
        if role in ("tradesperson","builder","mechanic"): qualifications += ["Vocational trade certificate"]
        if role == "loan_officer": qualifications += ["Banking and credit training"]
        if role=='security_guard':qualifications += ['Security officer certificate']
        # A known degree does not expose a skill that has never been demonstrated.
        if role == "cashier" and number % 2 == 0:
            qualifications += ["Bachelor of Electrical Engineering"]
            skills["engineering"] = self.roll(65, 88)
        birth = date.fromisoformat(self.w.date).replace(year=date.fromisoformat(self.w.date).year - self.roll(24, 49), day=1)
        from .employee_names import unique_name
        p = Person(f"person-{number}", unique_name(self.w,f"person-{number}"), birth.isoformat(), qualifications, skills, [skill], ["Expertise", "Leadership", "Stable hours", "Higher income"][self.roll(0, 3)], self.roll(2, 15), candidate=candidate)
        p.labor_state='unemployed' if candidate else 'employed'
        if role in ('engineer','chef','legal','accounting'):
            license_name={'engineer':'professional_engineer','chef':'food_safety','legal':'legal_practice','accounting':'accounting'}[role]
            p.licenses[license_name]=(date.fromisoformat(self.w.date)+timedelta(days=1095)).isoformat()
        if role=='security_guard':p.licenses['security_guard']=(date.fromisoformat(self.w.date)+timedelta(days=1095)).isoformat()
        if role in ('real_estate_agent','electrician','plumber','hvac_technician'):
            from .specialists import LICENSES
            p.licenses[LICENSES[role]]=(date.fromisoformat(self.w.date)+timedelta(days=1095)).isoformat()
            p.qualifications.append('Real estate practice certificate' if role=='real_estate_agent' else 'Vocational trade certificate')
        self.w.people.append(p)
        return p

    def add_business(self, template_index: int, group: bool = False) -> None:
        spec = dict(BUSINESS_CONTENT["catalog"][template_index])
        catalog_name = spec["name"]
        staff = spec.pop("staff")
        property_specs = spec.pop("properties", [])
        number = self.w.next_business_id
        self.w.next_business_id += 1
        bid = f"business-{number}"
        from .world_names import business_name, property_name
        spec['name']=business_name(self.w,bid,'holding' if group else spec['industry'])
        business = Business(id=bid, **spec)
        self.w.businesses.append(business)
        manager_id = None
        for index, (role, salary, hours) in enumerate(staff):
            person = self.make_person(role)
            pos = Position(f"{bid}-position-{index+1}", bid, role, manager_id)
            self.w.positions.append(pos)
            if role == "manager" or (role == "property_manager" and manager_id is None): manager_id = pos.id
            person.history.append(dict(date=self.w.date, event=f"Employed by {business.name} before acquisition."))
            self.w.employments.append(Employment(f"{bid}-employment-{index+1}", person.id, pos.id, bid, salary, hours, self.w.date, status="seller"))
        for index, spec in enumerate(property_specs):
            spec = dict(spec)
            use, basis = spec.pop("use"), spec.pop("basis")
            spec["description"] = spec["description"].replace(catalog_name, business.name)
            p = Property(**spec, id=f"{bid}-property-{index+1}", asking=0, status="business_asset", reserved_for=bid, acquisition_basis=basis, occupancy_use=use)
            p.name=property_name(self.w,p.id,p.category,p.kind)
            self.w.properties.append(p)

    def initialize(self) -> None:
        if self.w.businesses:
            return
        for index in range(len(BUSINESS_CONTENT["catalog"])):
            self.add_business(index)
        for role in ROLE_SKILLS:
            self.make_person(role, candidate=True)
        self.make_person("cashier", candidate=True)

    def quote(self, bid: str) -> dict:
        b = self.company(bid, owned=False)
        properties = [p for p in self.w.properties if p.reserved_for == bid]
        inventory = b.inventory_units * b.unit_cost
        property_basis = sum(p.acquisition_basis for p in properties)
        children=[child for child in self.w.businesses if child.market_parent==b.id and child.owner is None and child.status=='market']
        net_assets = b.cash_at_sale + b.equipment + inventory + property_basis + sum(child.asking for child in children)
        fee = b.asking // 100
        return dict(children=children,price=b.asking, fee=fee, total=b.asking + fee, cash=b.cash_at_sale, equipment=b.equipment, inventory=inventory, property_basis=property_basis, net_assets=net_assets, goodwill=b.asking-net_assets, properties=properties, staff=[e for e in self.w.employments if e.employer==bid and e.status=="seller"])

    def acquire(self, b: Business) -> None:
        q = self.quote(b.id)
        if q["goodwill"] < 0:
            raise RuleError("The acquisition has an unsupported negative goodwill value.")
        parent = b.reserved_by
        self.w.accounts[b.id] = {}
        self.e.post(b.id, f"opening:{b.id}", f"Acquired opening balances: {b.name}", {"asset:cash":q["cash"], "asset:equipment":q["equipment"], "asset:inventory":q["inventory"], "asset:property":q["property_basis"], **{f"asset:escrow:{child.id}":child.asking for child in q["children"]}, "equity:capital":-q["net_assets"]})
        self.e.post(parent, f"acquisition:{b.id}", f"Company acquisition completed: {b.name}", {f"asset:escrow:{b.id}":-b.escrow, investment_account(b.id):q["net_assets"], f"asset:goodwill:{b.id}":q["goodwill"]})
        b.owner, b.status, b.acquired_on = parent, "operating", self.w.date
        b.escrow, b.closing_on = 0, None
        for child in q['children']:
            child.reserved_by=b.id;child.escrow=child.asking
            self.acquire(child)
        for office in self.w.systems.get('offices',[]):
            if office['business_id']==b.id:office['active']=True
        for p in q["properties"]:
            p.owner, p.basis, p.bought_on = b.id, p.acquisition_basis, self.w.date
            if p.occupancy_use == "operating":
                p.status, p.occupant = "occupied", b.id
            else:
                p.status, p.rent, p.tenant = "rented", p.suggested_rent, f"Inherited household {p.id}"
                p.lease_end = calendar_target(date.fromisoformat(self.w.date), "year").isoformat()
        for emp in self.w.employments:
            if emp.employer == b.id and emp.status == "seller":
                emp.status = "active"
                self.record(emp.person_id, f"Employment continued when {b.name} was acquired.")
        self.e.event("Business acquisition completed", f"{b.name} joined your portfolio with {len(q['staff'])} employees and {len(q['properties'])} properties. Select its account to manage it.", True)

    def record(self, person_id: str, text: str) -> None:
        person = self.person(person_id)
        person.history.append(dict(date=self.w.date, event=text))
        person.history = person.history[-50:]

    def check_schedule(self, emp: Employment, replacing: str | None = None) -> None:
        if not 4 <= emp.weekly_hours <= 60 or not 0 <= emp.shift_start <= 20:
            raise RuleError("Use 4–60 weekly hours and a shift beginning between 00:00 and 20:00.")
        if len(set(emp.days)) != len(emp.days) or not emp.days or any(type(d) is not int or d not in range(7) for d in emp.days):
            raise RuleError("Choose distinct working days.")
        minutes = emp.weekly_hours * 60 // len(emp.days)
        if minutes > 720 or emp.shift_start*60 + minutes > 1440:
            raise RuleError("A scheduled shift cannot exceed 12 hours or extend past midnight.")
        others = [e for e in self.w.employments if e.person_id == emp.person_id and e.id != replacing and e.status in ("active","joining","seller")]
        if sum(e.weekly_hours for e in others) + emp.weekly_hours > 60:
            raise RuleError("This person would have more than 60 committed work hours per week.")
        for other in others:
            if set(other.days).intersection(emp.days):
                end = emp.shift_start*60 + minutes
                other_end = other.shift_start*60 + other.weekly_hours*60//len(other.days)
                if max(emp.shift_start, other.shift_start)*60 < min(end, other_end):
                    raise RuleError("This shift overlaps another employment commitment.")

    def action(self, action: str, args: dict, command_id: str) -> str:
        target=args.get('business_id')
        if args.get('employment_id'):
            target=self.contract(args['employment_id']).employer
        if args.get('position_id'):
            target=self.position(args['position_id']).business_id
        if target and action not in ('fund_business','distribute_profit') and self.company(target,owned=False).status=='closed':
            raise RuleError('This operation is closed. Settle liabilities, collect receivables or liquidate its remaining assets from Operations.')
        if action=='hire_for_role':
            from .staffing import vacancies
            b=self.company(args.get('business_id',''));role=args.get('role','')
            if role not in INDUSTRY_ROLES[b.industry]:raise RuleError('Choose a role used by this business.')
            vacant=vacancies(self.w,b.id,role)
            if args.get('position_id'):
                pos=next((p for p in vacant if p.id==args['position_id']),None)
                if not pos:raise RuleError('This vacancy is no longer available. Refresh the hiring guide.')
            elif vacant:pos=vacant[0]
            else:
                self.action('create_position',{'business_id':b.id,'role':role},command_id+':vacancy')
                pos=self.w.positions[-1]
            hiring_result=self.action('hire',{**args,'position_id':pos.id},command_id)
            emp=self.w.employments[-1]
            from .workforce import Workforce
            from .domain import GAME_RULES
            workforce=Workforce(self.e);policy=workforce.effective(b.id,emp)[0]
            benefits=workforce.benefit_cost(emp,policy)
            wages=emp.salary+emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
            tax=wages*GAME_RULES['tax']['payroll_percent']//100
            from .money_display import money
            return f"{hiring_result} Estimated monthly employer cost: {money(wages+benefits+tax)} ({money(wages)} wages, {money(benefits)} benefits, {money(tax)} payroll tax)."
        if action == "acquire_business":
            b = self.company(args.get("business_id", ""), owned=False)
            parent = args.get("entity", "personal")
            from .campaign import Campaign
            Campaign(self.e).require(parent)
            if parent not in self.w.accounts or b.owner is not None or b.status != "market" or b.market_parent:
                raise RuleError("Choose an available business and one of your accounts.")
            q = self.quote(b.id)
            self.e.post(parent, command_id, f"Fund acquisition: {b.name}", {"asset:cash":-q["total"], f"asset:escrow:{b.id}":q["price"], "expense:acquisition":q["fee"]})
            b.status, b.reserved_by, b.escrow = "closing", parent, b.asking
            b.closing_on = (date.fromisoformat(self.w.date)+timedelta(days=3)).isoformat()
            self.e.event("Business purchase agreed", f"{b.name} closes on {b.closing_on}. Purchase funds are held in escrow; staff and assets transfer together.")
            return "Acquisition funded. Advance three days to take ownership."
        if action in ("fund_business", "distribute_profit"):
            entity = args.get("business_id", "")
            if entity not in self.w.accounts or entity == "personal": raise RuleError("Choose a company you own.")
            from .campaign import Campaign
            Campaign(self.e).require(entity)
            parent = self.parent(entity)
            amount = args.get("amount")
            if type(amount) is not int or amount <= 0: raise RuleError("Enter a positive money amount.")
            if action == "fund_business":
                self.e.post(parent, command_id+":parent", f"Capital contribution to {entity}", {"asset:cash":-amount,investment_account(entity):amount})
                self.e.post(entity, command_id+":child", "Capital received from owner", {"asset:cash":amount,"equity:capital":-amount})
                return "Capital transferred from the direct owner's account."
            accounts = self.w.accounts[entity]
            profit = -sum(v for k,v in accounts.items() if k.startswith(("income:","expense:"))) - accounts.get("equity:distributions",0)
            if amount > profit: raise RuleError("Distributions cannot exceed accumulated, undistributed profit.")
            self.e.post(entity, command_id+":child", "Profit distributed to owner", {"asset:cash":-amount,"equity:distributions":amount})
            self.e.post(parent, command_id+":parent", f"Distribution received from {entity}", {"asset:cash":amount,"income:dividends":-amount})
            return "Profit distributed to the direct owner. Group reports eliminate the internal dividend."
        if action == "business_policy":
            b = self.company(args.get("business_id", ""))
            benefits = args.get("benefits", b.benefits)
            price = whole_number(args.get("price_percent", b.price_percent))
            if benefits not in BENEFITS or not 75 <= price <= 150: raise RuleError("Choose a benefits package and a price from 75% to 150%.")
            if any(f['operator']==b.id and f['status']=='active' for f in self.w.systems.get('franchises',[])) and not 90<=price<=110:raise RuleError('This franchise agreement limits prices to 90–110% of standard.')
            b.benefits, b.price_percent = benefits, price
            kit_policy=self.w.systems.get('revenue_kits',{}).get(b.id)
            if kit_policy and b.industry=='gas_station':kit_policy['offers']['fuel']['price_percent']=price
            b.auto_restock = args.get("auto_restock", "on") in (True, "true", "on")
            if "operating_policy" in b.authority:b.authority["operating_policy"]["stock"]=b.auto_restock
            self.e.event("Business policy updated", f"{b.name}: new prices and benefits apply to future days. Existing leases and project fees are unchanged.")
            return f"Benefits: {benefits}. Prices: {price}% of standard. Automatic stock replenishment: {'on' if b.auto_restock else 'off'}. Changes apply to future operations."
        if action == "restock":
            b = self.company(args.get("business_id", ""))
            units = whole_number(args.get("units", 0))
            if b.industry not in SALES or not 1 <= units <= 10000: raise RuleError("Choose 1–10,000 inventory units for an inventory business.")
            cost = units * b.unit_cost
            self.e.post(b.id, command_id, "Inventory purchased", {"asset:cash":-cost,"asset:inventory":cost})
            from .industry_operations import IndustryOperations
            IndustryOperations(self.e).add_stock(b,units)
            b.inventory_units += units
            return "Stock purchased. It becomes an expense when sold, consumed or wasted."
        if action == "new_project":
            b = self.company(args.get("business_id", ""))
            from .engineering import accept
            return accept(self,b,kit_key=args.get('kit') or None)
        if action == "engineering_policy":
            b=self.company(args.get('business_id',''))
            if b.industry not in PROJECTS:raise RuleError('Select a project business.')
            from .campaign import flag,integer
            b.concurrent_project_limit=integer(args.get('concurrent_project_limit',b.concurrent_project_limit),1,10)
            b.project_planning_days=integer(args.get('project_planning_days',b.project_planning_days),5,120)
            b.auto_projects=flag(args.get('auto_projects'))
            if 'operating_policy' in b.authority:b.authority['operating_policy']['jobs']=b.auto_projects
            return 'Automatic job acceptance '+('enabled. The business takes its next quoted job on the next staffed working day; routine completions do not pause time.' if b.auto_projects else 'disabled. Current work continues; you choose when to accept the next job.')
        if action == "bank_policy":
            b=self.company(args.get('business_id',''))
            if b.industry!='bank':raise RuleError('Select a bank.')
            from .campaign import flag,integer
            b.auto_lending=flag(args.get('auto_lending'))
            b.bank_reserve_percent=integer(args.get('reserve_percent',b.bank_reserve_percent),25,100)
            return 'Lending policy updated. Existing loans keep their agreed terms; deposit withdrawals and repayments continue.'
        if action == "remove_vacancy":
            from .positions import remove_vacancy
            return remove_vacancy(self, args.get("position_id", ""))
        if action == "create_position":
            b = self.company(args.get("business_id", ""))
            role = args.get("role", "")
            if role not in INDUSTRY_ROLES[b.industry]: raise RuleError("Choose a role used by this industry.")
            if len(open_positions(self.w,b.id)) >= 100: raise RuleError("This version supports up to 100 positions per business.")
            from .specialists import LICENSES
            license_name=args.get('required_license') or LICENSES.get(role)
            if license_name not in {None,'professional_engineer','food_safety',*LICENSES.values()}:
                raise RuleError('Choose a recognized license requirement.')
            managers = [p.id for p in open_positions(self.w,b.id) if p.role=="manager"]
            number = self.w.next_position_id; self.w.next_position_id += 1
            self.w.positions.append(Position(f"position-new-{number}", b.id, role, managers[0] if managers and role!="manager" else None))
            self.w.positions[-1].required_license=license_name
            return "Vacancy created. Select a candidate and make an offer."
        if action == "hire":
            pos = self.position(args.get("position_id", "")); b = self.company(pos.business_id)
            person = self.person(args.get("person_id", ""))
            if not position_open(self.w,pos): raise RuleError("This vacancy has been removed. Choose an open position.")
            if not person.candidate or any(e.position_id==pos.id and e.status in ("active","joining","seller") for e in self.w.employments): raise RuleError("Choose an available applicant and a vacant position.")
            salary, hours = whole_number(args.get("amount",0)), whole_number(args.get("weekly_hours",40))
            if pos.role == "engineer" and not any("Engineering" in q for q in person.qualifications): raise RuleError("This engineering position requires an engineering qualification.")
            from .specialists import LICENSES
            license_name=pos.required_license or LICENSES.get(pos.role)
            if license_name and person.licenses.get(license_name,'')<self.w.date:raise RuleError('The required professional license is missing or expired.')
            expected = ROLE_PAY[pos.role]*hours//40
            if salary < expected*80//100: raise RuleError("The candidate declined: offer at least 80% of the role's market pay for these hours.")
            from .specialists import recruitment_quote,consume
            recruitment=recruitment_quote(self.w,b.id);fee=recruitment['fee']
            if self.w.cash(b.id) < salary + fee: raise RuleError("Fund at least one month of this salary plus the recruitment fee before hiring.")
            number=self.w.next_employment_id; self.w.next_employment_id += 1
            emp = Employment(f"employment-new-{number}", person.id, pos.id, b.id, salary, hours, (date.fromisoformat(self.w.date)+timedelta(days=3)).isoformat(), status="joining")
            self.check_schedule(emp)
            if recruitment['hr_minutes']:consume(self.w,b.id,"hr",recruitment['hr_minutes'])
            if fee:self.e.post(b.id, command_id, f"Outside hiring support: {person.name}", {"asset:cash":-fee,"expense:recruitment":fee})
            self.w.employments.append(emp); person.candidate=False;person.labor_state="employed"
            self.record(person.id, f"Accepted {pos.role.replace('_',' ')} role at {b.name}; starts {emp.start_date}. "+recruitment['explanation'])
            return f"{person.name} accepted the {pos.role.replace('_',' ')} role for {hours} hours/week, starting {emp.start_date}. {recruitment['explanation']} Payroll begins at their start."
        emp = self.contract(args.get("employment_id", "")); person = self.person(emp.person_id)
        b = self.company(emp.employer); pos = self.position(emp.position_id)
        if action == "employment_terms":
            salary, hours = whole_number(args.get("amount",emp.salary)), whole_number(args.get("weekly_hours",emp.weekly_hours))
            shift = whole_number(args.get("shift_start",emp.shift_start))
            if not 10000 <= salary <= 100000000: raise RuleError("Use a monthly base salary from $100 to $1,000,000.")
            old = emp.salary, emp.weekly_hours, emp.shift_start
            if salary/max(1,hours)>emp.salary/max(1,emp.weekly_hours):
                from .leadership import mark_review
                mark_review(self.w,emp)
            emp.salary, emp.weekly_hours, emp.shift_start = salary,hours,shift
            self.check_schedule(emp, replacing=emp.id)
            self.record(person.id, f"Contract updated: monthly base pay {salary/100:,.2f}, {hours} hours/week, shift starts {shift:02}:00 (previous pay {old[0]/100:,.2f}).")
            return "Future pay and scheduled hours updated. Past payroll is unchanged."
        if action == "train":
            if person.training_until or emp.status != "active": raise RuleError("Choose an active employee not already training.")
            self.e.post(b.id, command_id, f"Training: {person.name}", {"asset:cash":-50000,"expense:training":50000})
            person.training_until=(date.fromisoformat(self.w.date)+timedelta(days=14)).isoformat(); person.training_skill=self.skill(pos.role)
            self.record(person.id, "Started two weeks of training; one working hour per day is reserved for study.")
            return "Training booked for $500. Work capacity is reduced during the 14-day course."
        if action == "leave":
            days=whole_number(args.get("days",7))
            if not 1 <= days <= 14 or emp.leave_until or emp.status!="active": raise RuleError("Choose 1–14 calendar days for an active employee not already on leave.")
            from .time_off import check_legacy
            check_legacy(self.w,emp,days,'vacation')
            today=date.fromisoformat(self.w.date)
            used=sum((today+timedelta(days=i)).weekday() in emp.days for i in range(1,days+1))
            if used > emp.leave_balance: raise RuleError("There are not enough paid leave days available.")
            emp.leave_balance-=used; emp.leave_until=(today+timedelta(days=days)).isoformat()
            self.record(person.id, f"Approved paid leave through {emp.leave_until}; {used} scheduled days used.")
            return "Paid leave approved. Coverage is reduced while the employee rests."
        if action == "end_employment":
            severance=emp.salary*12//52 if emp.status=="active" else 0
            if severance: self.e.post(b.id, command_id, f"Severance: {person.name}", {"asset:cash":-severance,"expense:severance":severance})
            emp.status, emp.end_date="ended",self.w.date
            person.candidate=True; person.morale=max(0,person.morale-8)
            self.record(person.id, f"Employment at {b.name} ended; one week's base pay was paid as severance where active.")
            self.e.event("Position now vacant", f"{person.name} left {b.name}. Their history is retained and the position can be filled again.",True)
            return "Employment ended. Earned payroll remains payable, and the vacancy is preserved."
        raise RuleError("That business action is not available.")

    def start_day(self) -> bool:
        stop=False
        for b in sorted(self.w.businesses,key=lambda b:b.id):
            if b.status=="closing" and b.closing_on<=self.w.date:
                self.acquire(b); stop=True
        for emp in self.w.employments:
            if emp.employer not in self.w.accounts: continue
            if emp.status=="joining" and emp.start_date<=self.w.date:
                emp.status="active"; self.record(emp.person_id,"Started the new role.")
                self.e.event("New employee started",f"{self.person(emp.person_id).name} joined {self.company(emp.employer).name}.",True);stop=True
            if emp.leave_until and emp.leave_until<self.w.date: emp.leave_until=None
        for person in self.w.people:
            if person.training_until and person.training_until<=self.w.date:
                skill=person.training_skill
                person.skills[skill]=min(100,person.skills.get(skill,0)+6)
                if skill not in person.demonstrated: person.demonstrated.append(skill)
                person.training_until,person.training_skill=None,None
                self.record(person.id,f"Completed training; demonstrated {skill} improved.")
                self.e.event("Training completed",f"{person.name} completed their course. Their skill record has been updated.",True);stop=True
        return stop

    def work(self, b: Business, today: date) -> tuple[dict, int]:
        # Hourly coverage preserves simultaneity: an off-shift cook cannot cover a server.
        buckets={role:[0]*24 for role in INDUSTRY_ROLES[b.industry]}
        staff=self.staff(b.id)
        from .workforce import Workforce
        workforce=Workforce(self.e) if self.w.systems else None
        managers=[self.person(e.person_id) for e in staff if self.position(e.position_id).role in ("manager","property_manager")]
        leadership=max((p.skills["leadership"] for p in managers),default=40)
        working_managers=0
        if not hasattr(self.e,'named_capacity'):self.e.named_capacity={}
        if not hasattr(self.e,'named_capacity_dates'):self.e.named_capacity_dates={}
        self.e.named_capacity_dates[b.id]=self.w.date
        self.e.named_capacity[b.id]={}
        if not hasattr(self.e,'named_initial'):self.e.named_initial={}
        self.e.named_initial[b.id]={}
        for emp in staff:
            person=self.person(emp.person_id); role=self.position(emp.position_id).role
            on_leave=bool(emp.leave_until and emp.leave_until>=self.w.date)
            policy,extra_absence=workforce.before_work(emp,person,today) if workforce else ({},False)
            on_leave=on_leave or extra_absence
            scheduled=today.weekday() in emp.days and not on_leave
            overtime=emp.salary*max(0,emp.weekly_hours-40)//max(1,emp.weekly_hours*2)
            salary=daily_share(emp.salary+overtime+emp.compensation.get('shift_premium',0),today)
            from .time_off import unpaid
            if unpaid(self.w,emp):salary=0
            benefits=daily_share(workforce.benefit_cost(emp,policy) if workforce else BENEFITS[b.benefits],today)
            self.e.post(b.id,f"payroll:{emp.id}:{self.w.date}",f"Earned pay and benefits: {person.name}",{"expense:wages":salary,"expense:benefits":benefits,"liability:payroll":-salary-benefits})
            if workforce:
                from .domain import GAME_RULES
                payroll_tax=salary*GAME_RULES['tax']['payroll_percent']//100
                if payroll_tax:self.e.post(b.id,f'payroll-tax:{emp.id}:{self.w.date}','Employer payroll tax',{'expense:payroll_tax':payroll_tax,'liability:payable':-payroll_tax})
            expected=ROLE_PAY[role]*emp.weekly_hours//40
            fair=min(130,emp.salary*100//max(1,expected))
            target=max(10,min(95,60+(fair-90)//3+leadership//10+min(12,(workforce.benefit_cost(emp,policy) if workforce else BENEFITS[b.benefits])//10000)-max(0,emp.weekly_hours-40)-person.burnout//5-(20 if b.payroll_overdue else 0)))
            from .leadership import Leadership
            target=max(10,target-Leadership(self.e).morale_penalty(emp))
            person.morale+=max(-2,min(2,target-person.morale))
            person.engagement+=max(-1,min(1,person.morale-person.engagement))
            person.burnout=max(0,min(100,person.burnout+(2 if scheduled and emp.weekly_hours>40 else -3 if on_leave else -1 if not scheduled else 0)))
            if today.day==1:
                entitlement=policy.get('vacation_days',24)
                emp.leave_balance=max(emp.leave_balance,min(entitlement*2,emp.leave_balance+entitlement*today.month//12-entitlement*(today.month-1)//12))
            pos=self.position(emp.position_id)
            from .specialists import LICENSES
            license_name=pos.required_license or LICENSES.get(pos.role)
            if license_name and person.licenses.get(license_name,'')<self.w.date:
                scheduled=False
                if workforce:workforce.decision('license:'+emp.id+':'+person.licenses.get(license_name,'missing'),'Required license unavailable',person.name+' cannot perform licensed duties until their credential is renewed.',b.id)
            if not scheduled: continue
            cap=min(policy.get('overtime_limit',60),b.authority.get('overtime_cap',60) if b.authority.get('enabled') else 60)
            minutes=min(emp.weekly_hours,cap)*60//len(emp.days)
            if person.training_until: minutes=max(0,minutes-60)
            if person.education: minutes=max(0,minutes-120)
            from .leadership import Leadership
            minutes=max(0,minutes-Leadership(self.e).reserved_minutes(emp))
            from .service_products import ServiceProducts
            minutes-=ServiceProducts(self.e).participant_minutes(emp,minutes)
            skill=self.skill(role)
            quality=max(20,min(115,55+person.skills.get(skill,30)//2+(person.engagement-50)//5-person.burnout//3+min(5,emp.compensation.get("commission_percent",0))))
            start=emp.shift_start*60;end=start+minutes;before_minutes=sum(buckets[role])
            for hour in range(24):
                overlap=max(0,min(end,(hour+1)*60)-max(start,hour*60))
                if workforce:
                    from .shared_services import SharedServices
                    overlap=max(0,overlap-SharedServices(self.e).outgoing_minutes(emp,hour))
                buckets[role][hour]+=overlap*quality//100
            self.e.named_capacity[b.id][emp.id]=sum(buckets[role])-before_minutes
            self.e.named_initial[b.id][emp.id]=self.e.named_capacity[b.id][emp.id]
            if role in ('manager','property_manager') and sum(buckets[role])>before_minutes:working_managers+=1
            emp.worked_days+=1
            if emp.worked_days>=5 and skill not in person.demonstrated:
                person.demonstrated.append(skill);self.record(person.id,f"Demonstrated {skill} through work in this role.")
        manager_factor=100 if working_managers else 75
        if len(staff)>max(1,working_managers)*8: manager_factor=max(55,manager_factor-(len(staff)-working_managers*8)*3)
        if workforce:
            from .shared_services import SharedServices
            SharedServices(self.e).incoming(b,today,buckets)
        return buckets,manager_factor

    def invoice(self,b:Business,amount:int,stream:str,source:str,delay:int=14) -> None:
        if not amount:return
        self.e.post(b.id,source,f"Earned {stream.replace('_',' ')}",{"asset:receivable":amount,f"income:{stream}":-amount})
        b.receivables.append(dict(id=source,amount=amount,due=(date.fromisoformat(self.w.date)+timedelta(days=delay)).isoformat()))

    def operate(self,b:Business,today:date) -> bool:
        stop=False
        from .customer_collections import CustomerCollections
        CustomerCollections(self.e).collect(b)
        from .restaurant import Restaurant,active as restaurant_active,settings as restaurant_settings
        dining_model=Restaurant(self.e) if restaurant_active(self.w,b) else None
        if dining_model:dining_model.begin_day(b,today)
        buckets,management=self.work(b,today)
        from .property_operations import PropertyOperations
        PropertyOperations(self.e).deliver(self,b,buckets)
        from .property_services import PropertyServices
        PropertyServices(self.e).deliver_home_office(self,b,buckets)
        from .service_office import ServiceOffice
        ServiceOffice(self.e).deliver(self,b,buckets)
        from .service_products import ServiceProducts
        ServiceProducts(self.e).operate(b,buckets)
        from .industry_operations import IndustryOperations
        IndustryOperations(self.e).before(b,buckets)
        from .specialists import apply
        specialists=apply(self,b,buckets)
        if b.industry in ('trades','construction'):
            target='tradesperson' if b.industry=='trades' else 'builder'
            for role in ('electrician','plumber','hvac_technician'):
                for hour,value in enumerate(buckets.get(role,[])):buckets[target][hour]+=value
                buckets[role]=[0]*24
        minutes={role:sum(values) for role,values in buckets.items()}
        from .revenue_kits import RevenueKits,state as kit_state,active as kit_active
        kit_system=RevenueKits(self.e)
        open_day=today.weekday()<5 and b.status in ("operating","independent") and not (b.disrupted_until and b.disrupted_until>=self.w.date)
        if dining_model:
            open_day=today.weekday() in restaurant_settings(self.w,b)['days'] and b.status in ('operating','independent') and not (b.disrupted_until and b.disrupted_until>=self.w.date)
        operations={"output":0,"unit":"units","demand":0,"bottleneck":"Closed today; salaries and holding costs still accrue.","streams":{}}
        def revenue(amount,stream):
            if amount:self.e.post(b.id,f"{stream}:{b.id}:{self.w.date}",stream.replace('_',' ').title(),{"asset:cash":amount,f"income:{stream}":-amount})
        if kit_state(self.w,b):
            kit_system.overhead(b)
            if b.industry=='gas_station':kit_system.gas(self,b,buckets,management,open_day)
        if kit_state(self.w,b) and b.industry in ('engineering','factory'):
            operations.update(kit_system.projects(self,b,buckets,management,open_day))
        elif b.industry in SALES:
            if b.auto_restock and open_day and (not kit_state(self.w,b) or kit_active(self.w,b,'fuel')):
                wanted=max(0,ServiceProducts(self.e).stock_target(b)-b.inventory_units)
                # Keep a payroll reserve rather than converting every dollar into stock.
                reserve=sum(e.salary for e in self.staff(b.id))//4
                units=min(wanted,max(0,self.w.cash(b.id)-reserve)//b.unit_cost)
                from .leadership import Leadership
                units=Leadership(self.e).stock_limit(b,units)
                if units:
                    self.e.post(b.id,f"restock:{b.id}:{self.w.date}","Automatic stock purchase",{"asset:cash":-units*b.unit_cost,"asset:inventory":units*b.unit_cost})
                    IndustryOperations(self.e).add_stock(b,units)
                    b.inventory_units+=units
            capacity=sales_capacity(b.industry,buckets)
            capacity=capacity*management*b.capacity_percent//10000
            from .distress import Distress
            demand=b.daily_demand*self.roll(92,108)//100*max(25,200-b.price_percent)//100*Distress(self.e).capacity(b)//100 if open_day else 0
            demand=demand*IndustryOperations(self.e).demand_factor(b)//100
            if self.w.systems:
                from .economy import Economy
                demand=demand*Economy(self.e).demand_factor(b)//100
            if any(f['operator']==b.id and f['status']=='active' for f in self.w.systems.get('franchises',[])):demand=demand*105//100
            demand=demand*(100+specialists['marketing_percent'])//100
            if kit_state(self.w,b) and not kit_active(self.w,b,'fuel'):demand=0
            quantity=min(capacity,demand,b.inventory_units)
            if dining_model:
                dining=dining_model.sales(b,buckets,open_day,specialists)
                quantity=dining['output'];demand=dining['demand'];capacity=dining['capacity']
            value=quantity*b.unit_price*b.price_percent//100*IndustryOperations(self.e).sale_factor(b,quantity)//100
            revenue(value,SALES[b.industry][4])
            if self.w.systems and value:
                from .domain import GAME_RULES
                tax=value*GAME_RULES['tax']['sales_percent']//100
                self.e.post(b.id,f'sales-tax:{b.id}:{self.w.date}','Sales tax collected from customers',{'asset:cash':tax,'liability:sales_tax':-tax})
            if quantity:self.e.post(b.id,f"cost_of_sales:{b.id}:{self.w.date}","Inventory sold or ingredients consumed",{"asset:inventory":-quantity*b.unit_cost,"expense:cost_of_sales":quantity*b.unit_cost})
            rebate=quantity*b.unit_cost*specialists['purchasing_percent']//400
            if rebate:self.e.post(b.id,f"supplier-rebate:{b.id}:{self.w.date}","Supplier volume rebate on goods sold",{"asset:cash":rebate,"expense:cost_of_sales":-rebate})
            specialists['supplier_savings']=rebate
            IndustryOperations(self.e).remove_stock(b,quantity)
            b.inventory_units-=quantity
            if b.industry in ("restaurant","grocery") and b.inventory_units:
                waste=max(1,b.inventory_units//100)
                self.e.post(b.id,f"waste:{b.id}:{self.w.date}","Perishable ingredient waste",{"asset:inventory":-waste*b.unit_cost,"expense:waste":waste*b.unit_cost})
                IndustryOperations(self.e).remove_stock(b,waste)
                b.inventory_units-=waste
            operations.update(output=quantity,demand=demand,capacity=capacity,unit=SALES[b.industry][5],bottleneck=("Closed today." if not open_day else "Inventory" if quantity<min(capacity,demand) else "Staff coverage / skill" if capacity<demand else "Customer demand"))
            if dining_model:
                operations.update(dining)
                if open_day:dining_model.feedback(b,operations)
            if kit_state(self.w,b):kit_state(self.w,b)['last']['fuel']=dict(output=quantity,revenue=value,capacity=capacity,demand=demand,stock=b.inventory_units,spoiled=0)
        elif b.industry in ('cleaning','landscaping','security'):
            from .property_services import PropertyServices
            operations.update(PropertyServices(self.e).operate(self,b,buckets,management,open_day))
        elif b.industry=='factory':
            operations.update(IndustryOperations(self.e).factory(self,b,minutes,open_day))
        elif b.industry in PROJECTS:
            available=project_capacity(b.industry,minutes)*management*min(120,b.capacity_percent)//10000 if open_day else 0
            from .distress import Distress
            available=available*Distress(self.e).capacity(b)//100
            from .project_portfolio import autofill, project_minutes, remaining, deliver
            autofill(self,b,project_minutes(b,available))
            qualified_capacity=available
            retainer_minutes=min(60,available) if b.retainer else 0;available-=retainer_minutes
            if retainer_minutes:
                earned=weekday_share(b.retainer,today)*retainer_minutes//60
                self.invoice(b,earned,"support_retainer",f"retainer:{b.id}:{self.w.date}")
            advisory=min(240,available//3) if b.hourly_rate else 0;available-=advisory
            self.invoice(b,advisory*b.hourly_rate//60,"hourly_consulting",f"hourly:{b.id}:{self.w.date}")
            progress=min(available,remaining(b))
            if progress and b.material_hourly_cost:
                credit_limit=min(1000000,max(100000,b.equipment//10))
                outstanding=max(0,-self.w.accounts[b.id].get('liability:payable',0))
                budget=self.w.cash(b.id)+max(0,credit_limit-outstanding)
                funded=budget*60//b.material_hourly_cost
                if progress>funded:
                    progress=max(0,funded)
                    self.e.event('Project supplies blocked',b.name+': supplier credit is exhausted. Add cash or collect invoices to obtain further materials.',True,financial_amount=b.material_hourly_cost)
            project_earned_today=0
            if progress:
                materials=progress*b.material_hourly_cost//60
                specialists['supplier_savings']=materials*specialists['purchasing_percent']//400
                materials-=specialists['supplier_savings']
                if materials:self.e.post(b.id,f"project_materials:{b.id}:{self.w.date}","Project materials consumed",{"expense:project_materials":materials,"liability:payable":-materials})
                progress,project_earned_today,project_allocations=deliver(self,b,progress)
            else:project_allocations=[]
            operations.update(output=advisory+progress+retainer_minutes,unit="qualified minutes",demand=remaining(b),project_allocations=project_allocations,qualified_capacity=qualified_capacity,project_minutes=progress,project_fee_earned=project_earned_today,consulting_minutes=advisory,retainer_minutes=retainer_minutes,bottleneck="Qualified staffed hours" if b.project_active else "Next job scheduled automatically" if b.auto_projects else "Accept another fixed-fee project")
        elif b.industry=="bank":
            from .banking import operate_bank
            operations.update(operate_bank(self,b,today,minutes,management,open_day))
            stop=operations['withdrawals_unpaid']>0
        elif b.industry=='logistics':
            from .logistics import freight_capacity
            capacity=freight_capacity(b,buckets,management) if open_day else 0
            operations.update(output=0,unit='deliveries',demand=b.daily_demand,freight_capacity=capacity,internal_deliveries=0,external_deliveries=0,bottleneck='Drivers, dispatchers and fleet capacity' if open_day else 'Closed today')
        elif b.industry=='self_storage':
            from .storage import operate_storage
            operations.update(operate_storage(self,b,today,minutes,open_day))
        elif b.industry=="property_management":
            coverage=min(b.external_units,minutes["property_manager"]//15) if open_day else 0
            # Contracts are serviced on weekdays; monthly fees are spread across actual weekdays.
            fees=weekday_share(coverage*b.management_fee,today) if open_day else 0
            self.invoice(b,fees,"management_fees",f"management:{b.id}:{self.w.date}",7)
            billable=min(240,minutes["maintenance"]) if open_day else 0
            revenue(billable*b.hourly_rate//60,"maintenance_services")
            operations.update(output=coverage,unit="client properties serviced",demand=b.external_units,bottleneck="Property-manager capacity" if coverage<b.external_units else "Contracted client portfolio")
        elif b.industry=="office":
            departments=[d for d in self.w.systems.get('departments',{}).values() if d['provider']==b.id]
            used=sum(d.get('last_used',0) for d in departments)
            pending=sum(t['remaining'] for t in self.w.systems.get('service_tasks',[]) if t['provider']==b.id and t['status'] in ('queued','working'))
            operations.update(output=used,unit='shared-service staff minutes',demand=pending,
                bottleneck='Queued work competes for qualified staff and geographic coverage' if pending else 'No queued service work; payroll and office costs still accrue')
        elif b.industry=="rental":
            rentals=[p for p in self.w.properties if p.owner==b.id and p.occupancy_use!="operating"]
            if open_day:
                shortage=max(0,len(rentals)*30-minutes["maintenance"])
                if shortage:self.e.post(b.id,f"outsource:{b.id}:{self.w.date}","Outsourced maintenance coverage",{"expense:outsourced_maintenance":shortage*100,"liability:payable":-shortage*100})
            operations.update(output=sum(p.status=="rented" for p in rentals),unit="occupied properties",demand=len(rentals),bottleneck="Owned leases and occupancy; no invented rent from staff headcount")
        if open_day and b.industry in SALES:IndustryOperations(self.e).customer_feedback(b,operations)
        overhead=daily_share(b.monthly_overhead,today)
        specialists['overhead_savings']=overhead*specialists['purchasing_percent']//100
        overhead-=specialists['overhead_savings']
        from .premises import external_rent
        external_rent(self.e,b,today)
        if overhead:self.e.post(b.id,f"overhead:{b.id}:{self.w.date}","Operating costs",{"expense:operations":overhead,"liability:payable":-overhead})
        if (today.weekday()==4 or b.payroll_overdue) and b.industry!='logistics':
            owed=-self.w.accounts[b.id].get("liability:payroll",0)
            paid=min(owed,self.w.cash(b.id))
            if paid:self.e.post(b.id,f"payday:{b.id}:{self.w.date}","Payday: earned wages and benefits",{"asset:cash":-paid,"liability:payroll":paid})
            b.payroll_overdue=paid<owed
            if b.payroll_overdue:
                self.e.event("Payroll needs funding",f"{b.name} could not pay its full payroll. Add capital; unpaid wages reduce morale.",True,financial_amount=owed-paid);stop=True
        day_postings=[p for p in self.e.postings if p["entity"]==b.id]
        streams={};expenses=0
        for posting in day_postings:
            for account,value in posting["lines"].items():
                if account.startswith("income:"):streams[account[7:]]=streams.get(account[7:],0)-value
                if account.startswith("expense:"):expenses+=value
        operations.update(specialists=specialists,date=self.w.date,streams=streams,revenue=sum(streams.values()),expenses=expenses,profit=sum(streams.values())-expenses,management=management)
        b.last_day=operations;b.history.append(operations);b.history=b.history[-90:]
        return stop

    def end_day(self,today:date) -> bool:
        stop=False
        for b in sorted(self.w.businesses,key=lambda b:b.id):
            if (b.owner or b.outside_owner) and b.status!='closed':
                from .campaign import Campaign
                before=len(self.e.pause_reasons);start=len(self.e.events)
                result=self.operate(b,today)
                if Campaign(self.e).controlled(b.id):stop=result or stop
                else:
                    del self.e.pause_reasons[before:]
                    for event in self.e.events[start:]:event['important']=False
        if today.day==1:
            available=sum(p.candidate for p in self.w.people)
            for _ in range(max(0,min(3,18-available))):
                roles=list(ROLE_SKILLS);self.make_person(roles[self.roll(0,len(roles)-1)],candidate=True)
            if sum(b.status=="market" for b in self.w.businesses)<8:
                self.add_business((self.w.next_business_id-1)%len(BUSINESS_CONTENT["catalog"]))
        return stop

    def validate(self) -> None:
        for items in (self.w.businesses,self.w.people,self.w.positions,self.w.employments):
            if len({item.id for item in items})!=len(items):raise RuleError("Duplicate business/workforce identity.")
        for b in self.w.businesses:
            if b.industry=='logistics' and b.fleet_vehicles<1:raise RuleError('A logistics company needs a fleet.')
            if b.industry=='self_storage':
                if not 0 <= b.storage_occupied <= b.storage_units or b.storage_units<=0 or b.storage_monthly_rent<=0:
                    raise RuleError('Storage occupancy and unit rents must be valid.')
            if b.owner:
                from .revenue_kits import validate as validate_kits
                validate_kits(self.w,b)
                if b.industry in PROJECTS:
                    from .project_portfolio import validate as validate_projects
                    validate_projects(b,self.w.accounts[b.id])
                if b.owner not in self.w.accounts:raise RuleError("Business owner has no ledger.")
                current=b.id;seen=set()
                while current not in ("personal", None):
                    if current in seen:raise RuleError("Ownership cycle rejected.")
                    seen.add(current);current=self.parent(current)
                accounts=self.w.accounts[b.id]
                if b.industry=='bank':
                    from .banking import validate_bank
                    validate_bank(b,accounts)
                if accounts.get("asset:inventory",0)!=b.inventory_units*b.unit_cost:raise RuleError("Inventory does not reconcile.")
                if accounts.get("asset:receivable",0)!=sum(i["amount"] for i in b.receivables):raise RuleError("Customer receivables do not reconcile.")
                if self.w.accounts[b.owner].get(investment_account(b.id),0)!=-accounts.get("equity:capital",0):raise RuleError("Ownership investment does not reconcile.")
        occupied=set()
        for emp in self.w.employments:
            pos=self.position(emp.position_id);self.person(emp.person_id)
            if emp.employer!=pos.business_id:raise RuleError("Employment is assigned to another employer's position.")
            if emp.status in ("active","joining","seller"):
                if not position_open(self.w,pos):raise RuleError("An archived position cannot have an employee.")
                if emp.position_id in occupied:raise RuleError("A position cannot have two incumbents.")
                occupied.add(emp.position_id);self.check_schedule(emp,replacing=emp.id)
        for pos in self.w.positions:
            if pos.reports_to and not position_open(self.w,self.position(pos.reports_to)):
                raise RuleError("Reporting lines cannot point to a removed vacancy.")
            from .employee_reporting import parent_position
            seen={pos.id};parent=parent_position(self.w,pos)
            while parent:
                if parent in seen:raise RuleError("Reporting cycle rejected.")
                seen.add(parent);other=self.position(parent)
                parent=parent_position(self.w,other)
