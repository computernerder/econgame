"""Versioned SQLite snapshots and an append-only double-entry journal."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .domain import CONTENT_VERSION, PREVIOUS_CONTENT_VERSION, STORAGE_CONTENT_VERSION, EXPANSION_CONTENT_VERSION, PROPERTY_CONTENT_VERSION, INDUSTRIES_CONTENT_VERSION, LEGACY_CONTENT_VERSION, V1_CONTENT_VERSION, V2_CONTENT_VERSION, SIMULATION_VERSION, Engine, RuleError, World, new_game

SCHEMA_VERSION = 3


class Store:
    def __init__(self, path: Path, initial: Engine | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, SCHEMA_VERSION):
                raise RuleError(f"Save schema {version} is not supported. The original file was not modified.")
            if version in (1,2):
                self.migrate_v1(db,version)
            if version == 0 and db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                raise RuleError("This file is not a recognized game save. Choose a different save path.")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS world (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY, entity TEXT NOT NULL, source TEXT NOT NULL, date TEXT NOT NULL, memo TEXT NOT NULL, UNIQUE(entity,source));
                CREATE TABLE IF NOT EXISTS lines (journal_id INTEGER REFERENCES journal(id), account TEXT NOT NULL, amount INTEGER NOT NULL, PRIMARY KEY(journal_id,account));
                CREATE INDEX IF NOT EXISTS journal_scope_date ON journal(entity,date);
                CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, date TEXT NOT NULL, data TEXT NOT NULL);
            """)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            if not db.execute("SELECT 1 FROM world").fetchone():
                engine = initial or new_game()
                db.execute("INSERT INTO world VALUES(1,0,?)", (json.dumps(engine.world.to_dict()),))
                self.append(db, engine)
            else:
                self.upgrade_industries(db)
                self.upgrade_properties(db)
                self.upgrade_expansion(db)
                self.upgrade_storage(db)
                self.upgrade_logistics(db)
                self.upgrade_operations(db)
                self.upgrade_service_projects(db)
                self.upgrade_commercial_contracts(db)
                self.upgrade_property_services(db)
                self.upgrade_parallel_projects(db)
                self.upgrade_employee_management(db)
                self.upgrade_property_scale(db)
                self.upgrade_vermont(db)

    def upgrade_vermont(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version')!=CONTENT_VERSION or data.get('simulation_version')!=SIMULATION_VERSION:return
        from .vermont import VERSION, migrate
        if data.get('systems',{}).get('geography_version',0)>=VERSION:return
        self.backup('before-vermont-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        migrate(engine)
        engine.event('Welcome to Vermont','Regions are now Vermont counties. Willow Creek became Rutland County, Northbank became Chittenden County, and Parkside became Washington County. Existing assets, staff, balances and geographic authority are preserved; eleven more counties are available.')
        engine.validate();self.audit(engine.world);engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('Campaign changed during the Vermont upgrade.')
        self.append(db,engine);db.commit()

    def upgrade_property_scale(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version')!=CONTENT_VERSION or data.get('simulation_version')!=SIMULATION_VERSION:return
        if data.get('systems',{}).get('land_market_version'):return
        self.backup('before-property-scale-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        from .property_development import Development
        Development(engine).ensure()
        engine.event('Property development available','Empty lots, specialized premises, licensed repairs and in-house agent representation are available. Existing holdings and staff credentials are preserved.')
        engine.validate();self.audit(engine.world);engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('Campaign changed during property upgrade.')
        self.append(db,engine);db.commit()

    def upgrade_employee_management(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version')!=CONTENT_VERSION or data.get('simulation_version')!=SIMULATION_VERSION:return
        if data.get('systems',{}).get('employee_management_version',0)>=21:return
        self.backup('before-employee-management-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        from .employee_names import migrate_names
        renamed=migrate_names(engine.world)
        engine.world.systems['employee_management_version']=21
        engine.event('Employee management updated',f'Dated time-off requests, coverage and cross-company reporting are available. {renamed} numbered or duplicate names replaced; employee identities, payroll and history retained.')
        engine.validate();self.audit(engine.world);engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db,engine);db.commit()

    def upgrade_parallel_projects(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version')!=CONTENT_VERSION or data.get('simulation_version')!=SIMULATION_VERSION:return
        if all('parallel_projects' in b and 'concurrent_project_limit' in b for b in data.get('businesses',[])):return
        self.backup('before-parallel-projects-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        engine.event('Concurrent projects available','Project businesses can share qualified hours across multiple contracts. Existing jobs, earned fees and employee identities retained; recovery backup created.')
        engine.validate();self.audit(engine.world);engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db,engine);db.commit()

    def upgrade_property_services(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') not in (CONTENT_VERSION,PREVIOUS_CONTENT_VERSION) or data.get('simulation_version')!=SIMULATION_VERSION:return
        if data['systems'].get('property_services_version',0)>=14 and data['systems'].get('version')==5 and data['content_version']==CONTENT_VERSION:return
        self.backup('before-property-services-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        from .domain import BUSINESS_CONTENT
        from .business_rules import BusinessRules
        from .property_services import PropertyServices,SERVICES
        rules=BusinessRules(engine);present={b.industry for b in engine.world.businesses}
        for index,spec in enumerate(BUSINESS_CONTENT['catalog']):
            if spec['industry'] in SERVICES and spec['industry'] not in present:rules.add_business(index);present.add(spec['industry'])
        for spec in SERVICES.values():
            if not any(p.candidate and spec['skill'] in p.demonstrated for p in engine.world.people):rules.make_person(spec['role'],candidate=True)
        engine.world.content_version=CONTENT_VERSION;engine.world.systems.update(version=5,property_services_version=14)
        PropertyServices(engine).initialize()
        engine.event('Property service businesses available','Cleaning, landscaping and licensed security companies serve outside customers and owned property plans. Existing people and balances retained; recovery backup created.')
        engine.validate();self.audit(engine.world);engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db,engine);db.commit()

    def upgrade_commercial_contracts(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') not in (CONTENT_VERSION,PREVIOUS_CONTENT_VERSION) or data.get('simulation_version')!=SIMULATION_VERSION:return
        if data.get('systems',{}).get('commercial_contracts_version',0)>=13 and data['systems'].get('version',0)>=4:return
        self.backup('before-commercial-contracts-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        engine.world.systems.update(version=4,commercial_contracts_version=13)
        from .transaction_legal import TransactionLegal
        TransactionLegal(engine).initialize()
        engine.event('Contracts and purchasing available','New Covenant Works listings disclose transfer consent and roof obligations. Outside-service supplier agreements offer finite prepaid capacity. Prior properties, employees and balances retained; recovery backup created.')
        engine.validate();self.audit(engine.world);engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db,engine);db.commit()

    def upgrade_service_projects(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') not in (CONTENT_VERSION,PREVIOUS_CONTENT_VERSION) or data.get('simulation_version')!=SIMULATION_VERSION:return
        systems=data.get('systems',{})
        if systems.get('version') not in (1,2,3,4,5):raise RuleError('Unsupported campaign systems version.')
        if systems.get('service_projects_version',0)>=12 and systems.get('version')>=3:return
        self.backup('before-service-projects-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        engine.world.systems.update(version=3,service_projects_version=12)
        engine.event('Specific service projects available','HR recruiting, assessment, onboarding and succession; IT deployments; tenant maintenance requests. Existing obligations and people retained; recovery backup created.')
        engine.validate();self.audit(engine.world)
        engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db,engine);db.commit()

    def upgrade_operations(self,db):
        data=json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') not in (CONTENT_VERSION,PREVIOUS_CONTENT_VERSION) or data.get('simulation_version')!=SIMULATION_VERSION:return
        if data.get('systems',{}).get('operations_version',0)>=11:return
        self.backup('before-operations-'+uuid.uuid4().hex[:12])
        engine=Engine(World.from_dict(data))
        engine.world.systems.update(version=2,operations_version=11)
        from .property_operations import PropertyOperations
        PropertyOperations(engine).ensure_market_types()
        engine.event('Operating systems updated','Staffed service queues, dated obligations, optional authority, property systems and contingent sales are available. Existing balances, employees and ownership were preserved; a campaign backup was made.')
        engine.validate();self.audit(engine.world)
        engine.world.revision+=1
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',(engine.world.revision,json.dumps(engine.world.to_dict()),data['revision']))
        if changed.rowcount!=1:raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db,engine);db.commit()

    def upgrade_industries(self, db):
        """Upgrade only the recognized prior content release, exactly once."""
        data = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') != LEGACY_CONTENT_VERSION or data.get('simulation_version') != SIMULATION_VERSION:
            return
        self.backup('before-industries-' + uuid.uuid4().hex[:12])
        from .business_rules import BusinessRules
        from .domain import BUSINESS_CONTENT, INDUSTRY_CONTENT
        from .business_models import INDUSTRY_ROLES, ROLE_SKILLS
        engine = Engine(World.from_dict(data))
        rules = BusinessRules(engine)
        new_types = {b['industry'] for b in INDUSTRY_CONTENT['catalog']}
        present = {b.industry for b in engine.world.businesses}
        for index, spec in enumerate(BUSINESS_CONTENT['catalog']):
            if spec['industry'] in new_types - present:
                rules.add_business(index)
                present.add(spec['industry'])
        # Supply applicants for new specialties without replacing existing people.
        roles = {role for industry in new_types for role in INDUSTRY_ROLES[industry][:3]}
        for role in sorted(roles):
            if not any(p.candidate and ROLE_SKILLS[role] in p.demonstrated for p in engine.world.people):
                rules.make_person(role, candidate=True)
        engine.world.content_version = INDUSTRIES_CONTENT_VERSION
        engine.event('New business industries available', 'Skilled trades, construction, gas stations, grocery stores, banks and car dealerships are available to buy or start. Existing ownership and balances are preserved.')
        engine.validate()
        self.audit(engine.world)
        engine.world.revision += 1
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',
                             (engine.world.revision, json.dumps(engine.world.to_dict()), data['revision']))
        if changed.rowcount != 1:
            raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db, engine)
        db.commit()

    @staticmethod
    def ensure_property_categories(engine):
        from .domain import CONTENT
        for index, spec in enumerate(CONTENT['properties']):
            if spec.get('category') not in ('commercial','industrial'):
                continue
            if not any(p.status=='market' and p.category==spec['category'] and p.region==spec['region'] for p in engine.world.properties):
                engine.populate_market(1, template_index=index)

    def upgrade_properties(self, db):
        data = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') != INDUSTRIES_CONTENT_VERSION or data.get('simulation_version') != SIMULATION_VERSION:
            return
        self.backup('before-property-types-' + uuid.uuid4().hex[:12])
        engine = Engine(World.from_dict(data))
        self.ensure_property_categories(engine)
        engine.world.content_version = PROPERTY_CONTENT_VERSION
        engine.event('Three property markets', 'Residential homes, commercial premises and industrial buildings are now available. Existing ownership and leases are preserved.')
        engine.validate()
        self.audit(engine.world)
        engine.world.revision += 1
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',
                            (engine.world.revision, json.dumps(engine.world.to_dict()), data['revision']))
        if changed.rowcount != 1:
            raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db, engine)
        db.commit()

    @staticmethod
    def ensure_expansion(engine):
        from .domain import BUSINESS_CONTENT, EXPANSION_CONTENT
        from .business_rules import BusinessRules
        from .business_models import ROLE_SKILLS, INDUSTRY_ROLES
        types = {spec['industry'] for spec in EXPANSION_CONTENT['catalog']}
        present = {b.industry for b in engine.world.businesses}
        rules = BusinessRules(engine)
        for index, spec in enumerate(BUSINESS_CONTENT['catalog']):
            if spec['industry'] in types - present:
                rules.add_business(index)
                present.add(spec['industry'])
        for role in sorted({role for industry in types for role in INDUSTRY_ROLES[industry][:3]}):
            if not any(p.candidate and ROLE_SKILLS[role] in p.demonstrated for p in engine.world.people):
                rules.make_person(role, candidate=True)

    def upgrade_expansion(self, db):
        data = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') != PROPERTY_CONTENT_VERSION or data.get('simulation_version') != SIMULATION_VERSION:
            return
        self.backup('before-factories-boutiques-' + uuid.uuid4().hex[:12])
        engine = Engine(World.from_dict(data))
        self.ensure_expansion(engine)
        engine.world.content_version = EXPANSION_CONTENT_VERSION
        engine.event('Factories and boutiques available', 'Manufacturing factories and fashion boutiques are now available to buy or start. Existing businesses and finances are preserved.')
        engine.validate()
        self.audit(engine.world)
        engine.world.revision += 1
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',
                            (engine.world.revision, json.dumps(engine.world.to_dict()), data['revision']))
        if changed.rowcount != 1:
            raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db, engine)
        db.commit()

    @staticmethod
    def ensure_storage(engine):
        from .domain import BUSINESS_CONTENT, STORAGE_CONTENT
        from .business_rules import BusinessRules
        from .business_models import ROLE_SKILLS, INDUSTRY_ROLES
        types = {spec['industry'] for spec in STORAGE_CONTENT['catalog']}
        present = {b.industry for b in engine.world.businesses}
        rules = BusinessRules(engine)
        for index, spec in enumerate(BUSINESS_CONTENT['catalog']):
            if spec['industry'] in types - present:
                rules.add_business(index)
                present.add(spec['industry'])
        for role in sorted({role for industry in types for role in INDUSTRY_ROLES[industry][:3]}):
            if not any(p.candidate and ROLE_SKILLS[role] in p.demonstrated for p in engine.world.people):
                rules.make_person(role, candidate=True)

    def upgrade_storage(self, db):
        data = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') != EXPANSION_CONTENT_VERSION or data.get('simulation_version') != SIMULATION_VERSION:
            return
        self.backup('before-storage-' + uuid.uuid4().hex[:12])
        engine = Engine(World.from_dict(data))
        self.ensure_storage(engine)
        engine.world.content_version = STORAGE_CONTENT_VERSION
        engine.event('Self-storage available', 'Storage facilities are now available to buy or start, with finite units, tenant occupancy and rental income. Existing assets and finances are preserved.')
        engine.validate()
        self.audit(engine.world)
        engine.world.revision += 1
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',
                            (engine.world.revision, json.dumps(engine.world.to_dict()), data['revision']))
        if changed.rowcount != 1:
            raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db, engine)
        db.commit()

    @staticmethod
    def ensure_logistics(engine):
        from .domain import BUSINESS_CONTENT, LOGISTICS_CONTENT
        from .business_rules import BusinessRules
        from .business_models import ROLE_SKILLS, INDUSTRY_ROLES
        types = {spec['industry'] for spec in LOGISTICS_CONTENT['catalog']}
        present = {b.industry for b in engine.world.businesses}
        rules = BusinessRules(engine)
        for index, spec in enumerate(BUSINESS_CONTENT['catalog']):
            if spec['industry'] in types - present:
                rules.add_business(index)
                present.add(spec['industry'])
        for role in sorted({role for industry in types for role in INDUSTRY_ROLES[industry][:3]}):
            if not any(p.candidate and ROLE_SKILLS[role] in p.demonstrated for p in engine.world.people):
                rules.make_person(role, candidate=True)

    def upgrade_logistics(self, db):
        data = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        if data.get('content_version') != STORAGE_CONTENT_VERSION or data.get('simulation_version') != SIMULATION_VERSION:
            return
        self.backup('before-logistics-' + uuid.uuid4().hex[:12])
        engine = Engine(World.from_dict(data))
        self.ensure_logistics(engine)
        engine.world.content_version = CONTENT_VERSION
        engine.event('Logistics and group efficiencies available', 'Logistics companies can provide transport at cost within an ownership group. Product operations now incur delivery costs. Banking and transport benefits can work together; existing assets and balances are preserved.')
        engine.validate()
        self.audit(engine.world)
        engine.world.revision += 1
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute('UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?',
                            (engine.world.revision, json.dumps(engine.world.to_dict()), data['revision']))
        if changed.rowcount != 1:
            raise RuleError('The campaign changed during upgrade. Close the other game window and retry.')
        self.append(db, engine)
        db.commit()

    def migrate_v1(self, db: sqlite3.Connection, version=1) -> None:
        """Upgrade a known v1 save once; keep an immutable pre-migration copy."""
        data=json.loads(db.execute("SELECT data FROM world WHERE id=1").fetchone()[0])
        if data.get("simulation_version")!=version or data.get("content_version")!={1:V1_CONTENT_VERSION,2:V2_CONTENT_VERSION}[version]:
            raise RuleError("This v1 save has unrecognized content. It was not modified.")
        self.backup(("before-v2-" if version==1 else "before-v3-")+uuid.uuid4().hex[:12])
        from .business_rules import BusinessRules
        world=World.from_dict(data)
        engine=Engine(world)
        world.simulation_version=SIMULATION_VERSION
        world.content_version=CONTENT_VERSION
        BusinessRules(engine).initialize()
        from .campaign import Campaign
        Campaign(engine).initialize()
        # A v2 world already has companies, so initialize() will not seed new
        # catalog entries. Make the new industries available on this path too.
        from .domain import BUSINESS_CONTENT, INDUSTRY_CONTENT
        present = {b.industry for b in world.businesses}
        added = {spec['industry'] for spec in INDUSTRY_CONTENT['catalog']}
        for index, spec in enumerate(BUSINESS_CONTENT['catalog']):
            if spec['industry'] in added - present:
                BusinessRules(engine).add_business(index)
                present.add(spec['industry'])
        self.ensure_property_categories(engine)
        self.ensure_expansion(engine)
        self.ensure_storage(engine)
        self.ensure_logistics(engine)
        engine.event("Campaign systems upgraded", "Your existing assets, employees and finances have been preserved. New management and campaign systems are available.")
        engine.validate()
        self.audit(world)
        world.revision+=1
        # The snapshot, event and schema version share the same SQLite transaction.
        db.execute("BEGIN IMMEDIATE")
        changed=db.execute("UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?",(world.revision,json.dumps(world.to_dict()),data["revision"]))
        if changed.rowcount!=1:raise RuleError("The campaign changed during migration; close the other game window and retry.")
        self.append(db,engine)
        db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        db.commit()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def load(self) -> World:
        with self.connection() as db:
            world = World.from_dict(json.loads(db.execute("SELECT data FROM world WHERE id=1").fetchone()[0]))
        if world.simulation_version != SIMULATION_VERSION or world.content_version != CONTENT_VERSION:
            raise RuleError("This save uses different simulation/content versions. Keep the original save; use matching game files or a new save.")
        Engine(world).validate()
        return world

    @staticmethod
    def append(db: sqlite3.Connection, engine: Engine) -> None:
        for p in engine.postings:
            cursor = db.execute("INSERT INTO journal(entity,source,date,memo) VALUES(?,?,?,?)", (p["entity"], p["source"], p["date"], p["memo"]))
            db.executemany("INSERT INTO lines VALUES(?,?,?)", [(cursor.lastrowid, a, v) for a, v in p["lines"].items()])
        for event in engine.events:
            db.execute("INSERT INTO events VALUES(?,?,?)", (event["id"], event["date"], json.dumps(event)))

    def commit(self, engine: Engine, expected_revision: int, command: tuple | None = None) -> None:
        engine.validate()
        engine.world.revision = expected_revision + 1
        with self.connection() as db:
            cursor = db.execute("UPDATE world SET revision=?,data=? WHERE id=1 AND revision=?", (engine.world.revision, json.dumps(engine.world.to_dict()), expected_revision))
            if cursor.rowcount != 1:
                raise RuleError("The save changed elsewhere. Reopen the game before continuing.")
            self.append(db, engine)
            if command:
                db.execute("INSERT INTO commands VALUES(?,?,?)", command)

    def command_result(self, command_id: str, fingerprint: str) -> str | None:
        with self.connection() as db:
            row = db.execute("SELECT fingerprint,result FROM commands WHERE id=?", (command_id,)).fetchone()
        if not row:
            return None
        if row["fingerprint"] != fingerprint:
            raise RuleError("That request identifier was already used for a different action.")
        return row["result"]

    def backup(self, label: str = "checkpoint") -> Path:
        target = self.path.with_name(f"{self.path.stem}.{label}.sqlite3")
        with self.connection() as db, sqlite3.connect(target) as dest:
            db.backup(dest)
        return target

    def report(self, scope: str, since: str, entities=None) -> dict:
        scopes = entities or [scope]
        slots = ",".join("?" for _ in scopes)
        with self.connection() as db:
            rows = db.execute(f"SELECT l.account,SUM(l.amount) amount FROM lines l JOIN journal j ON j.id=l.journal_id WHERE j.entity IN ({slots}) AND j.date>=? GROUP BY l.account", (*scopes, since)).fetchall()
            entries = db.execute(f"SELECT j.id,j.entity,j.date,j.memo,COALESCE(SUM(CASE WHEN l.account='asset:cash' THEN l.amount ELSE 0 END),0) cash FROM journal j JOIN lines l ON l.journal_id=j.id WHERE j.entity IN ({slots}) GROUP BY j.id ORDER BY j.id DESC LIMIT 100", tuple(scopes)).fetchall()
            grouped = {entry["id"]: [] for entry in entries}
            if grouped:
                placeholders = ",".join("?" for _ in grouped)
                for line in db.execute(f"SELECT journal_id,account,amount FROM lines WHERE journal_id IN ({placeholders}) ORDER BY journal_id,account", tuple(grouped)):
                    grouped[line["journal_id"]].append({"account": line["account"], "amount": line["amount"]})
            for_entry = [{**dict(entry), "lines": grouped[entry["id"]]} for entry in entries]
            # Initial endowment is the opening balance, not cash generated by play.
            opening = db.execute(f"SELECT COALESCE(SUM(l.amount),0) FROM lines l JOIN journal j ON j.id=l.journal_id WHERE j.entity IN ({slots}) AND l.account='asset:cash' AND (j.date<? OR (j.entity='personal' AND j.source IN ('opening','scenario-capital')))", (*scopes,since)).fetchone()[0]
            ending = db.execute(f"SELECT COALESCE(SUM(l.amount),0) FROM lines l JOIN journal j ON j.id=l.journal_id WHERE j.entity IN ({slots}) AND l.account='asset:cash'", tuple(scopes)).fetchone()[0]
        accounts = {r["account"]: r["amount"] for r in rows}
        if entities:
            from .business_views import eliminated
            accounts = {k:v for k,v in accounts.items() if not eliminated(k,entities)}
        income = -sum(v for k, v in accounts.items() if k.startswith("income:") and (not entities or k!="income:dividends"))
        expense = sum(v for k, v in accounts.items() if k.startswith("expense:"))
        return dict(income=income, expense=expense, profit=income - expense, cash_flow=ending-opening, cash_opening=opening, cash_closing=ending, entries=for_entry)

    def audit(self, world: World) -> None:
        with self.connection() as db:
            unbalanced = db.execute("SELECT journal_id FROM lines GROUP BY journal_id HAVING SUM(amount)<>0").fetchall()
            if unbalanced:
                raise RuleError("The journal has unbalanced entries.")
            for entity, balances in world.accounts.items():
                rows = db.execute("SELECT l.account,SUM(l.amount) amount FROM lines l JOIN journal j ON j.id=l.journal_id WHERE j.entity=? GROUP BY l.account", (entity,)).fetchall()
                actual = {row["account"]: row["amount"] for row in rows}
                if actual != balances:
                    raise RuleError("The saved balances do not match the journal.")

