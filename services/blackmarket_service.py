import random
from database.db_manager import db
from services.local_deduction import deduct_local_proportional

ALLOY_HOLD_CAP = 10
BASE_BUY_PRICE = 200_000
BUY_PRICE_GROWTH = 1.1
SELL_PAYOUT_BASE = 50_000
SELL_PAYOUT_MIN_RATIO = 0.9
SELL_PAYOUT_MAX_RATIO = 1.0
BUY_RESOURCES = ('CM', 'EL', 'CS')
SELL_RESOURCES = ('CM', 'EL', 'CS')
LOCAL_RESOURCES = {'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS'}


def buy_price_for_tier(held: int) -> int:
    return round(BASE_BUY_PRICE * (BUY_PRICE_GROWTH ** held))


def total_buy_price(held: int, quantity: int) -> dict:
    per_unit_total = sum(buy_price_for_tier(held + i) for i in range(quantity))
    return {res: per_unit_total for res in BUY_RESOURCES}


def sell_payout() -> dict:
    ratio = random.uniform(SELL_PAYOUT_MIN_RATIO, SELL_PAYOUT_MAX_RATIO)
    return {res: round(SELL_PAYOUT_BASE * ratio) for res in SELL_RESOURCES}


async def buy_alloys(faction_id: int, quantity: int) -> dict:
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")

    async with db.get_connection() as conn:
        async with conn.transaction():
            alloys_id = await conn.fetchval("SELECT id FROM resources WHERE name = 'Alloys'")
            if not alloys_id:
                raise ValueError("RESOURCE_NOT_FOUND: Alloys resource is not configured.")

            held = await conn.fetchval(
                "SELECT COALESCE(amount, 0) FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
                faction_id, alloys_id
            ) or 0

            if held >= ALLOY_HOLD_CAP:
                raise ValueError(f"CAP_REACHED: Your faction already holds {held} Alloys, the black market's limit.")
            if held + quantity > ALLOY_HOLD_CAP:
                raise ValueError(
                    f"CAP_REACHED: Buying {quantity} would bring your holdings to {held + quantity}, "
                    f"above the black market's cap of {ALLOY_HOLD_CAP}. You may buy at most {ALLOY_HOLD_CAP - held} more."
                )

            costs = total_buy_price(held, quantity)

            for res_name, cost in costs.items():
                res_id = await conn.fetchval("SELECT id FROM resources WHERE name = $1", res_name)
                if not res_id:
                    raise ValueError(f"RESOURCE_NOT_FOUND: Unknown resource {res_name}")
                available = await conn.fetchval(
                    "SELECT COALESCE(SUM(amount), 0) FROM local_treasury WHERE faction_id = $1 AND resource_id = $2",
                    faction_id, res_id
                )
                if available < cost:
                    raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient {res_name}. Need {cost:,}, have {available:,}")
                await deduct_local_proportional(conn, faction_id, res_id, available, cost)

            await conn.execute("""
                INSERT INTO faction_treasury (faction_id, resource_id, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (faction_id, resource_id)
                DO UPDATE SET amount = faction_treasury.amount + $3
            """, faction_id, alloys_id, quantity)

            return {'costs': costs, 'held_before': held, 'held_after': held + quantity}


async def sell_alloys(faction_id: int, quantity: int) -> dict:
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")

    async with db.get_connection() as conn:
        async with conn.transaction():
            alloys_id = await conn.fetchval("SELECT id FROM resources WHERE name = 'Alloys'")
            if not alloys_id:
                raise ValueError("RESOURCE_NOT_FOUND: Alloys resource is not configured.")

            held = await conn.fetchval(
                "SELECT COALESCE(amount, 0) FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
                faction_id, alloys_id
            ) or 0

            if held < quantity:
                raise ValueError(f"RESOURCE_INSUFFICIENT: You only hold {held} Alloys, cannot sell {quantity}.")

            totals = {res: 0 for res in SELL_RESOURCES}
            for _ in range(quantity):
                payout = sell_payout()
                for res, amt in payout.items():
                    totals[res] += amt

            await conn.execute(
                "UPDATE faction_treasury SET amount = amount - $3 WHERE faction_id = $1 AND resource_id = $2",
                faction_id, alloys_id, quantity
            )

            for res_name, amount in totals.items():
                res_id = await conn.fetchval("SELECT id FROM resources WHERE name = $1", res_name)
                if not res_id:
                    raise ValueError(f"RESOURCE_NOT_FOUND: Unknown resource {res_name}")
                if res_name in LOCAL_RESOURCES:
                    target_world = await conn.fetchval("""
                        SELECT world_id FROM world_factions
                        WHERE faction_id = $1
                        ORDER BY territory DESC
                        LIMIT 1
                    """, faction_id)
                    if target_world is None:
                        raise ValueError("NO_WORLD: Your faction has no world to receive resources.")
                    await conn.execute("""
                        INSERT INTO local_treasury (world_id, faction_id, resource_id, amount)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (world_id, faction_id, resource_id)
                        DO UPDATE SET amount = local_treasury.amount + $4
                    """, target_world, faction_id, res_id, amount)
                else:
                    await conn.execute("""
                        INSERT INTO faction_treasury (faction_id, resource_id, amount)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (faction_id, resource_id)
                        DO UPDATE SET amount = faction_treasury.amount + $3
                    """, faction_id, res_id, amount)

            return {'payout': totals, 'held_before': held, 'held_after': held - quantity}


async def get_alloys_held(faction_id: int) -> int:
    alloys_id = await db.fetchval("SELECT id FROM resources WHERE name = 'Alloys'")
    if not alloys_id:
        return 0
    row = await db.fetchrow(
        "SELECT COALESCE(amount, 0) AS amount FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, alloys_id
    )
    return row['amount'] if row else 0
