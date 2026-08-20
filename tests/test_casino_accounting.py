import pytest

from services import casino_service


class FakeConn:
    def __init__(self, pool_amount, floor, faction_amount):
        self.pool = pool_amount
        self.floor = floor
        self.faction = faction_amount
        self.res_id = 7

    async def fetchval(self, query, *args):
        if "FROM resources WHERE name" in query:
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
            self.faction += args[2]


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


class FakeTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _install(monkeypatch, conn):
    conn.transaction = lambda: FakeTx()
    monkeypatch.setattr(casino_service, 'db', FakeDB(conn))


@pytest.mark.asyncio
@pytest.mark.parametrize("multiplier", [0.0, 1.0, 2.0, 5.0])
async def test_settle_bet_conserves_value(monkeypatch, multiplier):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    before_total = conn.pool + conn.faction

    result = await casino_service.settle_bet(1, None, 'ER', 1000, multiplier)

    after_total = conn.pool + conn.faction
    assert after_total == before_total, "value created or destroyed"
    assert conn.pool >= 0
    assert result['net'] == result['payout'] - result['wager']


@pytest.mark.asyncio
async def test_settle_bet_loss_grows_pool(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    pool_before = conn.pool
    await casino_service.settle_bet(1, None, 'ER', 1000, 0.0)
    assert conn.pool == pool_before + 1000


@pytest.mark.asyncio
async def test_settle_bet_push_is_pool_neutral(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    pool_before, faction_before = conn.pool, conn.faction
    await casino_service.settle_bet(1, None, 'ER', 1000, 1.0)
    assert conn.pool == pool_before
    assert conn.faction == faction_before


@pytest.mark.asyncio
async def test_settle_bet_win_costs_pool_only_net(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    pool_before = conn.pool
    await casino_service.settle_bet(1, None, 'ER', 1000, 3.0)
    assert conn.pool == pool_before - 2000


@pytest.mark.asyncio
async def test_chicken_open_then_crash_conserves(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    before_total = conn.pool + conn.faction
    opened = await casino_service.open_chicken_round(1, None, 'ER', 1000)
    await casino_service.close_chicken_round_crash('ER', opened['res_id'], 1000)
    assert conn.pool + conn.faction == before_total
    assert conn.pool == 10_000_000 + 1000


@pytest.mark.asyncio
async def test_chicken_open_then_cashout_conserves(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    before_total = conn.pool + conn.faction
    opened = await casino_service.open_chicken_round(1, None, 'ER', 1000)
    await casino_service.close_chicken_round_cashout(1, None, 'ER', opened['res_id'], 1000, 2.0)
    assert conn.pool + conn.faction == before_total
    assert conn.pool == 10_000_000 - 1000


@pytest.mark.asyncio
async def test_chicken_open_then_refund_is_neutral(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    pool_before, faction_before = conn.pool, conn.faction
    opened = await casino_service.open_chicken_round(1, None, 'ER', 1000)
    await casino_service.close_chicken_round_refund(1, None, 'ER', opened['res_id'], 1000)
    assert conn.pool == pool_before
    assert conn.faction == faction_before
