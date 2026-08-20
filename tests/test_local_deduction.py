import math
import pytest

from services.local_deduction import deduct_local_proportional


class FakeConn:
    def __init__(self, worlds):
        self.worlds = dict(worlds)

    async def execute(self, query, *args):
        if "FLOOR" in query:
            faction_id, resource_id, total, amount = args
            for wid, val in list(self.worlds.items()):
                if val > 0:
                    self.worlds[wid] = val - math.floor((val / total) * amount)
        else:
            faction_id, resource_id, world_id, take = args
            self.worlds[world_id] -= take

    async def fetchval(self, query, *args):
        return sum(self.worlds.values())

    async def fetch(self, query, *args):
        rows = [{'world_id': w, 'amount': a} for w, a in self.worlds.items() if a > 0]
        return sorted(rows, key=lambda r: r['amount'], reverse=True)


async def run_case(worlds, amount):
    conn = FakeConn(worlds)
    before = sum(conn.worlds.values())
    await deduct_local_proportional(conn, 1, 2, before, amount)
    after = sum(conn.worlds.values())
    return before, after, conn.worlds


@pytest.mark.asyncio
async def test_exact_amount_deducted_with_awkward_remainders():
    before, after, worlds = await run_case({1: 1000, 2: 3, 3: 2}, 600)
    assert before - after == 600
    assert all(v >= 0 for v in worlds.values())


@pytest.mark.asyncio
async def test_even_split_rounding():
    before, after, worlds = await run_case({1: 10, 2: 10}, 15)
    assert before - after == 15
    assert all(v >= 0 for v in worlds.values())


@pytest.mark.asyncio
async def test_full_drain():
    before, after, worlds = await run_case({1: 50, 2: 50}, 100)
    assert after == 0


@pytest.mark.asyncio
async def test_single_world():
    before, after, worlds = await run_case({1: 500}, 137)
    assert before - after == 137
    assert worlds[1] == 363


@pytest.mark.asyncio
async def test_shortfall_spills_past_largest_world():
    before, after, worlds = await run_case({1: 3, 2: 3, 3: 3, 4: 3, 5: 3}, 14)
    assert before - after == 14
    assert all(v >= 0 for v in worlds.values())


@pytest.mark.asyncio
async def test_zero_amount_is_noop():
    before, after, worlds = await run_case({1: 100, 2: 50}, 0)
    assert before == after


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", list(range(1, 40)))
async def test_sweep_always_exact(amount):
    before, after, worlds = await run_case({1: 17, 2: 11, 3: 7, 4: 5}, amount)
    assert before - after == amount
    assert all(v >= 0 for v in worlds.values())
