"""Local presentation. No economic calculations live in the browser."""
from __future__ import annotations

import secrets
import copy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, DictLoader, select_autoescape, pass_context
from pydantic import BaseModel, Field

from . import __version__
from .build_info import build_info
from .application import Game, money
from .domain import RuleError, Engine
from .business_views import business_context, company_view
from .business_rules import BusinessRules
from .campaign_views import PAGES, campaign_view
from .funding_balances import account_balances
from .campaign_options import forecast

from .money_display import dollars, whole_money_text, display_payload

class DisplayJSONResponse(JSONResponse):
    def render(self, content):
        return super().render(display_payload(content))

ROOT = Path(__file__).parent


class Command(BaseModel):
    action: str = Field(max_length=40)
    args: dict[str, Any] = Field(default_factory=dict)
    revision: int
    campaign_session: str | None = None
    command_id: str = Field(min_length=8, max_length=100)


def create_app(game: Game, token: str, host: str, *, network_access=None, lifespan=None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, default_response_class=DisplayJSONResponse, lifespan=lifespan)
    # Capture every template at startup, including lazily used page includes.
    # Installing an update must not mix new templates with an older running engine.
    templates = {p.relative_to(ROOT / "templates").as_posix(): p.read_text(encoding="utf-8")
                 for p in (ROOT / "templates").rglob("*.html")}
    env = Environment(loader=DictLoader(templates), autoescape=select_autoescape(), finalize=whole_money_text)
    env.filters["money"] = money
    env.filters["dollars"] = dollars
    from .readable_names import text_label, account_label, name_catalog
    @pass_context
    def human(context, value):
        return text_label(context['g']['labels'], value)
    @pass_context
    def account_name(context, value):
        return account_label(context['g']['labels'], value)
    env.globals['human'] = human
    env.globals['account_name'] = account_name
    env.filters['human'] = human
    env.filters['account_name'] = account_name
    from .ui_workflows import role_label
    env.filters["role_label"] = role_label
    origin = f"http://{host}"
    env.globals['network_mode'] = network_access is not None
    build = build_info()
    env.globals['build'] = build

    def secure_headers(response):
        # Native login/logout forms need their real Origin for CSRF validation.
        # no-referrer makes browsers send Origin: null on form POSTs.
        # Network URLs contain no launcher key; do not send referrers off-site.
        referrer_policy = "same-origin" if network_access is not None else "no-referrer"
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": referrer_policy, "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        response.headers["X-Empire-Build"] = build["header"]
        return response

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        if network_access is not None:
            response = await network_access.check(request, env)
            return secure_headers(response if response is not None else await call_next(request))
        if request.headers.get("host") != host:
            return DisplayJSONResponse({"detail": "This game accepts only its own local address."}, status_code=403)
        if request.url.path == "/" and secrets.compare_digest(request.query_params.get("key", ""), token):
            response = RedirectResponse("/", status_code=303)
            response.set_cookie("game_session", token, httponly=True, samesite="strict")
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        if not secrets.compare_digest(request.cookies.get("game_session", ""), token):
            return HTMLResponse("<h1>Open Empire Manager from its launcher</h1><p>This window has no active game session.</p>", status_code=403)
        if request.method not in ("GET", "HEAD"):
            if request.headers.get("origin") != origin or not secrets.compare_digest(request.headers.get("x-game-token", ""), token):
                return DisplayJSONResponse({"detail": "This action did not come from the game window."}, status_code=403)
        response = await call_next(request)
        return secure_headers(response)

    @app.exception_handler(RuleError)
    async def rule_error(request: Request, error: RuleError):
        from .recovery_navigation import recovery_links
        with game.lock:
            links=recovery_links(game.world,str(error),getattr(request.state,"action_args",{}))
        return DisplayJSONResponse({"detail": str(error), "recovery_links": links}, status_code=409)

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(page: str = "overview", scope: str = "personal", property_id: str = "", region: str = "all", business_id: str = "", employment_id: str = "", industry: str = "all", search: str = "", consolidated: bool = False, role: str = "", chart: str = "ownership", org_root: str = "", position_id: str = "", all_properties: bool = False, category: str = "all", leader_id: str = "", activity_business: str = "", activity_status: str = "all", activity_page: int = 1, inbox_item: str = "", authority_business: str = "", action_focus: str = "", work_system: str = "", department_id: str = "", shared_team: str = "", service_product: str = ""):
        if page not in PAGES and page not in ("games","management","hiring","overview", "market", "portfolio", "property", "finance", "owner", "activity", "business_market", "businesses", "business", "people", "employee", "organization"):
            page = "overview"
        with game.lock:
            from .navigation import resolve_context, navigation_view
            all_properties=all_properties and page=='portfolio'
            context=resolve_context(game.world,page,scope,business_id,employment_id,property_id,chart,org_root,all_properties)
            page,scope,business_id,org_root=(context[k] for k in ('page','scope','business_id','org_root'))
            from .vermont import county
            region=county(region)
            view = game.view(scope)
            view['labels'] = name_catalog(game.world)
            from .financial_trends import trend_view
            trend_group = (consolidated and page == 'finance') or page == 'overview'
            view['trends'] = trend_view(game.world, game.store, view['group_entities'] if trend_group else [scope], trend_group)
            view['cash_trend'] = trend_view(game.world, game.store, [scope])['charts'][0] if trend_group else view['trends']['charts'][0]
            view['trend_scope'] = view['scope_name'] + (' and currently owned companies' if trend_group else ' account')
            view['navigation_notice']=context['notice']
            view["counties"]=sorted(r["id"] for r in game.world.systems["regions"])
            view["account_balances"] = account_balances(game.world)
            from .saved_games import library, label
            view["campaign_session"]=game.session_id
            view["campaign_label"]=label(game.world,game.store.path)
            if page=="games":view["games"]=library(game)
            if page in ('people','employee'):
                from .employee_management_views import view as employee_management_view
                view['employee_management']=employee_management_view(game.world,business_id,employment_id if page=='employee' else '')
            view['authority_focus']=authority_business if page=='management' and authority_business in {b['id'] for b in view['businesses']} else ''
            if view['authority_focus']:search=''  # A direct limit link must not be hidden by an old search.
            nav=navigation_view(game.world,page,scope,business_id,chart,all_properties)
            if page=="property" and any(p["id"]==property_id for p in view["market"]):nav["buyer"]=True
            staffing=hiring=org=management=leader_activity=None
            if page=="management":
                from .management import Management
                management=Management(Engine(game.world)).overview(search)
                from .leadership_activity import activity_view
                leader_activity=activity_view(game.world,activity_business,leader_id,activity_status,activity_page)
            if page=='organization':
                from .organization import organization_view
                org=organization_view(game.world,chart,business_id,org_root)
            from .staffing import staffing_plan,hiring_view
            if page=='business' and any(b['id']==business_id for b in view['businesses']):staffing=staffing_plan(game.world,business_id)
            view['restaurant']=None
            if page=='business':
                selected_restaurant=next((b for b in game.world.businesses if b.id==business_id and b.industry=='restaurant' and b.id in {v['id'] for v in view['businesses']}),None)
                if selected_restaurant:
                    from .restaurant_views import view as restaurant_view
                    view['restaurant']=restaurant_view(game.world,selected_restaurant)
            if page=='hiring':hiring=hiring_view(game.world,business_id,role,position_id)
            campaign = campaign_view(game.world,page,view["scope"],employment_id) if page in PAGES else None
            if campaign:
                from .ui_workflows import prepare
                prepare(campaign,game.world,scope,property_id,action_focus,work_system,department_id,shared_team,service_product)
            if campaign and inbox_item:
                from .decision_inbox import focus
                focus(campaign,game.world,inbox_item)
            report = game.store.report(view["scope"], view["date"][:7] + "-01", view["group_entities"] if consolidated else None) if page == "finance" else None
            balances = {}
            financial_detail = None
            for entity in (view['group_entities'] if consolidated else [view['scope']]):
                for key,value in game.world.accounts[entity].items():
                    if key.startswith(('asset:', 'liability:')) and not (consolidated and key.startswith('asset:investment')):
                        balances[key] = balances.get(key,0)+value
            if page == 'finance':
                from .financial_detail import detail_view
                financial_detail=detail_view(game.world,game.store,view['group_entities'] if consolidated else [view['scope']],balances,view['date'][:7]+'-01')
        from .property_scale_views import detail, hr_view
        view['hr_work']=hr_view(game.world)
        from .property_development import owner_busy
        view['owner_repair_busy']=owner_busy(game.world)
        view['owner_decisions_left']=max(0,2-game.world.systems.get('owner_decisions',{}).get(game.world.date,0))
        selected = next((p for p in view["market"] + view["owned"] if p["id"] == property_id), None)
        care=detail(game.world,property_id) if selected else None
        if page == "property" and selected is None:
            page = "portfolio"
        if category not in ('all','residential','commercial','office','mixed_use','industrial','land'):category='all'
        properties = view['market'] if page=='market' else view['all_owned'] if all_properties else view['owned']
        market = [p for p in properties if (region=='all' or p['region']==region) and (category=='all' or p['category']==category)]
        business = next((b for b in view['business_market'] + view['businesses'] if b['id']==business_id),None)
        employee = next((e for e in view['employees'] if e['id']==employment_id),None)
        if page=='business' and business is None: page='businesses'
        if page=='employee' and employee is None: page='people'
        listing=[b for b in view['business_market'] if industry=='all' or b['industry']==industry]
        employees=[e for e in view['employees'] if (not business_id or e['business_id']==business_id) and (not search or search.lower() in (e['name']+' '+e['role_label']+' '+e['business_name']).lower())]
        return env.get_template("game.html").render(runtime_version=__version__, g=view, page=page, selected=selected, market=market, region=region, report=report, token=token, business=business, employee=employee, business_market=listing, industry=industry, employees=employees, search=search, business_id=business_id, balances=balances, financial_detail=financial_detail, consolidated=consolidated, campaign=campaign, campaign_pages=PAGES, staffing=staffing, hiring=hiring, org=org, management=management, leader_activity=leader_activity, nav=nav, all_properties=all_properties, category=category, care=care)

    def normalized_args(data):
        args = dict(data.args)
        if data.action in ("hire_for_role","invest", "withdraw", "fund_business", "distribute_profit", "hire", "employment_terms", "promote"):
            try:
                dollars = Decimal(str(args.pop("amount_dollars")))
                if not dollars.is_finite() or dollars <= 0 or dollars > Decimal("1000000000") or dollars != dollars.quantize(Decimal("0.01")):
                    raise ValueError()
                args["amount"] = int(dollars * 100)
            except (InvalidOperation, ValueError, KeyError):
                raise RuleError("Enter a positive dollar amount with at most two decimal places.")
        for key in list(args):
            if key.endswith('_dollars'):
                try:
                    value=Decimal(str(args.pop(key)))
                    if not value.is_finite() or value<0 or value>Decimal('1000000000') or value!=value.quantize(Decimal('0.01')):raise ValueError()
                    args[key[:-8]]=int(value*100)
                except (InvalidOperation,ValueError):raise RuleError('Enter a nonnegative dollar amount with no more than two decimals.')
        return args

    def check_campaign(data):
        if data.campaign_session is not None and data.campaign_session!=game.session_id:
            raise RuleError('A different game is now open. Refresh this screen before making a decision.')

    @app.post("/api/preview")
    def preview(data: Command, request: Request):
        request.state.action_args=data.args
        args=normalized_args(data)
        with game.lock:
            check_campaign(data)
            if game.progress['running'] or data.revision!=game.world.revision:
                raise RuleError("Refresh after time advancement before reviewing a new decision.")
            from .saved_games import ACTIONS, preview as game_preview
            if data.action in ACTIONS:
                return dict(message=game_preview(game,data.action,args),description='Saved games stay independent. No game time advances.',action_links=[])
            engine=Engine(copy.deepcopy(game.world))
            before=business_context(game.world,'personal')
            try:
                result=engine.action(data.action,args,'preview-only')
                engine.validate()
            except RuleError: raise
            except (ValueError,TypeError): raise RuleError("Check the entered numbers and choices.")
            after=business_context(engine.world,'personal')
            names={e['id']:e['name'] for e in after['entities']}
            changes=[]
            for entity in game.world.accounts:
                delta=engine.world.cash(entity)-game.world.cash(entity)
                if delta:changes.append(f"{names.get(entity, entity)} cash: {money(delta)} (remaining {money(engine.world.cash(entity))}).")
            prior={b['id']:b['monthly_payroll'] for b in before['businesses']}
            for b in after['businesses']:
                if data.action!='hire_for_role' and b['monthly_payroll']!=prior.get(b['id'],0):
                    changes.append(f"{b['name']} monthly employer payroll: {money(prior.get(b['id'],0))} → {money(b['monthly_payroll'])}.")
            if data.action in ('policy_set','policy_reset'):
                from .workforce import Workforce
                effective=engine.world.systems['policies'][-1]['effective']
                old_wf=Workforce(Engine(game.world));new_wf=Workforce(engine)
                old_cost=new_cost=affected=0
                for emp in game.world.employments:
                    if emp.employer in game.world.accounts and emp.status in ('active','joining'):
                        old_policy=old_wf.effective(emp.employer,emp,on=effective)[0];new_policy=new_wf.effective(emp.employer,emp,on=effective)[0]
                        if old_policy!=new_policy:affected+=1
                        old_cost+=old_wf.benefit_cost(emp,old_policy);new_cost+=new_wf.benefit_cost(emp,new_policy)
                changes.append(f'{affected} employees affected from {effective}. Annualized employer benefit change: {money((new_cost-old_cost)*12)}. Leave/holiday changes also change coverage.')
            from .recovery_navigation import delegation_link
            policy_link=delegation_link(game.world,args.get('request_id')) if data.action=='management_approve' else None
            return {'message':result, 'description':' '.join(changes) or 'No immediate cash movement. This changes future operations or staffing.', 'action_links':[policy_link] if policy_link else []}

    @app.post("/api/command")
    def command(data: Command, request: Request):
        request.state.action_args=data.args
        args=normalized_args(data)
        try:
            with game.lock:
                check_campaign(data)
                result=game.execute(data.action,args,data.revision,data.command_id)
        except RuleError: raise
        except (ValueError,TypeError): raise RuleError("Check the entered numbers and choices.")
        return {"message":result}

    @app.post('/api/forecast')
    def forecast_query(data: Command):
        with game.lock:
            check_campaign(data)
            if game.progress['running'] or data.revision!=game.world.revision:raise RuleError('Pause time and refresh before forecasting from the latest saved state.')
            snapshot=copy.deepcopy(game.world)
        return forecast(snapshot,data.args.get('days',30))

    @app.get("/api/progress")
    def progress(scope: str = 'personal'):
        with game.lock:
            from .business_views import entity_names
            names=entity_names(game.world)
            account=scope if scope in names else 'personal'
            cash=game.world.cash(account)
            from .leadership_activity import notification
            from .decision_inbox import count
            from .recovery_navigation import progress_links
            return {**game.progress, 'account_balances':account_balances(game.world), 'campaign_session':game.session_id, 'links':progress_links(game.world,game.progress), 'inbox_count':count(game.world), 'leadership_activity':notification(game.world), 'cash_on_hand':cash, 'cash_label':money(cash), 'cash_scope':account}

    @app.post("/api/cancel")
    def cancel(request: Request):
        with game.lock:
            session=request.headers.get('x-game-session')
            if session and session!=game.session_id:raise RuleError('A different game is now open. Refresh this screen.')
            game.stop()
        return {"message": "Pausing after the current day is saved."}

    return app
