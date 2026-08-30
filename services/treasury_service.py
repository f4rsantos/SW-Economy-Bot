# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from repositories import treasury_repo


async def find_best_world_for_withdrawal(faction_id: int, resource_id: int, amount: int):
    return await treasury_repo.find_world_with_resource(faction_id, resource_id, amount)


async def get_world_resources(faction_id: int, world_id: int, resource_ids: list):
    return await treasury_repo.get_world_resources(faction_id, world_id, resource_ids)


async def find_best_worlds_for_multiple_resources(faction_id: int, resources: list):
    if not resources:
        return None
    resource_ids = [r['resource_id'] for r in resources]
    resource_amounts = {r['resource_id']: r['amount'] for r in resources}
    rows = await treasury_repo.get_local_amounts_for_resources(faction_id, resource_ids)
    worlds: dict = {}
    for row in rows:
        worlds.setdefault(row.world_id, {})[row.resource_id] = row.amount
    valid = []
    for world_id, world_res in worlds.items():
        if all(world_res.get(rid, 0) >= amt for rid, amt in resource_amounts.items()):
            valid.append((world_id, sum(world_res.values())))
    return max(valid, key=lambda x: x[1])[0] if valid else None


async def withdraw_from_world(faction_id: int, world_id: int, resource_id: int, amount: int):
    current = await treasury_repo.get_local_amount(faction_id, world_id, resource_id)
    if current is None or current < amount:
        return False
    await treasury_repo.subtract_from_world(faction_id, world_id, resource_id, amount)
    return True


async def set_resource(faction_id: int, resource_id: int, amount: int, world_id=None):
    if world_id:
        await treasury_repo.set_local_resource(faction_id, world_id, resource_id, amount)
    else:
        await treasury_repo.set_faction_resource(faction_id, resource_id, amount)


async def deposit_to_world(faction_id: int, world_id: int, resource_id: int, amount: int):
    await treasury_repo.deposit_to_world(faction_id, world_id, resource_id, amount)
