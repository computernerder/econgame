"""Pure daily simulation. Money is integer cents; UI and storage stay outside."""
from __future__ import annotations

import calendar
import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from .business_models import Business, Person, Position, Employment


class RuleError(ValueError):
    """An action the player can correct without losing state."""


CONTENT = json.loads((Path(__file__).parent / "content" / "properties.json").read_text(encoding="utf-8"))
V1_CONTENT_VERSION = hashlib.sha256(json.dumps(CONTENT, sort_keys=True).encode()).hexdigest()
BUSINESS_CONTENT = json.loads((Path(__file__).parent / "content" / "businesses.json").read_text(encoding="utf-8"))
V2_CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT], sort_keys=True).encode()).hexdigest()
GAME_RULES = json.loads((Path(__file__).parent / "content" / "game_rules.json").read_text(encoding="utf-8-sig"))
LEGACY_CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT, GAME_RULES], sort_keys=True).encode()).hexdigest()
INDUSTRY_CONTENT = json.loads((Path(__file__).parent / "content" / "industries.json").read_text(encoding="utf-8"))
BUSINESS_CONTENT['catalog'].extend(INDUSTRY_CONTENT['catalog'])
GAME_RULES['startup'].update(INDUSTRY_CONTENT['startup'])
INDUSTRIES_CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT, GAME_RULES], sort_keys=True).encode()).hexdigest()
PROPERTY_CONTENT = json.loads((Path(__file__).parent / "content" / "real_estate.json").read_text(encoding="utf-8"))
CONTENT['properties'].extend(PROPERTY_CONTENT['properties'])
PROPERTY_CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT, GAME_RULES], sort_keys=True).encode()).hexdigest()
EXPANSION_CONTENT = json.loads((Path(__file__).parent / 'content' / 'manufacturing_retail.json').read_text(encoding='utf-8'))
BUSINESS_CONTENT['catalog'].extend(EXPANSION_CONTENT['catalog'])
GAME_RULES['startup'].update(EXPANSION_CONTENT['startup'])
EXPANSION_CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT, GAME_RULES], sort_keys=True).encode()).hexdigest()
STORAGE_CONTENT = json.loads((Path(__file__).parent / 'content' / 'storage.json').read_text(encoding='utf-8'))
BUSINESS_CONTENT['catalog'].extend(STORAGE_CONTENT['catalog'])
GAME_RULES['startup'].update(STORAGE_CONTENT['startup'])
STORAGE_CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT, GAME_RULES], sort_keys=True).encode()).hexdigest()
LOGISTICS_CONTENT = json.loads((Path(__file__).parent / 'content' / 'logistics.json').read_text(encoding='utf-8'))
BUSINESS_CONTENT['catalog'].extend(LOGISTICS_CONTENT['catalog'])
GAME_RULES['startup'].update(LOGISTICS_CONTENT['startup'])
CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT, GAME_RULES], sort_keys=True).encode()).hexdigest()
PREVIOUS_CONTENT_VERSION = CONTENT_VERSION
PROPERTY_SERVICES_CONTENT = json.loads((Path(__file__).parent / 'content' / 'property_services.json').read_text(encoding='utf-8'))
BUSINESS_CONTENT['catalog'].extend(PROPERTY_SERVICES_CONTENT['catalog'])
GAME_RULES['startup'].update(PROPERTY_SERVICES_CONTENT['startup'])
CONTENT_VERSION = hashlib.sha256(json.dumps([CONTENT, BUSINESS_CONTENT, GAME_RULES], sort_keys=True).encode()).hexdigest()
# Geography has its own migration marker; preserve historical catalog fingerprints.
from .vermont import configure_catalogs
configure_catalogs(CONTENT, BUSINESS_CONTENT, GAME_RULES)
SIMULATION_VERSION = 3


@dataclass
class Property:
    id: str
    name: str
    kind: str
    region: str
    description: str
    full_value: int
    full_rent: int
    upkeep: int
    condition: int
    asking: int
    owner: str | None = None
    basis: int = 0
    status: str = "market"
    due: str | None = None
    target_condition: int | None = None
    rent: int = 0
    lease_end: str | None = None
    tenant: str | None = None
    offer: int = 0
    sale_net: int = 0
    bought_on: str | None = None
    reserved_for: str | None = None
    acquisition_basis: int = 0
    occupancy_use: str = "rental"
    occupant: str | None = None
    usable_area: int = 0
    spaces: list[dict] = field(default_factory=list)

    category: str = ""
    specialization: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.category:
            kind = self.kind.lower()
            self.category = ('industrial' if any(word in kind for word in ('warehouse','workshop','factory','industrial')) else
                             'commercial' if any(word in kind for word in ('commercial','office','retail','shop')) else 'residential')
        if self.category not in ('residential','commercial','industrial','office','mixed_use','land'):
            raise RuleError('Unknown property category.')

    @property
    def value(self) -> int:
        return self.full_value * (60 + self.condition * 40 // 100) // 100

    @property
    def suggested_rent(self) -> int:
        return self.full_rent * (60 + self.condition * 40 // 100) // 100


@dataclass
class World:
    date: str = "2026-01-01"
    seed: int = 42
    revision: int = 0
    simulation_version: int = SIMULATION_VERSION
    content_version: str = CONTENT_VERSION
    owner_name: str = "Alex Morgan"
    birth_date: str = "1996-01-15"
    properties: list[Property] = field(default_factory=list)
    accounts: dict[str, dict[str, int]] = field(default_factory=lambda: {"personal": {}, "company": {}})
    events: list[dict] = field(default_factory=list)
    rng_state: Any = None
    next_id: int = 1
    businesses: list[Business] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    employments: list[Employment] = field(default_factory=list)
    business_rng_state: Any = None
    next_business_id: int = 1
    next_person_id: int = 1
    next_position_id: int = 1
    next_employment_id: int = 1
    systems: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> World:
        data = dict(data)
        data["properties"] = [Property(**p) for p in data["properties"]]
        for key, model in (("businesses",Business),("people",Person),("positions",Position),("employments",Employment)):
            data[key] = [model(**item) for item in data.get(key,[])]
        return cls(**data)

    def cash(self, entity: str) -> int:
        return self.accounts[entity].get("asset:cash", 0)


def tuples(value: Any) -> Any:
    return tuple(tuples(v) for v in value) if isinstance(value, (tuple, list)) else value


class Engine:
    def __init__(self, world: World):
        self.world = world
        self.postings: list[dict] = []
        self.events: list[dict] = []
        self.pause_reasons: list[dict] = []
        self.pause_reason_text = ""

    def random_int(self, low: int, high: int) -> int:
        rng = random.Random(self.world.seed)
        if self.world.rng_state is not None:
            rng.setstate(tuples(self.world.rng_state))
        result = rng.randint(low, high)
        self.world.rng_state = rng.getstate()
        return result

    def post(self, entity: str, source: str, memo: str, lines: dict[str, int]) -> None:
        if entity not in self.world.accounts or sum(lines.values()) != 0:
            raise RuleError("The transaction does not balance.")
        if any(type(v) is not int for v in lines.values()):
            raise RuleError("Money must use whole cents.")
        accounts = self.world.accounts[entity]
        if accounts.get("asset:cash", 0) + lines.get("asset:cash", 0) < 0:
            raise RuleError("There is not enough cash in this account. Transfer funds or choose a lower-cost action.")
        from .distress import track
        # Attribute actual cash settlements to their dated property invoices.
        paid=min(max(0,lines.get('liability:payable',0)),max(0,-lines.get('asset:cash',0)))
        for lot in sorted(self.world.systems.get('obligation_lots',{}).get(entity,{}).get('liability:payable',[]),key=lambda r:r['due']):
            amount=min(paid,lot['remaining']);paid-=amount
            if amount and lot['source'].startswith('upkeep:'):
                pid=lot['source'].split(':')[1]
                totals=self.world.systems.setdefault('property_income_totals',{}).setdefault(pid,dict(since=self.world.date,earned=0,collected=0))
                totals['holding_paid']=totals.get('holding_paid',0)+amount
            if not paid:break
        track(self.world,entity,source,lines)
        for account, value in lines.items():
            accounts[account] = accounts.get(account, 0) + value
        self.postings.append(dict(entity=entity, source=source, date=self.world.date, memo=memo, lines=lines))
        if self.world.systems:
            monthly=self.world.systems.setdefault('monthly_financials',{}).setdefault(entity,{}).setdefault(self.world.date[:7],{})
            for key,value in lines.items():
                if key.startswith(('income:','expense:')):monthly[key]=monthly.get(key,0)+value
        business = next((b for b in self.world.businesses if b.id == entity), None)
        if business:
            financial = {k:v for k,v in lines.items() if k.startswith(('income:', 'expense:'))}
            if financial:
                day = business.financial_days.setdefault(self.world.date, {})
                for key, value in financial.items():
                    day[key] = day.get(key, 0) + value
                for old in sorted(business.financial_days)[:-90]:
                    del business.financial_days[old]

    def event(self, title: str, detail: str, important: bool = False, financial_amount: int | None = None, invoice_id: str | None = None, request_id: str | None = None) -> None:
        item = dict(id=self.world.next_id, date=self.world.date, title=title, detail=detail, important=important)
        self.world.next_id += 1
        self.world.events.append(item)
        self.world.events = self.world.events[-80:]
        self.events.append(item)
        if financial_amount is not None:item["financial_amount"]=financial_amount
        if invoice_id is not None:item["invoice_id"]=invoice_id
        if request_id is not None:item["request_id"]=request_id
        if important:
            from .skip_controls import allowed
            self.pause_reasons.append(item)
            item["pause_suppressed"]=not allowed(self.world.systems.get("settings",{}),item)

    def get_property(self, property_id: str) -> Property:
        for prop in self.world.properties:
            if prop.id == property_id:
                return prop
        raise RuleError("That property is no longer available.")

    def owned(self, property_id: str) -> Property:
        prop = self.get_property(property_id)
        from .campaign import Campaign
        if prop.owner is None or prop.status == "sold" or not Campaign(self).controlled(prop.owner):
            raise RuleError("You do not own this property.")
        return prop

    def populate_market(self, count: int, template_index: int | None = None) -> None:
        for _ in range(count):
            template = CONTENT["properties"][(self.world.next_id - 1) % len(CONTENT["properties"])] if template_index is None else CONTENT["properties"][template_index]
            prop = Property(**template, id=f"p{self.world.next_id}", asking=0)
            prop.condition = max(20, min(95, prop.condition + self.random_int(-5, 5)))
            prop.asking = prop.value * self.random_int(90, 96) // 100
            prop.name = f"{100 + self.world.next_id} {prop.name}"
            self.world.properties.append(prop)
            self.world.next_id += 1

    def quote(self, action: str, property_id: str, entity: str = 'personal') -> dict:
        p = self.get_property(property_id)
        if action == "buy":
            from .property_development import brokerage
            fee = brokerage(self.world,p,entity,p.asking,2)
            from .transaction_legal import TransactionLegal
            legal_fee=TransactionLegal(self).closing_fee(p,entity)
            return dict(price=p.asking, fee=fee+legal_fee, legal_fee=legal_fee, total=p.asking+fee+legal_fee)
        if action in ("refresh", "rehabilitate"):
            gain = min(15 if action == "refresh" else 35, 100 - p.condition)
            cost = p.full_value * gain * (14 if action == "refresh" else 18) // 10_000
            days = max(3, gain if action == "refresh" else gain + 7)
            target = p.condition + gain
            value = p.full_value * (60 + target * 40 // 100) // 100
            return dict(total=cost, days=days, target=target, value=value, gain=gain)
        if action == "sell":
            gross = p.value * 98 // 100
            from .property_development import brokerage
            fee = brokerage(self.world,p,p.owner,gross,3)
            return dict(price=gross, fee=fee, total=gross - fee, gain=gross - fee - p.basis)
        raise RuleError("Unknown quote.")

    def action(self, action: str, args: dict, command_id: str) -> str:
        import copy
        from .vermont import remap_locations
        args=copy.deepcopy(args);remap_locations(args)
        from .property_development import owner_busy, RECOVERY
        busy=not getattr(self,'action_depth',0) and owner_busy(self.world) and not getattr(self,'simulating',False) and action not in RECOVERY and not action.startswith('debug_')
        used=self.world.systems.get('owner_decisions',{}).get(self.world.date,0)
        if busy and used>=2:
            raise RuleError('Owner repair work leaves two discretionary decisions per day. Advance one day or outsource the repair in Property workbench. Required approvals and funding remain available.')
        self.action_depth=getattr(self,'action_depth',0)+1
        try:result=self._action(action,args,command_id)
        finally:self.action_depth-=1
        if busy:self.world.systems['owner_decisions']={self.world.date:used+1}
        return result

    def _action(self, action: str, args: dict, command_id: str) -> str:
        w = self.world
        if action in {'restaurant_plan','restaurant_rota','restaurant_expand','restaurant_schedule'}:
            from .restaurant import Restaurant
            return Restaurant(self).action(action,args,command_id)
        if action == 'inbox_decline_offer':
            from .decision_inbox import decline_offer
            return decline_offer(self,args.get('inbox_id',''))
        if action == 'leadership_activity_read':
            from .leadership_activity import mark_reviewed
            return mark_reviewed(w,args.get('cursor'))
        from .developer import Developer, ACTIONS as DEVELOPER_ACTIONS
        if action in DEVELOPER_ACTIONS:
            return Developer(self).action(action, args, command_id)
        if w.systems.get('campaign_outcome',{}).get('status')=='insolvent' and action not in ('new_campaign','settings'):
            raise RuleError('This campaign ended in insolvency. Review the records or start a new campaign.')
        if action == 'routine_management_policy':
            from .routine_management import RoutineManagement
            return RoutineManagement(self).action(args)
        if action == 'recover_invoice':
            from .customer_collections import CustomerCollections
            return CustomerCollections(self).action(args, command_id)
        if action in ('close_operation','settle_obligations','negotiate_terms','write_off_invoice','liquidate_assets'):
            from .distress import Distress
            return Distress(self).action(action,args,command_id)
        if action in ('department_configure','service_request','service_priority','outsource_service','cancel_service'):
            from .service_office import ServiceOffice
            return ServiceOffice(self).action(action,args,command_id)
        if action=='develop_property':
            from .property_development import Development
            return Development(self).action(args,command_id)
        if action=='accept_supplier_contract':
            from .supplier_contracts import SupplierContracts
            return SupplierContracts(self).action(args,command_id)
        if action=='respond_property_request':
            from .property_requests import PropertyRequests
            return PropertyRequests(self).action(args,command_id)
        if action in ('property_service','cancel_property_service'):
            from .property_services import PropertyServices
            return PropertyServices(self).action(action,args,command_id)
        if action in ('inspect_property','flip_budget','property_work','advertise_space','accept_tenant','renew_property_lease','market_property','accept_property_offer','withdraw_property_sale','fund_flip','flip_work','add_flip_reserve','outsource_property_work'):
            from .property_operations import PropertyOperations
            return PropertyOperations(self).action(action,args,command_id)
        if action in ('buy_revenue_kit','revenue_policy','restock_stream'):
            from .revenue_kits import RevenueKits
            return RevenueKits(self).action(action,args,command_id)
        if action=='local_improvement':
            from .industry_operations import IndustryOperations
            return IndustryOperations(self).action(args,command_id)
        if action=='start_location':
            from .operating_locations import OperatingLocations
            return OperatingLocations(self).action(args,command_id)
        if action=='promote_home_office':
            from .leadership_transfer import promote
            return promote(self,args)
        if action=='executive_assign':
            from .executives import Executives
            return Executives(self).action(args)
        if action=='autonomy_policy':
            from .operating_automation import OperatingAutomation
            return OperatingAutomation(self).action(args)
        if action in {'time_off_request','time_off_decide','time_off_cancel','time_off_policy'}:
            from .time_off import TimeOff
            return TimeOff(self).action(action,args,command_id)
        if action=='employee_benefits':
            from .employee_management_views import benefit_action
            return benefit_action(self,args)
        if action == 'authority_contract':
            from .authority import Authority
            return Authority(self).set_contract(args)
        if action in {"specialist_report","negotiate_acquisition"}:
            from .specialists import Specialists
            return Specialists(self).action(action,args)
        if action=="management_policy":
            from .management import Management
            return Management(self).action(args)
        if action in {"leadership_defaults","director_assign","director_remove","director_inheritance","leadership_raise","annual_raise","management_approve","management_defer","management_reopen"}:
            from .leadership import Leadership
            return Leadership(self).action(action,args,command_id)
        if action in {"policy_set","policy_reset","delegation","recruit","reporting","promote","compensation","education","review_employee","special_leave","screen_candidate","renew_license"}:
            from .workforce import Workforce
            return Workforce(self).action(action,args,command_id)
        if action=='transfer_business':
            from .ownership import Ownership
            return Ownership(self).transfer(args,command_id)
        if action in {'start_business','upgrade_business','integration','sell_business','cancel_opening'}:
            from .expansion import Expansion
            return Expansion(self).action(action,args,command_id)
        if action=='due_diligence':
            from .expansion import Expansion
            return Expansion(self).diligence(args,command_id)
        if action in {'settings','succession','sandbox_funds','new_campaign'}:
            from .campaign_options import CampaignOptions
            return CampaignOptions(self).action(action,args,command_id)
        if action in {'create_brand' ,'grant_franchise','join_franchise','franchise_audit','renew_franchise','end_franchise'}:
            from .franchises import Franchises
            return Franchises(self).action(action,args,command_id)
        if action in {'occupy_property','lease_premises','configure_spaces' ,'lease_space','convert_space','self_renovate','release_premises','lease_response','end_lease','write_off_rent'}:
            from .real_estate import RealEstate
            return RealEstate(self).action(action,args,command_id)
        if action in {'civic_project' ,'insurance'}:
            from .economy import Economy
            return Economy(self).action(action,args,command_id)
        if action in {'borrow' ,'repay_loan','restructure_loan','tax_plan','file_taxes'}:
            from .finance_rules import Finance
            return Finance(self).action(action,args,command_id)
        if action in {'service_agreement','assign_staff','share_department_staff','end_assignment','headquarters'}:
            from .shared_services import SharedServices
            return SharedServices(self).action(action,args,command_id)
        if action in ('set_residence','clear_residence'):
            from .personal_residence import action as residence_action
            return residence_action(self,action,args)
        if action == 'decide':
            from .campaign import Campaign
            return Campaign(self).choose(args)
        if action in {"bank_policy","hire_for_role","engineering_policy","acquire_business","fund_business","distribute_profit","business_policy","restock","new_project","create_position","remove_vacancy","hire","employment_terms","train","leave","end_employment"}:
            from .business_rules import BusinessRules
            return BusinessRules(self).action(action,args,command_id)
        if action == "create_holding_company":
            from .holding_company import exists
            if exists(w):raise RuleError("You already have a holding company. Use its account or start another business.")
            name = str(args.get("name", "")).strip()
            if not 2 <= len(name) <= 80:raise RuleError("Use a company name of 2–80 characters.")
            w.systems["holding_company"] = {"name":name,"created":w.date}
            w.accounts.setdefault("company", {})
            self.event("Holding company created", f"{name} is ready. Add capital when you want it to buy property or own businesses.")
            return f"{name} created. No funds were transferred."
        if action in ("invest", "withdraw"):
            from .holding_company import exists
            if not exists(w):raise RuleError("Create a holding company before transferring capital.")
            amount = args.get("amount")
            if type(amount) is not int or amount <= 0:
                raise RuleError("Enter a positive amount in whole cents.")
            if action == "withdraw" and amount > w.accounts["personal"].get("asset:investment", 0):
                raise RuleError("You can only return capital you have invested. Profit distributions arrive with business ownership.")
            direction = 1 if action == "invest" else -1
            self.post("personal", command_id + ":personal", "Company capital transfer", {"asset:cash": -amount * direction, "asset:investment": amount * direction})
            self.post("company", command_id + ":company", "Owner capital transfer", {"asset:cash": amount * direction, "equity:capital": -amount * direction})
            self.event("Capital transferred", "Personal and company funds were moved with matching entries. This is not income.")
            return "Capital transferred."
        if action == "profile":
            name = args.get("name", "").strip()
            if not 1 <= len(name) <= 60:
                raise RuleError("Use an owner name between 1 and 60 characters.")
            w.owner_name = name
            return "Owner name updated."
        p = self.get_property(args.get("property_id", ""))
        if action == "buy":
            entity = args.get("entity", "personal")
            from .campaign import Campaign
            Campaign(self).require(entity)
            if p.status != "market" or p.owner is not None:
                raise RuleError("This property is no longer for sale.")
            from .transaction_legal import TransactionLegal
            TransactionLegal(self).check_purchase(p,entity)
            q = self.quote("buy", p.id,entity)
            self.post(entity, command_id, f"Purchase: {p.name}", {"asset:cash": -q["total"], "asset:property": q["total"]})
            p.owner, p.status, p.basis, p.bought_on = entity, "vacant", q["total"], w.date
            TransactionLegal(self).acquired(p,entity)
            from .property_development import use_representation
            use_representation(w,p,entity,p.asking*2//100,q['fee']-q['legal_fee'])
            self.event("Your portfolio grew", f"Purchased {p.name}. Choose renovations, find a tenant, or arrange a sale.")
            return "Property purchased. It is ready for your next decision."
        p = self.owned(p.id)
        if p.occupancy_use=="personal_residence":raise RuleError("Move out of your personal residence before renting, selling or starting a whole-home renovation. Repairs remain available in Property workbench.")
        if p.category=='land' and action not in ('sell',):raise RuleError('An empty lot must be developed before repairs, improvements or renting.')
        if action=='sell' and p.id in w.systems.get('flip_progress',{}) and w.systems['flip_progress'][p.id]['phase']!='sold':
            raise RuleError('Market this funded flip through the Property workbench so project reserves and conditional closing reconcile.')
        if action in ('sell','refresh','rehabilitate') and any(j['property_id']==p.id and j['status']=='working' for j in w.systems.get('property_work',[])):
            raise RuleError('Complete the committed property work before starting another sale or whole-building renovation.')
        if action in ("refresh", "rehabilitate"):
            if p.status != "vacant" or p.condition >= 100:
                raise RuleError("Renovations need a vacant property with room for improvement.")
            q = self.quote(action, p.id)
            self.post(p.owner, command_id, f"Renovation: {p.name}", {"asset:cash": -q["total"], "asset:property": q["total"]})
            p.basis += q["total"]
            p.status, p.target_condition = "renovating", q["target"]
            p.due = (date.fromisoformat(w.date) + timedelta(days=q["days"])).isoformat()
            self.event("Contractor booked", f"{p.name} will be ready on {p.due}. Holding costs continue during work.")
            return "Renovation purchased. Advance time to complete the work."
        if action == "rent":
            if p.status != "vacant" or p.condition < 40:
                raise RuleError("Renting needs a vacant property with condition of at least 40.")
            p.status = "seeking"
            from .property_services import presentation
            p.rent = p.suggested_rent*presentation(w,p)//100
            p.due = (date.fromisoformat(w.date) + timedelta(days=self.random_int(3, 7))).isoformat()
            self.event("Rental listed", f"{p.name}: tenant search takes 3–7 days. Rent begins at move-in, with a one-year lease.")
            return "Rental listed. Your agent is finding a tenant."
        if action == "sell":
            if any(l['status']=='active' and l.get('property_id')==p.id for l in w.systems.get('loans',[])):raise RuleError('Repay the secured loan before selling its collateral.')
            if p.status != "vacant":
                raise RuleError("Selling currently requires a vacant property. Wait for work or the lease to finish.")
            q = self.quote("sell", p.id)
            from .property_development import use_representation
            use_representation(w,p,p.owner,q['price']*3//100,q['fee'])
            p.offer, p.sale_net, p.status = q["price"], q["total"], "selling"
            p.due = (date.fromisoformat(w.date) + timedelta(days=self.random_int(7, 14))).isoformat()
            self.event("Sale agreed", f"A buyer has committed to {p.name}. Closing is scheduled for {p.due}; holding costs continue until then.")
            return "Sale agreed. Proceeds arrive at closing."
        if action == "cancel_rental":
            if p.status != "seeking":
                raise RuleError("Only a rental still seeking a tenant can be withdrawn.")
            p.status, p.due, p.rent = "vacant", None, 0
            return "Rental listing withdrawn."
        raise RuleError("That action is not available.")

    def advance_day(self) -> bool:
        self.simulating=True
        from .campaign import Campaign
        if self.world.systems.get('campaign_outcome',{}).get('status')=='insolvent':
            raise RuleError('The campaign has ended in insolvency.')
        self.pause_reasons=[]
        w = self.world
        # A pending request for tomorrow must be reviewed before its start date;
        # the coming day's attendance and leave deduction then see the approval.
        from .time_off import TimeOff
        TimeOff(self).review_pending()
        # A formerly blocked routine proposal can now fit current authority.
        # Rechecking here keeps single days, long skips and save replay aligned.
        from .routine_management import RoutineManagement
        RoutineManagement(self).recheck_property_care()
        today = date.fromisoformat(w.date) + timedelta(days=1)
        w.date = today.isoformat()
        from .business_rules import BusinessRules
        business_rules = BusinessRules(self)
        from .executives import Executives
        Executives(self).tick()
        important = business_rules.start_day()
        if w.systems:
            from .workforce import Workforce
            important = Workforce(self).start_day() or important
            from .operating_automation import OperatingAutomation
            OperatingAutomation(self).tick()
            from .expansion import Expansion
            important = Expansion(self).start_day() or important
            from .time_off import TimeOff
            TimeOff(self).tick()
        for p in sorted(w.properties, key=lambda p: p.id):
            if p.owner is None:
                continue
            if p.due and p.due <= w.date:
                if p.status == "renovating":
                    p.condition, p.status = p.target_condition, "vacant"
                    p.target_condition = None
                    self.event("Renovation complete", f"{p.name} is ready. Choose a tenant or put it up for sale.", True)
                    important = True
                elif p.status == "seeking":
                    p.status, p.tenant = "rented", f"Household {self.random_int(100, 999)}"
                    p.lease_end = calendar_target(today, "year").isoformat()
                    self.event("Tenant moved in", f"{p.name} now earns rental income. Lease ends {p.lease_end}.", True)
                    important = True
                elif p.status == "selling":
                    fee = p.offer - p.sale_net
                    self.post(p.owner, f"sale:{p.id}:{w.date}", f"Sale completed: {p.name}", {"asset:cash": p.sale_net, "expense:selling": fee, "asset:property": -p.basis, "income:property_gain": -(p.offer - p.basis)})
                    p.status, p.owner, p.basis = "sold", None, 0
                    self.event("Sale completed", f"{p.name} sold. Net proceeds are now available in the seller's account.", True, financial_amount=p.sale_net)
                    important = True
                p.due = None
            if p.owner is None:
                continue
            if p.status == "rented" and p.lease_end <= w.date:
                p.status, p.tenant, p.lease_end, p.rent = "vacant", None, None, 0
                self.event("Lease ended", f"{p.name} is vacant. Relet, renovate, or sell it.", True)
                important = True
            if p.status == "rented":
                rent = daily_share(p.rent, today)
                from .property_operations import rent_factor
                rent=rent*rent_factor(w,p)//100
                self.post(p.owner, f"rent:{p.id}:{w.date}", f"Rent: {p.name}", {"asset:cash": rent, "income:rent": -rent})
                totals=w.systems.setdefault('property_income_totals',{}).setdefault(p.id,dict(since=w.date,earned=0,collected=0))
                totals['earned']+=rent;totals['collected']+=rent
            cost = daily_share(p.upkeep, today)
            progress=w.systems.get('flip_progress',{}).get(p.id)
            if progress and progress['phase']!='sold':
                release=min(cost,progress.get('holding_remaining',0),progress['reserve'])
                if release:
                    self.post(p.owner,'flip-holding:'+p.id+':'+w.date,'Release approved holding reserve',{'asset:flip_reserve':-release,'asset:cash':release})
                    progress['reserve']-=release;progress['holding_remaining']-=release
            property_tax=min(cost,daily_share(p.basis*GAME_RULES['tax']['property_basis_points']//120000,today)) if w.systems else 0
            self.post(p.owner, f"upkeep:{p.id}:{w.date}", f"Holding costs: {p.name}", {"expense:holding": cost-property_tax, "expense:property_tax":property_tax,"liability:payable": -cost})
            w.systems.setdefault('property_cost_totals',{}).setdefault(p.id,dict(holding=0,interest=0,repairs=0))['holding']+=cost
        if w.systems:
            from .real_estate import RealEstate
            important = RealEstate(self).tick(today) or important
        important = business_rules.end_day(today) or important
        from .service_office import ServiceOffice
        ServiceOffice(self).tick()
        from .property_operations import PropertyOperations
        PropertyOperations(self).tick()
        from .property_development import Development
        Development(self).tick()
        from .transaction_legal import TransactionLegal
        TransactionLegal(self).tick()
        from .property_services import PropertyServices
        PropertyServices(self).tick()
        from .property_requests import PropertyRequests
        PropertyRequests(self).tick()
        OperatingAutomation(self).review_new_requests()
        if w.systems:
            important = Workforce(self).after_day() or important
            from .shared_services import SharedServices
            SharedServices(self).settle(today)
            from .logistics import settle_transport
            important = settle_transport(business_rules,today) or important
            from .finance_rules import Finance
            from .franchises import Franchises
            Franchises(self).tick(today)
            important = Finance(self).end_day(today) or important
            from .economy import Economy
            important = Economy(self).tick(today) or important
            from .campaign_options import CampaignOptions
            important = CampaignOptions(self).tick(today) or important
        for entity in w.accounts:
            owed = -w.accounts[entity].get("liability:payable", 0)
            paid = min(owed, w.cash(entity))
            if paid:
                self.post(entity, f"settlement:{entity}:{w.date}", "Settle property holding costs", {"asset:cash": -paid, "liability:payable": paid})
            if owed > paid and Campaign(self).controlled(entity):
                self.event("Funds needed", f"The {entity} account has unpaid holding costs. Add funds or sell an asset; review the outstanding balance.", True, financial_amount=owed-paid)
                important = True
        if today.day == 1:
            available = [p for p in w.properties if p.status == "market" and p.category!='land']
            for p in available[:-10]:
                p.status = "expired"
            self.populate_market(2)
            self.event("New properties available", "Two new listings have arrived on the property market.")
        if (today.month, today.day) == (date.fromisoformat(w.birth_date).month, date.fromisoformat(w.birth_date).day):
            self.event("Another year of experience", "Your owner has aged a year. Aging does not end your campaign.")
        from .leadership import Leadership
        from .routine_management import RoutineManagement
        RoutineManagement(self).tick()
        handled=Leadership(self).resolve_decisions()
        from .operating_locations import OperatingLocations
        OperatingLocations(self).settle()
        from .distress import Distress
        Distress(self).tick()
        from .authority import Authority
        Authority(self).guardrails()
        from .skip_controls import should_pause
        self.simulating=False
        return should_pause(self,important and not handled)

    def validate(self) -> None:
        w = self.world
        from .distress import Distress
        Distress(self).validate()
        from .extension_validation import validate_extensions
        validate_extensions(w)
        from .personal_residence import validate as validate_residence
        validate_residence(w)
        if len({p.id for p in w.properties}) != len(w.properties):
            raise RuleError("Duplicate property identity.")
        for entity, accounts in w.accounts.items():
            if sum(accounts.values()) != 0 or w.cash(entity) < 0:
                raise RuleError("Account balances failed validation.")
            basis = sum(p.basis for p in w.properties if p.owner == entity)
            if basis != accounts.get("asset:property", 0):
                raise RuleError("Property assets do not reconcile.")
        if w.accounts["personal"].get("asset:investment", 0) != -w.accounts["company"].get("equity:capital", 0):
            raise RuleError("Company capital does not reconcile.")
        from .business_rules import BusinessRules
        BusinessRules(self).validate()
        from .campaign import Campaign
        Campaign(self).validate()
        from .shared_services import SharedServices
        SharedServices(self).validate()
        from .finance_rules import Finance
        Finance(self).validate()
        from .real_estate import RealEstate
        RealEstate(self).validate()


def daily_share(monthly: int, today: date) -> int:
    days = calendar.monthrange(today.year, today.month)[1]
    return monthly // days + (1 if today.day <= monthly % days else 0)


def calendar_target(today: date, period: str) -> date:
    if period in ("day", "week"):
        return today + timedelta(days=1 if period == "day" else 7)
    if period not in ("month", "quarter", "year"):
        raise RuleError("Choose day, week, month, quarter, year, or a future date.")
    months = {"month": 1, "quarter": 3, "year": 12}[period]
    total = today.year * 12 + today.month - 1 + months
    year, month = total // 12, total % 12 + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def new_game(seed: int = 42) -> Engine:
    engine = Engine(World(seed=seed))
    engine.post("personal", "opening", "Starting personal capital", {"asset:cash": 35_000_000, "equity:capital": -35_000_000})
    engine.populate_market(len(CONTENT["properties"]))
    engine.event("Your first chapter", "Start with $350,000. Buy a property to renovate, flip, or rent. Personal ownership is a complete path; a company is optional.")
    from .business_rules import BusinessRules
    BusinessRules(engine).initialize()
    from .campaign import Campaign
    Campaign(engine).initialize()
    engine.world.systems.update(version=5,operations_version=11,service_projects_version=12,commercial_contracts_version=13,property_services_version=14)
    engine.world.systems['employee_management_version']=21
    engine.world.systems.update(geography_version=24,setting='Vermont')
    from .property_operations import PropertyOperations
    PropertyOperations(engine).ensure_market_types()
    from .property_development import Development
    Development(engine).ensure()
    from .transaction_legal import TransactionLegal
    TransactionLegal(engine).initialize()
    engine.validate()
    return engine
