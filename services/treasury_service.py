from database.db_manager import db


async def find_best_world_for_withdrawal(faction_id: int, resource_id: int, amount: int):
    result = await db.fetchrow("""
        SELECT world_id FROM local_treasury
        WHERE faction_id = $1 AND resource_id = $2 AND amount >= $3
        ORDER BY amount DESC LIMIT 1
    """, faction_id, resource_id, amount)
    return result['world_id'] if result else None


async def get_world_resources(faction_id: int, world_id: int, resource_ids: list):
    results = await db.fetch("""
        SELECT resource_id, amount FROM local_treasury
        WHERE faction_id = $1 AND world_id = $2 AND resource_id = ANY($3)
    """, faction_id, world_id, resource_ids)
    return {r['resource_id']: r['amount'] for r in results}


async def find_best_worlds_for_multiple_resources(faction_id: int, resources: list):
    if not resources:
        return None
    resource_ids = [r['resource_id'] for r in resources]
    resource_amounts = {r['resource_id']: r['amount'] for r in resources}
    results = await db.fetch("""
        SELECT world_id, resource_id, amount FROM local_treasury
        WHERE faction_id = $1 AND resource_id = ANY($2)
    """, faction_id, resource_ids)
    worlds: dict = {}
    for row in results:
        worlds.setdefault(row['world_id'], {})[row['resource_id']] = row['amount']
    valid = []
    for world_id, world_res in worlds.items():
        if all(world_res.get(rid, 0) >= amt for rid, amt in resource_amounts.items()):
            valid.append((world_id, sum(world_res.values())))
    return max(valid, key=lambda x: x[1])[0] if valid else None


async def withdraw_from_world(faction_id: int, world_id: int, resource_id: int, amount: int):
    current = await db.fetchrow(
        "SELECT amount FROM local_treasury WHERE faction_id = $1 AND world_id = $2 AND resource_id = $3",
        faction_id, world_id, resource_id
    )
    if not current or current['amount'] < amount:
        return False
    await db.execute(
        "UPDATE local_treasury SET amount = amount - $1 WHERE faction_id = $2 AND world_id = $3 AND resource_id = $4",
        amount, faction_id, world_id, resource_id
    )
    return True


async def set_resource(faction_id: int, resource_id: int, amount: int, world_id=None):
    if world_id:
        await db.execute("""
            INSERT INTO local_treasury (world_id, faction_id, resource_id, amount)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (world_id, faction_id, resource_id) DO UPDATE SET amount = $4
        """, world_id, faction_id, resource_id, amount)
    else:
        await db.execute("""
            INSERT INTO faction_treasury (faction_id, resource_id, amount)
            VALUES ($1, $2, $3)
            ON CONFLICT (faction_id, resource_id) DO UPDATE SET amount = $3
        """, faction_id, resource_id, amount)


async def deposit_to_world(faction_id: int, world_id: int, resource_id: int, amount: int):
    await db.execute("""
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + $4
    """, faction_id, world_id, resource_id, amount)
