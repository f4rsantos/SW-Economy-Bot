# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from repositories import badge_repo
from services.transfer_service import deduct_resources
from services.utility_service import add_badge_to_user


async def get_badge_catalog() -> dict[int, dict]:
    rows = await badge_repo.get_badge_catalog_rows()
    catalog: dict[int, dict] = {}
    for row in rows:
        bid = row.id
        if bid not in catalog:
            catalog[bid] = {
                'name': row.name,
                'needs_world': row.needs_world,
                'icon_url': row.icon_url,
                'costs': {},
            }
        catalog[bid]['costs'][row.resource_name] = row.amount
    return catalog


async def get_badge_names(badge_ids: list[int]) -> dict[int, str]:
    return await badge_repo.get_badge_names(badge_ids)


async def get_badges_info(badge_ids: list[int]) -> list:
    if not badge_ids:
        return []
    return await badge_repo.get_badges_info(list(badge_ids))


async def user_has_badge(user_id: int, badge_id: int) -> bool:
    return await badge_repo.user_has_badge(user_id, badge_id)


async def get_user_badge_ids(user_id: int) -> set[int]:
    row = await badge_repo.get_user_badge_ids(user_id)
    return set(row or [])


async def purchase_badge(faction_id: int, world_id: int | None, badge_id: int, user_id: int):
    catalog = await get_badge_catalog()
    entry = catalog.get(badge_id)
    if not entry:
        raise ValueError(f"Badge {badge_id} is not a purchasable badge.")

    async with badge_repo.get_connection() as conn:
        async with conn.transaction():
            owned = await badge_repo.get_user_badge_ids_for_update(conn, user_id, badge_id)
            if owned:
                raise ValueError(f"You already own the **[{entry['name']}]** badge.")

            await deduct_resources(faction_id, world_id, entry['costs'], conn=conn)
            await badge_repo.append_badge_to_user(conn, user_id, badge_id)


async def get_badge_progress(user_id: int, badge_id: int) -> dict[str, int]:
    rows = await badge_repo.get_badge_progress_rows(user_id, badge_id)
    return {row.resource_name: row.current_amount for row in rows}


async def log_badge_progress(
    user_id: int,
    badge_id: int,
    faction_id: int,
    world_id: int | None,
    contributions: dict[str, int],
    catalog_entry: dict,
) -> dict:
    targets = catalog_entry['costs']

    if await user_has_badge(user_id, badge_id):
        raise ValueError(f"You already own the **[{catalog_entry['name']}]** badge.")

    await deduct_resources(faction_id, world_id, contributions)

    progress = await get_badge_progress(user_id, badge_id)
    for resource_name, amount in contributions.items():
        row = await badge_repo.upsert_badge_progress_resource(user_id, badge_id, resource_name, amount)
        progress[resource_name] = row['current_amount']

    completed = all(progress.get(res, 0) >= target for res, target in targets.items())

    if completed:
        await add_badge_to_user(user_id, badge_id)
        await badge_repo.delete_badge_progress(user_id, badge_id)

    return {'progress': progress, 'targets': targets, 'completed': completed}
