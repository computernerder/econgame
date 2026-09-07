"""Persistent companies, people, positions and employment contracts."""
from dataclasses import dataclass, field


@dataclass
class Business:
    id: str
    name: str
    industry: str
    region: str
    description: str
    asking: int
    cash_at_sale: int
    equipment: int
    inventory_units: int = 0
    unit_cost: int = 0
    unit_price: int = 0
    daily_demand: int = 0
    monthly_overhead: int = 0
    monthly_lease: int = 0
    owner: str | None = None
    status: str = "market"
    acquired_on: str | None = None
    closing_on: str | None = None
    reserved_by: str | None = None
    escrow: int = 0
    benefits: str = "standard"
    price_percent: int = 100
    auto_restock: bool = True
    external_units: int = 0
    management_fee: int = 0
    hourly_rate: int = 0
    retainer: int = 0
    contract_fee: int = 0
    contract_minutes: int = 0
    project_number: int = 1
    project_progress: int = 0
    project_earned: int = 0
    project_active: bool = False
    auto_projects: bool = True
    contract_base_fee: int = 0
    contract_base_minutes: int = 0
    project_history: list[dict] = field(default_factory=list)
    parallel_projects: list[dict] = field(default_factory=list)
    concurrent_project_limit: int = 3
    project_planning_days: int = 20
    material_hourly_cost: int = 0
    fleet_vehicles: int = 0
    storage_units: int = 0
    storage_occupied: int = 0
    storage_monthly_rent: int = 0
    bank_loans: list[dict] = field(default_factory=list)
    next_loan_id: int = 1
    auto_lending: bool = True
    loan_rate_bps: int = 1000
    deposit_rate_bps: int = 200
    bank_reserve_percent: int = 25
    receivables: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    financial_days: dict[str, dict[str, int]] = field(default_factory=dict)
    last_day: dict = field(default_factory=dict)
    payroll_overdue: bool = False
    culture: int = 70
    reputation: int = 60
    capacity_percent: int = 100
    opening_on: str | None = None
    outside_owner: str | None = None
    market_parent: str | None = None
    insurance: dict = field(default_factory=dict)
    disrupted_until: str | None = None
    authority: dict = field(default_factory=dict)
    integration: dict = field(default_factory=dict)


@dataclass
class Person:
    id: str
    name: str
    birth_date: str
    qualifications: list[str]
    skills: dict[str, int]
    demonstrated: list[str]
    ambition: str
    experience: int
    candidate: bool = False
    morale: int = 72
    engagement: int = 72
    burnout: int = 10
    training_until: str | None = None
    training_skill: str | None = None
    history: list[dict] = field(default_factory=list)
    loyalty: int = 65
    trust: int = 70
    personality: str = "cooperative"
    home_region: str = "Rutland County"
    labor_state: str = "employed"
    notice_on: str | None = None
    education: dict = field(default_factory=dict)
    relationships: dict = field(default_factory=dict)
    observations: list[dict] = field(default_factory=list)
    licenses: dict = field(default_factory=dict)


@dataclass
class Position:
    id: str
    business_id: str
    role: str
    reports_to: str | None = None
    required_license: str | None = None


@dataclass
class Employment:
    id: str
    person_id: str
    position_id: str
    employer: str
    salary: int
    weekly_hours: int
    start_date: str
    days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    shift_start: int = 8
    status: str = "active"
    end_date: str | None = None
    leave_until: str | None = None
    leave_balance: int = 20
    worked_days: int = 0
    compensation: dict = field(default_factory=dict)
    sick_balance: int = 8
    floating_balance: int = 2
    last_pay_review: str | None = None
    probation_until: str | None = None
    absence_until: str | None = None
    supervisor_id: str | None = None
    enrollment: dict = field(default_factory=dict)
    policy_overrides: dict = field(default_factory=dict)


ROLE_SKILLS = {"manager":"leadership", "cashier":"retail", "stocker":"logistics", "chef":"cooking", "server":"service", "engineer":"engineering", "technician":"engineering", "property_manager":"property", "maintenance":"maintenance"}
ROLE_PAY = {"manager":340000,"cashier":260000,"stocker":270000,"chef":320000,"server":250000,"engineer":520000,"technician":380000,"property_manager":320000,"maintenance":300000}
INDUSTRY_ROLES = {"retail":["manager","cashier","stocker"],"restaurant":["manager","chef","server"],"engineering":["manager","engineer","technician"],"property_management":["manager","property_manager","maintenance"],"rental":["manager","property_manager","maintenance"]}
BENEFITS = {"lean":0,"standard":12500,"supportive":30000,"premium":50000}
INDUSTRY_NAMES = {"retail":"Retail", "restaurant":"Restaurant", "engineering":"Engineering", "property_management":"Property management", "rental":"Real estate rentals"}

OPENING_ROLES = {'retail':{'manager','cashier','stocker'},'restaurant':{'manager','chef','server'},'engineering':{'manager','engineer'},'property_management':{'property_manager'},'rental':set(),'office':{'manager'}}
ROLE_SKILLS.update({'prep_cook':'cooking','dishwasher':'service','host':'service'})
ROLE_PAY.update({'prep_cook':270000,'dishwasher':230000,'host':250000})
INDUSTRY_ROLES['restaurant'].extend(['prep_cook','dishwasher','host'])


ROLE_SKILLS.update({'tradesperson':'maintenance','apprentice':'maintenance','builder':'maintenance','laborer':'logistics','attendant':'service','salesperson':'retail','mechanic':'maintenance','teller':'service','loan_officer':'finance'})
ROLE_PAY.update({'tradesperson':420000,'apprentice':270000,'builder':440000,'laborer':290000,'attendant':280000,'salesperson':360000,'mechanic':390000,'teller':310000,'loan_officer':460000})
INDUSTRY_ROLES.update({'trades':['manager','tradesperson','apprentice'],'construction':['manager','builder','laborer'],'gas_station':['manager','cashier','attendant'],'grocery':['manager','cashier','stocker'],'bank':['manager','teller','loan_officer'],'car_dealership':['manager','salesperson','mechanic']})
INDUSTRY_NAMES.update({'trades':'Skilled trades','construction':'Construction','gas_station':'Gas stations','grocery':'Grocery stores','bank':'Banks','car_dealership':'Car dealerships'})
OPENING_ROLES.update({'trades':{'manager','tradesperson'},'construction':{'manager','builder'},'gas_station':{'manager','cashier','attendant'},'grocery':{'manager','cashier','stocker'},'bank':{'manager','teller','loan_officer'},'car_dealership':{'manager','salesperson','mechanic'}})

ROLE_SKILLS.update({'machine_operator':'maintenance','production_worker':'logistics'})
ROLE_PAY.update({'machine_operator':380000,'production_worker':290000})
INDUSTRY_ROLES.update({'factory':['manager','machine_operator','production_worker'],'boutique':['manager','salesperson','stocker']})
INDUSTRY_NAMES.update({'factory':'Factories','boutique':'Boutiques'})
OPENING_ROLES.update({'factory':{'manager','machine_operator'},'boutique':{'manager','salesperson','stocker'}})

INDUSTRY_ROLES['self_storage']=['property_manager','maintenance']
INDUSTRY_NAMES['self_storage']='Storage units'
OPENING_ROLES['self_storage']={'property_manager'}

ROLE_SKILLS.update({'driver':'logistics','dispatcher':'logistics'})
ROLE_PAY.update({'driver':320000,'dispatcher':330000})
INDUSTRY_ROLES['logistics']=['manager','driver','dispatcher']
INDUSTRY_NAMES['logistics']='Logistics companies'
OPENING_ROLES['logistics']={'manager','driver','dispatcher'}

ROLE_SKILLS.update({'cleaner':'service','gardener':'maintenance','security_guard':'service'})
ROLE_PAY.update({'cleaner':280000,'gardener':320000,'security_guard':340000})
for industry,role in (('cleaning','cleaner'),('landscaping','gardener'),('security','security_guard')):
    INDUSTRY_ROLES[industry]=['manager',role,'maintenance']
    INDUSTRY_NAMES[industry]={'cleaning':'Cleaning companies','landscaping':'Landscaping companies','security':'Security services'}[industry]
    OPENING_ROLES[industry]={'manager',role}

SUPPORT_ROLES = {'hr':'leadership','accounting':'finance','it':'technology','legal':'legal','purchasing':'logistics','marketing':'retail','logistics':'logistics'}
ROLE_SKILLS.update(SUPPORT_ROLES)
SUPPORT_ROLES.update({'finance':'finance','training':'leadership'})
ROLE_SKILLS.update({'finance':'finance','training':'leadership'})
ROLE_PAY.update({'finance':480000,'training':360000})
ROLE_PAY.update({'hr':360000,'accounting':440000,'it':420000,'legal':580000,'purchasing':340000,'marketing':350000,'logistics':320000})
for roles in INDUSTRY_ROLES.values():
    roles.extend(role for role in [*SUPPORT_ROLES,'maintenance'] if role not in roles)
INDUSTRY_ROLES['office']=['manager','maintenance',*SUPPORT_ROLES]
ROLE_PAY.update({'home_office_director':450000,'division_vp':600000,'corporate_services_vp':650000})
ROLE_SKILLS.update({role:'leadership' for role in ('home_office_director','division_vp','corporate_services_vp')})
INDUSTRY_ROLES['office'].extend(['home_office_director','division_vp','corporate_services_vp'])
INDUSTRY_NAMES['office']='Headquarters and shared services'
ROLE_SKILLS.update({'real_estate_agent':'service','electrician':'maintenance','plumber':'maintenance','hvac_technician':'maintenance'})
ROLE_PAY.update({'real_estate_agent':420000,'electrician':480000,'plumber':460000,'hvac_technician':470000})
for industry in ('office','property_management'):
    INDUSTRY_ROLES[industry].append('real_estate_agent')
for industry in ('office','trades','construction','property_management'):
    INDUSTRY_ROLES[industry].extend(['electrician','plumber','hvac_technician'])


def investment_account(entity: str) -> str:
    return "asset:investment" if entity == "company" else f"asset:investment:{entity}"
