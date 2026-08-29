# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from repositories import spend_repo
from services import spend_service


async def test_record_spend_inserts_one_row_per_resource(fake_db):
    fake_db.fetch_queue.append([{'id': 1, 'name': 'CM'}, {'id': 2, 'name': 'EL'}])
    await spend_repo.record_spend(10, {'CM': 100, 'EL': 50}, spend_service.SPEND)
    inserts = [e for e in fake_db.executed if e[0] == 'execute']
    assert len(inserts) == 2


async def test_record_spend_skips_zero_and_negative_amounts(fake_db):
    fake_db.fetch_queue.append([{'id': 1, 'name': 'CM'}])
    await spend_repo.record_spend(10, {'CM': 0}, spend_service.SPEND)
    inserts = [e for e in fake_db.executed if e[0] == 'execute']
    assert len(inserts) == 0


async def test_record_spend_noop_for_empty_resources(fake_db):
    await spend_repo.record_spend(10, {}, spend_service.SPEND)
    assert fake_db.executed == []


async def test_service_record_spend_swallows_db_errors(fake_db, monkeypatch):
    async def raise_error(faction_id, resources, direction):
        raise RuntimeError("db down")

    monkeypatch.setattr(spend_repo, "record_spend", raise_error)
    await spend_service.record_spend(10, {'CM': 500}, spend_service.SPEND)


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    async def fetch(self, query, *args):
        self.executed.append((query, args))
        return self._rows

    def transaction(self):
        return _FakeTxCtx()


class _FakeTxCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConnCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_spend_accumulates_within_a_cycle():
    from dtos.spend import WeeklySpendTotal

    a = WeeklySpendTotal(resource_name='CM', amount=100)
    b = WeeklySpendTotal(resource_name='CM', amount=250)
    assert a.amount + b.amount == 350


async def test_reset_and_report_deletes_rows_and_returns_totals(monkeypatch):
    from database.db_manager import db

    rows = [
        {'resource_name': 'CM', 'amount': 600},
        {'resource_name': 'ER', 'amount': -200},
    ]
    conn = _FakeConn(rows)
    monkeypatch.setattr(db, "get_connection", lambda: _FakeConnCtx(conn))

    reported = []

    async def on_reset(totals):
        reported.append(totals)
        return True

    totals = await spend_repo.reset_and_report(on_reset)

    assert len(conn.executed) == 1
    assert "DELETE FROM faction_weekly_spend" in conn.executed[0][0]
    assert totals[0].resource_name == 'CM'
    assert totals[0].amount == 600
    assert totals[1].resource_name == 'ER'
    assert totals[1].amount == -200
    assert reported == [totals]


async def test_reset_and_report_raises_when_callback_fails(monkeypatch):
    from database.db_manager import db

    conn = _FakeConn([{'resource_name': 'CM', 'amount': 100}])
    monkeypatch.setattr(db, "get_connection", lambda: _FakeConnCtx(conn))

    async def on_reset(totals):
        return False

    with pytest.raises(RuntimeError):
        await spend_repo.reset_and_report(on_reset)


async def test_reset_and_report_empty_when_no_spend(monkeypatch):
    from database.db_manager import db

    conn = _FakeConn([])
    monkeypatch.setattr(db, "get_connection", lambda: _FakeConnCtx(conn))

    async def on_reset(totals):
        return True

    totals = await spend_repo.reset_and_report(on_reset)
    assert totals == []


async def test_refund_offsets_spend_via_upsert(fake_db):
    fake_db.fetch_queue.append([{'id': 1, 'name': 'CM'}])
    await spend_repo.record_spend(10, {'CM': 1000}, spend_service.SPEND)
    fake_db.fetch_queue.append([{'id': 1, 'name': 'CM'}])
    await spend_repo.record_spend(10, {'CM': 400}, spend_service.REFUND)

    inserts = [e for e in fake_db.executed if e[0] == 'execute']
    assert len(inserts) == 2
    assert inserts[0][2][2] == spend_service.SPEND
    assert inserts[0][2][3] == 1000
    assert inserts[1][2][2] == spend_service.REFUND
    assert inserts[1][2][3] == 400


async def test_recruit_infantry_records_spend(monkeypatch):
    from services import fleet_service
    from repositories import fleet_repo

    recorded = []

    async def fake_record_spend(faction_id, resources, direction):
        recorded.append((faction_id, resources, direction))

    async def fake_get_resource_id_by_name(conn, name):
        return {'Population': 1, 'CM': 2}[name]

    async def fake_get_local_treasury_total(conn, faction_id, resource_id):
        return 10_000

    async def fake_deduct_local_proportional(conn, faction_id, resource_id, available, amount):
        return None

    async def fake_insert_military_recruitment(conn, faction_id, amount, completion, unit_id):
        return 42

    class _FleetFakeConn:
        pass

    class _FleetFakeConnCtx:
        async def __aenter__(self):
            return _FleetFakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FleetFakeTxCtx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(fleet_repo, "get_connection", lambda: _FleetFakeConnCtx())
    monkeypatch.setattr(_FleetFakeConn, "transaction", lambda self: _FleetFakeTxCtx(), raising=False)
    monkeypatch.setattr(fleet_repo, "get_resource_id_by_name", fake_get_resource_id_by_name)
    monkeypatch.setattr(fleet_repo, "get_local_treasury_total", fake_get_local_treasury_total)
    monkeypatch.setattr(fleet_service, "deduct_local_proportional", fake_deduct_local_proportional)
    monkeypatch.setattr(fleet_repo, "insert_military_recruitment", fake_insert_military_recruitment)
    monkeypatch.setattr(fleet_service.spend_service, "record_spend", fake_record_spend)

    rec_id = await fleet_service.recruit_infantry_to_unit(
        unit_id=1, faction_id=10, amount=100, costs={'CM': 5}, completion=None
    )

    assert rec_id == 42
    assert len(recorded) == 1
    faction_id, resources, direction = recorded[0]
    assert faction_id == 10
    assert resources == {'CM': 500, 'Population': 100}
    assert direction == fleet_service.spend_service.SPEND


async def test_weekly_spend_report_computes_net_change(monkeypatch):
    from services import background_tasks
    from dtos.spend import WeeklySpendTotal

    class FakeChannel:
        def __init__(self):
            self.sent = []

        async def send(self, embed=None):
            self.sent.append(embed)

    fake_channel = FakeChannel()

    async def fake_find_channel_by_name(name):
        return fake_channel

    async def fake_reset_snapshot_and_report(on_reset):
        totals = [WeeklySpendTotal(resource_name='CM', amount=300)]
        ok = await on_reset(totals)
        assert ok
        return totals

    monkeypatch.setattr(background_tasks, "_find_channel_by_name", fake_find_channel_by_name)
    monkeypatch.setattr(
        "services.spend_service.reset_snapshot_and_report", fake_reset_snapshot_and_report
    )

    await background_tasks.post_weekly_spend_report(
        resources_earned={'CM': 1000, 'ER': 50}, population_change=-20
    )

    assert len(fake_channel.sent) == 1
    description = fake_channel.sent[0].description
    assert "Total resources earned: 1 050" in description
    assert "Population change: -20" in description
    assert "Total resources spent: 300" in description
    assert "Change: +750" in description


async def test_weekly_spend_report_skips_when_channel_missing(monkeypatch):
    from services import background_tasks

    async def fake_find_channel_by_name(name):
        return None

    called = []

    async def fake_reset_snapshot_and_report(on_reset):
        called.append(True)
        return []

    monkeypatch.setattr(background_tasks, "_find_channel_by_name", fake_find_channel_by_name)
    monkeypatch.setattr(
        "services.spend_service.reset_snapshot_and_report", fake_reset_snapshot_and_report
    )

    await background_tasks.post_weekly_spend_report(resources_earned={}, population_change=0)

    assert called == []


async def test_weekly_spend_report_preserves_data_when_post_fails(monkeypatch):
    from services import background_tasks
    from dtos.spend import WeeklySpendTotal

    class FailingChannel:
        async def send(self, embed=None):
            raise RuntimeError("discord down")

    async def fake_find_channel_by_name(name):
        return FailingChannel()

    reset_committed = []

    async def fake_reset_snapshot_and_report(on_reset):
        totals = [WeeklySpendTotal(resource_name='CM', amount=300)]
        ok = await on_reset(totals)
        if not ok:
            raise RuntimeError("rolled back")
        reset_committed.append(True)
        return totals

    monkeypatch.setattr(background_tasks, "_find_channel_by_name", fake_find_channel_by_name)
    monkeypatch.setattr(
        "services.spend_service.reset_snapshot_and_report", fake_reset_snapshot_and_report
    )

    await background_tasks.post_weekly_spend_report(
        resources_earned={'CM': 1000}, population_change=0
    )

    assert reset_committed == []


async def test_multi_cycle_catch_up_reports_and_resets_each_cycle_independently(monkeypatch):
    from services import background_tasks
    from dtos.spend import WeeklySpendTotal

    class FakeChannel:
        def __init__(self):
            self.sent = []

        async def send(self, embed=None):
            self.sent.append(embed)

    fake_channel = FakeChannel()

    async def fake_find_channel_by_name(name):
        return fake_channel

    cycle_data = [
        [WeeklySpendTotal(resource_name='CM', amount=100)],
        [WeeklySpendTotal(resource_name='CM', amount=50)],
    ]
    call_count = {'n': 0}

    async def fake_reset_snapshot_and_report(on_reset):
        totals = cycle_data[call_count['n']]
        call_count['n'] += 1
        ok = await on_reset(totals)
        assert ok
        return totals

    monkeypatch.setattr(background_tasks, "_find_channel_by_name", fake_find_channel_by_name)
    monkeypatch.setattr(
        "services.spend_service.reset_snapshot_and_report", fake_reset_snapshot_and_report
    )

    await background_tasks.post_weekly_spend_report(resources_earned={'CM': 500}, population_change=0)
    await background_tasks.post_weekly_spend_report(resources_earned={'CM': 200}, population_change=0)

    assert call_count['n'] == 2
    assert len(fake_channel.sent) == 2
    assert "Total resources spent: 100" in fake_channel.sent[0].description
    assert "Total resources spent: 50" in fake_channel.sent[1].description
