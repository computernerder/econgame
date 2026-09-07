"""One writer, validated commands, read models, and cancellable daily skips."""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import uuid
from datetime import date
from pathlib import Path

from .domain import Engine, RuleError, calendar_target
from .persistence import Store
from .business_views import business_context, entity_names


from .money_display import money


class Game:
    def __init__(self, save_path: Path, save_lock=None):
        self.lock = threading.RLock()
        self.store = Store(save_path)
        self.world = self.store.load()
        self.store.audit(self.world)
        self.extra_save_lock = save_lock
        self.session_id = uuid.uuid4().hex
        self.library_results = {}
        self.cancel = threading.Event()
        self.worker: threading.Thread | None = None
        self.progress = dict(running=False, completed=0, total=0, message="Your game is saved after every action and day.")

    def execute(self, action: str, args: dict, revision: int, command_id: str) -> str:
        if not 8 <= len(command_id) <= 100:
            raise RuleError("Invalid request identifier. Refresh and try again.")
        fingerprint = hashlib.sha256(json.dumps([action, args], sort_keys=True).encode()).hexdigest()
        with self.lock:
            cached=self.library_results.get(command_id)
            if cached:
                if cached[0]!=fingerprint:raise RuleError('That request identifier was already used for a different action.')
                return cached[1]
            existing = self.store.command_result(command_id, fingerprint)
            if existing is not None:
                return existing
            if self.progress["running"]:
                raise RuleError("Pause time advancement before making changes.")
            if revision != self.world.revision:
                raise RuleError("This screen is out of date. Refresh it before making this decision.")
            from .saved_games import ACTIONS, execute as game_action
            if action in ACTIONS:
                result=game_action(self,action,args,command_id,fingerprint)
                self.library_results[command_id]=(fingerprint,result)
                if len(self.library_results)>100:self.library_results.pop(next(iter(self.library_results)))
                return result
            engine = Engine(copy.deepcopy(self.world))
            if action == "advance":
                today = date.fromisoformat(self.world.date)
                try:
                    target = date.fromisoformat(args["target"]) if args.get("target") else calendar_target(today, args.get("period", "day"))
                except (ValueError, TypeError, OverflowError) as exc:
                    raise RuleError("Choose a valid future date.") from exc
                days = (target - today).days
                if not 1 <= days <= 3660:
                    raise RuleError("Advance between one day and ten years at a time.")
                # Preferences and target commit with the advance command, before
                # its worker starts. A failed request cannot change either.
                from .campaign_options import CampaignOptions
                changes={k:args[k] for k in ('pause_routine','financial_pause_threshold') if k in args}
                if changes:CampaignOptions(engine).action('settings',changes,command_id)
                from .skip_controls import resume_target
                previous=resume_target(engine.world)
                if not (days==1 and previous and previous>target.isoformat()):
                    engine.world.systems['time_skip']=dict(target=target.isoformat())
                if days > 7:
                    self.store.backup()
                result = f"Advancing toward {target.isoformat()}. Routine work continues; your interruption preferences apply."
            elif action == "backup":
                self.store.backup("manual-backup")
                result = "Manual backup saved. Your current game remains active."
            else:
                result = engine.action(action, args, command_id)
            if action.startswith('developer_') and action != 'developer_toggle' and not self.world.systems.get('developer_history'):
                self.store.backup('before-developer-edit')
            self.store.commit(engine, revision, (command_id, fingerprint, result))
            self.world = engine.world
            if action == "advance":
                self.cancel.clear()
                self.progress = dict(running=True, completed=0, total=days, target=target.isoformat(), message=result)
                self.worker = threading.Thread(target=self._run, args=(days,), daemon=True, name="simulation-writer")
                self.worker.start()
            return result

    def _run(self, days: int) -> None:
        reason = "Time advancement complete."
        blocked = False
        blocker = ""
        digest={}
        with self.lock:
            start_balances = {e:self.world.cash(e) for e in self.world.accounts}
            start_cash = sum(start_balances[e] for e in entity_names(self.world))
            self.progress['cash_start'] = start_balances
            self.progress['start_date'] = self.world.date
        try:
            for _ in range(days):
                if self.cancel.is_set():
                    reason = "Paused at the last saved day."
                    break
                with self.lock:
                    from .campaign import Campaign
                    controlled=Campaign(Engine(self.world)).controlled
                    from .director_scope import overloaded
                    if days>1 and overloaded(self.world):
                        blocked=True;blocker='approval'
                        reason='Director workload exceeded. Review inherited oversight in the decision inbox before a long skip; a single day remains available for recovery.'
                        break
                    from .time_off import blockers as leave_blockers
                    if days>1 and leave_blockers(self.world):
                        blocked=True;blocker='approval'
                        reason='Time-off approval needed. Review pending requests in the decision inbox before a long skip.'
                        break
                    from .routine_management import ready_property_care
                    manager_queue=ready_property_care(self.world) if days>1 else set()
                    if days>1 and any(r['status']=='open' and r['id'] not in manager_queue and controlled(r['business_id']) for r in self.world.systems.get('management_requests',[])):
                        blocked = True
                        blocker = 'approval'
                        reason='Owner approval needed. Resolve management requests before a long skip; a single day remains available for recovery.'
                        break
                    engine = Engine(copy.deepcopy(self.world))
                    stop = engine.advance_day()
                    from .skip_controls import resume_target
                    if not resume_target(engine.world):engine.world.systems.pop('time_skip',None)
                    self.store.commit(engine, self.world.revision)
                    self.world = engine.world
                    self.progress["completed"] += 1
                    for event in engine.events:
                        if event.get('important') and event.get('pause_suppressed'):
                            digest[event['title']]=digest.get(event['title'],0)+1
                    self.progress['digest']=[dict(title=title,count=count) for title,count in sorted(digest.items())]
                if stop:
                    blocked = True
                    self.progress['stops']=getattr(engine,'pause_details',[])
                    reason = "Paused for an important event" + (": " + engine.pause_reason_text if engine.pause_reason_text else "") + ". Review your activity and choose your next step."
                    break
        except Exception as exc:
            blocked = True
            reason = f"Time stopped safely at the last saved day: {exc}"
        finally:
            with self.lock:
                self.progress['cash_end'] = {e:self.world.cash(e) for e in self.world.accounts}
                self.progress['end_date'] = self.world.date
                change = sum(self.world.cash(e) for e in entity_names(self.world)) - start_cash
                self.progress['group_cash_change'] = change
                count = self.progress["completed"]
                self.progress.update(running=False, blocked=blocked, blocker=blocker, reason=reason, message=f"{reason} Advanced {count} {'day' if count == 1 else 'days'}. Group cash change: {money(change)}.")

    def progress_view(self, scope='personal') -> dict:
        """Render the completed skip against its frozen account balances, not later actions."""
        progress=copy.deepcopy(self.progress)
        if not progress['running'] and 'cash_end' in progress:
            names=entity_names(self.world);scope=scope if scope in names else 'personal'
            start=progress['cash_start'].get(scope,0);end=progress['cash_end'].get(scope,0)
            change=end-start;count=progress['completed']
            progress.update(cash_change=change,cash_before=start,cash_after=end,change_scope=scope)
            progress['message']=(f"{progress['reason']} Advanced {count} {'day' if count==1 else 'days'}. "
                f"{names[scope]} cash change: {money(change)} ({money(start)} → {money(end)}). "
                f"{progress['start_date']} to {progress['end_date']}. "
                f"Group cash change across owned accounts: {money(progress['group_cash_change'])}.")
        return progress

    def stop(self) -> None:
        self.cancel.set()

    def close(self) -> None:
        self.stop()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=10)
        if self.extra_save_lock:self.extra_save_lock.close();self.extra_save_lock=None

    def view(self, scope: str = "personal") -> dict:
        with self.lock:
            w = self.world
            if scope not in entity_names(w): scope = "personal"
            today, birth = date.fromisoformat(w.date), date.fromisoformat(w.birth_date)
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            engine = Engine(w)
            properties = []
            for p in w.properties:
                if p.status in ("expired", "sold", "business_asset"):
                    continue
                item = vars(p).copy()
                from .personal_residence import is_residence, blocker
                item.update(is_residence=is_residence(p),residence_blocker=blocker(w,p))
                from .property_services import presentation
                item.update(owner_name=entity_names(w).get(p.owner,"Seller"), value=p.value, suggested_rent=p.suggested_rent*presentation(w,p)//100, buy=engine.quote("buy", p.id,scope), refresh=engine.quote("refresh", p.id), rehabilitate=engine.quote("rehabilitate", p.id), sell=engine.quote("sell", p.id))
                from .transaction_legal import TransactionLegal
                item['legal_terms']=TransactionLegal(engine).terms(p)
                properties.append(item)
            owned = [p for p in properties if p["owner"] == scope]
            accounts = w.accounts[scope]
            business = business_context(w,scope)
            personal_book = business['personal_book']
            company_equity = business['all_business_wealth']
            personal_equity = business['total_wealth'] - company_equity
            from .holding_company import exists, name
            view = dict(has_holding_company=exists(w), holding_company_name=name(w), date=w.date, date_label=today.strftime("%d %b %Y"), revision=w.revision, name=w.owner_name, age=age, scope=scope, cash=w.cash(scope), personal_cash=w.cash("personal"), company_cash=w.cash("company"), total_wealth=personal_equity + company_equity, personal_book=personal_book, company_equity=company_equity, invested=w.accounts["personal"].get("asset:investment", 0), owned=owned, market=[p for p in properties if p["status"] == "market"], events=list(reversed(w.events)), monthly_rent=sum(p["rent"] for p in owned if p["status"] == "rented")+sum(l["rent"] for l in w.systems.get("leases",[]) if l["owner"]==scope and l["status"]=="active"), monthly_upkeep=sum(p["upkeep"] for p in owned), portfolio_value=sum(p["value"] for p in owned), basis=accounts.get("asset:property", 0), payable=-accounts.get("liability:payable", 0), lifetime_profit=-sum(v for k, v in accounts.items() if k.startswith(("income:", "expense:"))), progress=self.progress_view(scope), accounts=dict(accounts))
            from .personal_residence import view as residence_view
            view['residence']=residence_view(w)
            view["all_owned"]=[p for p in properties if p["owner"] in entity_names(w)]
            view.update(business)
            from .skip_controls import preferences,resume_target
            skip=preferences(w.systems.get('settings',{}))
            view['skip_threshold']=skip['financial_pause_threshold']
            view['pause_routine']=skip['pause_routine']
            view['resume_target']=resume_target(w)
            view['campaign_modified'] = w.systems.get('settings', {}).get('modified', False)
            view['outcome']=w.systems.get('campaign_outcome')
            from .leadership_activity import notification
            view['leadership_activity']=notification(w)
            from .decision_inbox import count
            view['inbox_count']=count(w)
            from .recovery_navigation import progress_links, approval_links, delegation_link
            view['progress']['links']=progress_links(w,self.progress)
            view['approval_links']=approval_links(w)
            view['delegation_links']={r['id']:link for r in w.systems.get('management_requests',[]) if (link:=delegation_link(w,r['id']))}
            return view
