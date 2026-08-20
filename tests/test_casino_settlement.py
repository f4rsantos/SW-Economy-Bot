import pytest
from database.db_manager import db
import services.casino_service as casino_service

RESOURCE_IDS = {'ER': 1, 'CM': 2, 'EL': 3, 'CS': 4}
ID_TO_RESOURCE = {v: k for k, v in RESOURCE_IDS.items()}


class FakeConn:
    def __init__(self, state):
        self.state = state

    async def fetchrow(self, query, *args):
        if "FROM casino_pool" in query:
            resource_id = args[0]
            amount = self.state['pools'][resource_id]
            return {'resource_id': resource_id, 'amount': amount, 'floor_amount': self.state['floors'][resource_id]}
        return None

    async def fetchval(self, query, *args):
        if "SELECT id FROM resources WHERE name" in query:
            return RESOURCE_IDS.get(args[0])
        if "FROM local_treasury" in query:
            return self.state['faction_local'].get(args[2] if len(args) > 2 else None, 0)
        if "FROM faction_treasury" in query:
            return self.state['faction_global']
        return None

    async def execute(self, query, *args):
        if "UPDATE casino_pool SET amount = amount +" in query:
            resource_id, amount = args
            self.state['pools'][resource_id] += amount
        elif "UPDATE casino_pool SET amount = amount -" in query:
            resource_id, amount = args
            self.state['pools'][resource_id] -= amount
        elif "UPDATE faction_treasury SET amount = amount -" in query:
            self.state['faction_global'] -= args[2]
        elif "INSERT INTO faction_treasury" in query:
            self.state['faction_global'] += args[2]
        elif "UPDATE local_treasury SET amount = amount -" in query:
            self.state['faction_global'] -= args[3]
        elif "INSERT INTO local_treasury" in query:
            self.state['faction_global'] += args[3]
        return "OK"

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class FakeAcquireCtx:
    def __init__(self, state):
        self.state = state

    async def __aenter__(self):
        return FakeConn(self.state)

    async def __aexit__(self, *a):
        return False


@pytest.fixture
def fake_conn_state(monkeypatch):
    state = {
        'pools': {
            RESOURCE_IDS['ER']: 50_000_000_000,
            RESOURCE_IDS['CM']: 100_000,
            RESOURCE_IDS['EL']: 100_000,
            RESOURCE_IDS['CS']: 100_000,
        },
        'floors': {
            RESOURCE_IDS['ER']: 50_000_000_000,
            RESOURCE_IDS['CM']: 250_000,
            RESOURCE_IDS['EL']: 250_000,
            RESOURCE_IDS['CS']: 250_000,
        },
        'faction_global': 10_000_000_000,
        'faction_local': {},
    }
    monkeypatch.setattr(db, "get_connection", lambda: FakeAcquireCtx(state))
    return state


def _pool(state, resource: str) -> int:
    return state['pools'][RESOURCE_IDS[resource]]


@pytest.mark.asyncio
async def test_settle_bet_win_clamps_payout_to_pool(fake_conn_state):
    fake_conn_state['pools'][RESOURCE_IDS['ER']] = 1_000
    fake_conn_state['faction_global'] = 10_000_000_000

    result = await casino_service.settle_bet(
        faction_id=1, world_id=None, resource='ER', wager=100, payout_multiplier=100.0
    )
    assert result['payout'] <= 1_000 + 100
    assert _pool(fake_conn_state, 'ER') >= 0


@pytest.mark.asyncio
async def test_settle_bet_pool_never_negative_after_win(fake_conn_state):
    fake_conn_state['pools'][RESOURCE_IDS['ER']] = 50_000_000_000
    result = await casino_service.settle_bet(
        faction_id=1, world_id=None, resource='ER', wager=1_000_000, payout_multiplier=5.0
    )
    assert _pool(fake_conn_state, 'ER') >= 0
    assert result['payout'] <= 50_000_000_000 + 1_000_000


@pytest.mark.asyncio
async def test_settle_bet_loss_credits_full_wager_to_pool(fake_conn_state):
    pool_before = _pool(fake_conn_state, 'ER')
    await casino_service.settle_bet(
        faction_id=1, world_id=None, resource='ER', wager=1_000_000, payout_multiplier=0.0
    )
    assert _pool(fake_conn_state, 'ER') == pool_before + 1_000_000


@pytest.mark.asyncio
async def test_settle_bet_refuses_wager_above_table_max(fake_conn_state):
    fake_conn_state['pools'][RESOURCE_IDS['CM']] = 250_000
    table_max = casino_service.table_max_for_pool(
        _pool(fake_conn_state, 'CM'), 250_000
    )
    with pytest.raises(ValueError, match="TABLE_LIMIT"):
        await casino_service.settle_bet(
            faction_id=1, world_id=None, resource='CM', wager=table_max + 1, payout_multiplier=1.0
        )
