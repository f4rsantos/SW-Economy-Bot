import pytest
from services.blockade_service import get_blockading_fleet_for_world
from services.background_tasks import handle_transfer_arrival
from services.transfer_service import intercept_transfer, destroy_transfer


@pytest.mark.asyncio
async def test_get_blockading_fleet_returns_fleet_id(fake_db):
    fake_db.fetchrow_queue.append({"fleet_id": 42})
    result = await get_blockading_fleet_for_world(world_id=5, target_faction_id=9)
    assert result == 42


@pytest.mark.asyncio
async def test_get_blockading_fleet_returns_none_when_not_blockaded(fake_db):
    fake_db.fetchrow_queue.append(None)
    result = await get_blockading_fleet_for_world(world_id=5, target_faction_id=9)
    assert result is None


@pytest.mark.asyncio
async def test_arrival_skips_deposit_when_intercepted(fake_db):
    fake_db.fetchrow_queue.append({"name": "intercepted"})
    await handle_transfer_arrival({"transfer_id": 1, "to_faction_id": 2, "to_world_id": 3})
    kinds = [call[0] for call in fake_db.executed]
    assert "fetch" not in kinds
    assert not any(c[0] == "execute" and "DELETE FROM resource_transfers" in c[1] for c in fake_db.executed)


@pytest.mark.asyncio
async def test_arrival_deposits_when_still_in_transit(fake_db):
    fake_db.fetchrow_queue.append({"name": "in_transit"})
    fake_db.fetch_queue.append([{"resource_id": 7, "amount": 100}])
    await handle_transfer_arrival({"transfer_id": 1, "to_faction_id": 2, "to_world_id": 3})
    assert any(c[0] == "execute" and "INSERT INTO local_treasury" in c[1] for c in fake_db.executed)
    assert any(c[0] == "execute" and "DELETE FROM resource_transfers" in c[1] for c in fake_db.executed)


@pytest.mark.asyncio
async def test_arrival_noop_when_transfer_missing(fake_db):
    fake_db.fetchrow_queue.append(None)
    await handle_transfer_arrival({"transfer_id": 1, "to_faction_id": 2, "to_world_id": 3})
    assert not any(c[0] == "execute" for c in fake_db.executed)


@pytest.mark.asyncio
async def test_intercept_transfer_passes_world_id(fake_db):
    await intercept_transfer(transfer_id=1, fleet_id=5, world_id=9)
    call = fake_db.executed[0]
    assert call[0] == "execute"
    assert call[2] == (1, 5, 9)


@pytest.mark.asyncio
async def test_destroy_transfer_calls_sp(fake_db):
    await destroy_transfer(transfer_id=1)
    call = fake_db.executed[0]
    assert call[0] == "execute"
    assert "sp_destroy_transfer" in call[1]
    assert call[2] == (1,)
