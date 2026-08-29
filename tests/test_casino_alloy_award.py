# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from services import casino_service
from repositories import casino_repo


def test_is_high_stakes_exactly_at_threshold():
    assert casino_service.is_high_stakes(wager=50, table_max=100) is True


def test_is_high_stakes_just_below_threshold():
    assert casino_service.is_high_stakes(wager=49, table_max=100) is False


def test_is_high_stakes_well_above_threshold():
    assert casino_service.is_high_stakes(wager=100, table_max=100) is True


def test_is_high_stakes_zero_table_max_is_never_high_stakes():
    assert casino_service.is_high_stakes(wager=1, table_max=0) is False


class FakeConn:
    def __init__(self, faction_amount=0, alloys_id=99, fail=False):
        self.faction = faction_amount
        self.alloys_id = alloys_id
        self.fail = fail

    async def fetchval(self, query, *args):
        if "FROM resources WHERE name" in query:
            if self.fail:
                raise RuntimeError("db unavailable")
            return self.alloys_id
        return self.faction

    async def execute(self, query, *args):
        if self.fail:
            raise RuntimeError("db unavailable")
        if "INSERT INTO faction_treasury" in query:
            self.faction += args[2]
        return "OK"


class FakeDB:
    def __init__(self, conn):
        self.conn = conn

    def get_connection(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        return Ctx()


def _install(monkeypatch, conn):
    monkeypatch.setattr(casino_repo, 'db', FakeDB(conn))


@pytest.mark.asyncio
async def test_award_alloy_below_threshold_awards_nothing(monkeypatch):
    conn = FakeConn()
    _install(monkeypatch, conn)

    amount = await casino_service.award_alloy_if_qualified(
        faction_id=1, wager=49, table_max=100, won=True, eligible=True
    )

    assert amount == 0
    assert conn.faction == 0


@pytest.mark.asyncio
async def test_award_alloy_high_stakes_win_awards_within_range(monkeypatch):
    conn = FakeConn()
    _install(monkeypatch, conn)

    amount = await casino_service.award_alloy_if_qualified(
        faction_id=1, wager=100, table_max=100, won=True, eligible=True
    )

    assert casino_service.ALLOY_AWARD_MIN <= amount <= casino_service.ALLOY_AWARD_MAX
    assert conn.faction == amount


@pytest.mark.asyncio
async def test_award_alloy_deterministic_amount_reaches_faction(monkeypatch):
    conn = FakeConn()
    _install(monkeypatch, conn)
    monkeypatch.setattr(casino_service.random, 'randint', lambda lo, hi: 3)

    amount = await casino_service.award_alloy_if_qualified(
        faction_id=1, wager=100, table_max=100, won=True, eligible=True
    )

    assert amount == 3
    assert conn.faction == 3


@pytest.mark.asyncio
async def test_award_alloy_loss_awards_nothing_even_at_high_stakes(monkeypatch):
    conn = FakeConn()
    _install(monkeypatch, conn)

    amount = await casino_service.award_alloy_if_qualified(
        faction_id=1, wager=100, table_max=100, won=False, eligible=True
    )

    assert amount == 0
    assert conn.faction == 0


@pytest.mark.asyncio
async def test_award_alloy_ineligible_bet_type_awards_nothing_even_at_high_stakes(monkeypatch):
    conn = FakeConn()
    _install(monkeypatch, conn)

    amount = await casino_service.award_alloy_if_qualified(
        faction_id=1, wager=100, table_max=100, won=True, eligible=False
    )

    assert amount == 0
    assert conn.faction == 0


@pytest.mark.asyncio
async def test_award_alloy_failed_credit_does_not_raise(monkeypatch):
    conn = FakeConn(fail=True)
    _install(monkeypatch, conn)

    amount = await casino_service.award_alloy_if_qualified(
        faction_id=1, wager=100, table_max=100, won=True, eligible=True
    )

    assert amount == 0


@pytest.mark.asyncio
async def test_award_alloy_missing_alloys_resource_awards_nothing(monkeypatch):
    conn = FakeConn(alloys_id=None)
    _install(monkeypatch, conn)

    amount = await casino_service.award_alloy_if_qualified(
        faction_id=1, wager=100, table_max=100, won=True, eligible=True
    )

    assert amount == 0


class SettleFakeConn:
    def __init__(self, pool_amount, floor, faction_amount, alloys_id=99):
        self.pool = pool_amount
        self.floor = floor
        self.faction = faction_amount
        self.res_id = 7
        self.alloys_id = alloys_id
        self.alloys_credited = 0

    async def fetchval(self, query, *args):
        if "FROM resources WHERE name" in query:
            if args and args[0] == 'Alloys':
                return self.alloys_id
            return self.res_id
        return self.faction

    async def fetchrow(self, query, *args):
        if "casino_pool" in query:
            return {'resource_id': self.res_id, 'amount': self.pool, 'floor_amount': self.floor}
        return None

    async def execute(self, query, *args):
        if "casino_pool SET amount = amount +" in query:
            self.pool += args[1]
        elif "casino_pool SET amount = amount -" in query:
            self.pool -= args[1]
        elif "faction_treasury SET amount = amount -" in query:
            self.faction -= args[2]
        elif "INSERT INTO faction_treasury" in query:
            if args[1] == self.alloys_id:
                self.alloys_credited += args[2]
            self.faction += args[2]


class SettleFakeDB:
    def __init__(self, conn):
        self.conn = conn

    def get_connection(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        return Ctx()


class SettleFakeTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _install_settle(monkeypatch, conn):
    conn.transaction = lambda: SettleFakeTx()
    monkeypatch.setattr(casino_repo, 'db', SettleFakeDB(conn))


@pytest.mark.asyncio
async def test_settle_bet_high_stakes_win_awards_alloy_via_settlement(monkeypatch):
    conn = SettleFakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install_settle(monkeypatch, conn)
    monkeypatch.setattr(casino_service.random, 'randint', lambda lo, hi: 2)

    table_max = casino_service.table_max_for_pool(conn.pool, conn.floor)
    high_stakes_wager = table_max

    result = await casino_service.settle_bet(1, None, 'ER', high_stakes_wager, 2.0)

    assert result['alloys_awarded'] == 2
    assert conn.alloys_credited == 2


@pytest.mark.asyncio
async def test_settle_bet_low_stakes_win_awards_no_alloy(monkeypatch):
    conn = SettleFakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install_settle(monkeypatch, conn)

    result = await casino_service.settle_bet(1, None, 'ER', 1000, 2.0)

    assert result['alloys_awarded'] == 0
    assert conn.alloys_credited == 0


@pytest.mark.asyncio
async def test_settle_bet_roulette_non_straight_high_stakes_win_awards_no_alloy(monkeypatch):
    conn = SettleFakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install_settle(monkeypatch, conn)

    table_max = casino_service.table_max_for_pool(conn.pool, conn.floor)
    high_stakes_wager = table_max

    result = await casino_service.settle_bet(1, None, 'ER', high_stakes_wager, 2.0, alloy_eligible=False)

    assert result['alloys_awarded'] == 0
    assert conn.alloys_credited == 0


@pytest.mark.asyncio
async def test_settle_bet_roulette_straight_high_stakes_win_awards_alloy(monkeypatch):
    conn = SettleFakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install_settle(monkeypatch, conn)
    monkeypatch.setattr(casino_service.random, 'randint', lambda lo, hi: 1)

    table_max = casino_service.table_max_for_pool(conn.pool, conn.floor)
    high_stakes_wager = table_max

    result = await casino_service.settle_bet(1, None, 'ER', high_stakes_wager, 35.0, alloy_eligible=True)

    assert result['alloys_awarded'] == 1
    assert conn.alloys_credited == 1


@pytest.mark.asyncio
async def test_chicken_cashout_before_third_jump_awards_no_alloy(monkeypatch):
    conn = SettleFakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install_settle(monkeypatch, conn)

    table_max = casino_service.table_max_for_pool(conn.pool, conn.floor)
    opened = await casino_service.open_chicken_round(1, None, 'ER', table_max)
    result = await casino_service.close_chicken_round_cashout(
        1, None, 'ER', opened['res_id'], table_max, 2.0,
        table_max=opened['table_max'], alloy_eligible=False,
    )

    assert result['alloys_awarded'] == 0
    assert conn.alloys_credited == 0


@pytest.mark.asyncio
async def test_chicken_cashout_from_third_jump_awards_alloy(monkeypatch):
    conn = SettleFakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install_settle(monkeypatch, conn)
    monkeypatch.setattr(casino_service.random, 'randint', lambda lo, hi: 4)

    table_max = casino_service.table_max_for_pool(conn.pool, conn.floor)
    opened = await casino_service.open_chicken_round(1, None, 'ER', table_max)
    result = await casino_service.close_chicken_round_cashout(
        1, None, 'ER', opened['res_id'], table_max, 2.0,
        table_max=opened['table_max'], alloy_eligible=True,
    )

    assert result['alloys_awarded'] == 4
    assert conn.alloys_credited == 4
