from __future__ import annotations

import copy
import json
import sqlite3
import threading
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from economic_simulation.application import Game
from economic_simulation.desktop import SaveLock
from economic_simulation.domain import Engine, RuleError, World, calendar_target, daily_share, new_game
from economic_simulation.persistence import Store
from economic_simulation.web import create_app


@pytest.fixture
def game(tmp_path):
    game = Game(tmp_path / "test.sqlite3")
    yield game
    game.close()


def act(game, action, **args):
    command_id = f"test-command-{game.world.revision}-{action}"
    return game.execute(action, args, game.world.revision, command_id)


def step(game, count=1):
    for _ in range(count):
        engine = Engine(copy.deepcopy(game.world))
        engine.advance_day()
        game.store.commit(engine, game.world.revision)
        game.world = engine.world


def test_seed_and_calendar():
    assert new_game(123).world.to_dict() == new_game(123).world.to_dict()
    assert new_game(123).world.to_dict() != new_game(124).world.to_dict()
    assert calendar_target(date(2028, 1, 31), "month") == date(2028, 2, 29)
    assert calendar_target(date(2028, 2, 29), "year") == date(2029, 2, 28)
    for year in (2027, 2028):
        for month in range(1, 13):
            start = date(year, month, 1)
            end = calendar_target(start, "month")
            assert sum(daily_share(123457, start + timedelta(days=i)) for i in range((end-start).days)) == 123457


def test_invalid_purchase_is_atomic(game):
    act(game, "create_holding_company", name="Your property company")
    before = game.world.to_dict()
    with pytest.raises(RuleError, match="enough cash"):
        act(game, "buy", property_id=game.world.properties[0].id, entity="company")
    assert game.world.to_dict() == before
    assert game.store.load().to_dict() == json.loads(json.dumps(before))
    game.store.audit(game.world)


def test_capital_not_profit_and_no_double_counting(game):
    before = game.view()
    act(game,'create_holding_company',name='Your property company')
    act(game, "invest", amount=10_000_000)
    assert game.view()["total_wealth"] == before["total_wealth"]
    assert game.view()["lifetime_profit"] == 0
    assert game.view("company")["lifetime_profit"] == 0
    assert game.world.cash("company") == 10_000_000
    act(game, "withdraw", amount=2_000_000)
    assert game.world.cash("personal") == 27_000_000
    snapshot = game.world.to_dict()
    with pytest.raises(RuleError):
        act(game, "withdraw", amount=9_000_000)
    assert game.world.to_dict() == snapshot
    game.store.audit(game.world)


def test_buy_renovate_sell_reconciles(game):
    pid = game.world.properties[0].id
    act(game, "buy", property_id=pid)
    p = Engine(game.world).owned(pid)
    original_condition = p.condition
    assert game.view()["lifetime_profit"] == 0
    act(game, "rehabilitate", property_id=pid)
    p = Engine(game.world).owned(pid)
    assert p.condition == original_condition
    basis = p.basis
    due = p.due
    step(game, (date.fromisoformat(due) - date.fromisoformat(game.world.date)).days)
    p = Engine(game.world).owned(pid)
    assert p.condition == original_condition + 35 and p.status == "vacant"
    q = Engine(game.world).quote("sell", pid)
    cash_before = game.world.cash("personal")
    act(game, "sell", property_id=pid)
    assert game.world.cash("personal") == cash_before
    p = Engine(game.world).owned(pid)
    step(game, (date.fromisoformat(p.due) - date.fromisoformat(game.world.date)).days)
    p = Engine(game.world).get_property(pid)
    assert p.status == "sold" and p.owner is None
    assert game.world.accounts["personal"]["asset:property"] == 0
    expected_profit = q["total"] - basis - game.world.accounts["personal"]["expense:holding"] - game.world.accounts["personal"].get("expense:property_tax",0)
    assert game.view()["lifetime_profit"] == expected_profit
    assert game.world.cash("personal") == 35_000_000 + expected_profit
    game.store.audit(game.world)


def test_rent_only_after_move_in_and_lease_constraints(game):
    pid = game.world.properties[3].id
    act(game, "buy", property_id=pid)
    act(game, "rent", property_id=pid)
    p = Engine(game.world).owned(pid)
    days = (date.fromisoformat(p.due) - date.fromisoformat(game.world.date)).days
    step(game, days - 1)
    assert game.world.accounts["personal"].get("income:rent", 0) == 0
    step(game)
    p = Engine(game.world).owned(pid)
    assert p.status == "rented"
    assert -game.world.accounts["personal"]["income:rent"] == daily_share(p.rent, date.fromisoformat(game.world.date))
    for action in ("sell", "refresh", "cancel_rental"):
        with pytest.raises(RuleError):
            act(game, action, property_id=pid)
    game.store.audit(game.world)


def test_skip_and_daily_steps_identical_and_reload(tmp_path):
    a, b = Game(tmp_path / "a.sqlite3"), Game(tmp_path / "b.sqlite3")
    try:
        for game in (a, b):
            act(game, "buy", property_id=game.world.properties[3].id)
        # A single background year and the same daily pipeline; compare economic state excluding command revision.
        act(a, "advance", period="year")
        a.worker.join(20)
        assert not a.progress["running"] and a.progress["completed"] == 365
        step(b, 120)
        b = Game(tmp_path / "b.sqlite3")
        step(b, 245)
        da, db = a.world.to_dict(), b.world.to_dict()
        da.pop("revision"); db.pop("revision")
        assert json.loads(json.dumps(da)) == json.loads(json.dumps(db))
        for game in (a, b): game.store.audit(game.world)
    finally:
        a.close(); b.close()


def test_duplicate_command_survives_reload(game):
    pid = game.world.properties[0].id
    result = game.execute("buy", {"property_id": pid}, 0, "duplicate-buy-001")
    revision = game.world.revision
    reopened = Game(game.store.path)
    assert reopened.execute("buy", {"property_id": pid}, 0, "duplicate-buy-001") == result
    assert reopened.world.revision == revision
    with pytest.raises(RuleError, match="different action"):
        reopened.execute("buy", {"property_id": "p2"}, revision, "duplicate-buy-001")
    with pytest.raises(RuleError, match="out of date"):
        reopened.execute("buy", {"property_id": "p2"}, 0, "another-buy-001")


def test_skip_stops_at_completion(game):
    act(game, 'settings', pause_routine=True)
    pid = game.world.properties[0].id
    act(game, "buy", property_id=pid)
    act(game, "refresh", property_id=pid)
    due = Engine(game.world).owned(pid).due
    act(game, "advance", period="year")
    game.worker.join(10)
    assert game.world.date == due
    assert not game.progress["running"]
    assert "important event" in game.progress["message"]
    assert game.store.path.with_name("test.checkpoint.sqlite3").exists()


def test_cancel_leaves_committed_save(game, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = Engine.advance_day
    def controlled_day(engine):
        entered.set()
        release.wait(3)
        return original(engine)
    monkeypatch.setattr(Engine, "advance_day", controlled_day)
    act(game, "advance", period="year")
    assert entered.wait(3)
    game.stop()
    release.set()
    game.worker.join(10)
    assert game.progress["completed"] == 1
    assert game.world.date == "2026-01-02"
    assert json.loads(json.dumps(game.world.to_dict())) == game.store.load().to_dict()
    game.store.audit(game.world)


def test_database_rollback_on_duplicate_posting(game):
    before = game.world.to_dict()
    engine = Engine(copy.deepcopy(game.world))
    engine.post("personal", "opening", "Duplicate opening", {"asset:cash": 100, "equity:capital": -100})
    with pytest.raises(sqlite3.IntegrityError):
        game.store.commit(engine, game.world.revision)
    assert game.store.load().to_dict() == json.loads(json.dumps(before))
    game.store.audit(game.world)


def test_backup_and_newer_save_rejected(game, tmp_path):
    backup = game.store.backup("test-backup")
    assert Store(backup).load().date == game.world.date
    with sqlite3.connect(backup) as db: db.execute("PRAGMA user_version=999")
    original = backup.read_bytes()
    with pytest.raises(RuleError, match="not supported"):
        Store(backup)
    assert backup.read_bytes() == original


def test_one_process_per_save(tmp_path):
    lock = SaveLock(tmp_path / "campaign.lock")
    try:
        with pytest.raises(RuleError, match="already open"):
            SaveLock(tmp_path / "campaign.lock")
    finally: lock.close()
    reopened = SaveLock(tmp_path / "campaign.lock")
    reopened.close()


def test_routes_security_and_templates(game):
    token = "test-session-token"
    client = TestClient(create_app(game, token, "testserver"))
    assert client.get("/").status_code == 403
    assert client.get("/?key=" + token).status_code == 200
    for page in ("overview", "portfolio", "market", "owner", "finance", "activity"):
        response = client.get("/", params={"page": page})
        assert response.status_code == 200
        assert "Empire Manager" in response.text
        assert "Content-Security-Policy" in response.headers
    payload = dict(action="buy", args={"property_id": game.world.properties[0].id}, revision=0, command_id="web-buy-0001")
    headers = {"Origin": "http://testserver", "X-Game-Token": token}
    assert client.post("/api/command", json=payload).status_code == 403
    assert client.post("/api/command", json=payload, headers={**headers, "Origin": "https://foreign.example"}).status_code == 403
    assert client.get("/", headers={"Host":"foreign.example"}).status_code == 403
    assert client.post("/api/command", json=payload, headers=headers).status_code == 200
    assert client.post("/api/command", json=payload, headers=headers).status_code == 200
    assert client.get("/", params={"page":"property", "property_id":payload["args"]["property_id"]}).status_code == 200
    assert client.get("/static/../domain.py").status_code != 200
    act(game, "profile", name="<script>alert(1)</script>")
    response = client.get("/?page=owner")
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_leap_year_rent_and_age(tmp_path):
    game = Game(tmp_path / "leap.sqlite3")
    engine = Engine(copy.deepcopy(game.world))
    engine.world.date = "2028-01-01"
    game.store.commit(engine, game.world.revision)
    game.world = engine.world
    pid = game.world.properties[3].id
    act(game, "buy", property_id=pid)
    act(game, "rent", property_id=pid)
    step(game, 30)
    before = game.world.accounts["personal"]["income:rent"]
    rent = Engine(game.world).owned(pid).rent
    step(game, 29)
    assert game.world.date == "2028-02-29"
    assert before - game.world.accounts["personal"]["income:rent"] == rent
    assert game.view()["age"] == 32
    game.store.audit(game.world)


def test_rental_withdrawal_and_expiry(game):
    pid = game.world.properties[3].id
    act(game, "buy", property_id=pid)
    act(game, "rent", property_id=pid)
    act(game, "cancel_rental", property_id=pid)
    step(game, 10)
    assert Engine(game.world).owned(pid).status == "vacant"
    act(game, "rent", property_id=pid)
    step(game, 7)
    end = Engine(game.world).owned(pid).lease_end
    step(game, (date.fromisoformat(end) - date.fromisoformat(game.world.date)).days)
    assert Engine(game.world).owned(pid).status == "vacant"
    assert game.view()["monthly_rent"] == 0
    act(game, "sell", property_id=pid)
    game.store.audit(game.world)


def test_unpaid_costs_accrue_without_negative_cash(game):
    act(game, 'settings', financial_pause_threshold=0)
    pid = game.world.properties[0].id
    q = Engine(game.world).quote("buy", pid)
    act(game,'create_holding_company',name='Your property company')
    act(game, "invest", amount=q["total"])
    act(game, "buy", property_id=pid, entity="company")
    assert game.world.cash("company") == 0
    act(game, "advance", period="year")
    game.worker.join(10)
    assert game.progress["completed"] == 1
    assert game.view("company")["payable"] > 0
    assert game.world.cash("company") == 0
    act(game, "invest", amount=100_000)
    step(game)
    assert game.view("company")["payable"] == 0
    game.store.audit(game.world)


def test_rental_rng_continues_after_reload(game):
    pid = game.world.properties[3].id
    act(game, "buy", property_id=pid)
    a = Engine(copy.deepcopy(game.world))
    b = Engine(game.store.load())
    a.action("rent", {"property_id": pid}, "seeded-rental")
    b.action("rent", {"property_id": pid}, "seeded-rental")
    for _ in range(8):
        a.advance_day(); b.advance_day()
    assert json.loads(json.dumps(a.world.to_dict())) == json.loads(json.dumps(b.world.to_dict()))


def test_http_money_input_validation(game):
    client = TestClient(create_app(game, "money-token", "testserver"))
    client.get("/?key=money-token")
    headers = {"Origin":"http://testserver", "X-Game-Token":"money-token"}
    for amount in ("NaN", "Infinity", "-1", "0", "1.001", "not money"):
        response = client.post("/api/command", headers=headers, json={"action":"invest", "args":{"amount_dollars":amount}, "revision":game.world.revision, "command_id":"invalid-money-test"})
        assert response.status_code == 409
    assert game.world.cash("company") == 0
