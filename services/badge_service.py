from database.db_manager import db
from services.transfer_service import deduct_resources
from services.utility_service import add_badge_to_user


async def get_badge_catalog() -> dict[int, dict]:
    rows = await db.fetch(
        """
        SELECT b.id, b.name, b.needs_world, r.name AS resource_name, bc.amount
        FROM badges b
        JOIN badge_costs bc ON b.id = bc.badge_id
        JOIN resources r ON r.id = bc.resource_id
        WHERE b.is_purchasable = true
        ORDER BY b.id, r.name
        """
    )
    catalog: dict[int, dict] = {}
    for row in rows:
        bid = row['id']
        if bid not in catalog:
            catalog[bid] = {
                'name': row['name'],
                'needs_world': row['needs_world'],
                'costs': {},
            }
        catalog[bid]['costs'][row['resource_name']] = row['amount']
    return catalog


async def get_badge_names(badge_ids: list[int]) -> dict[int, str]:
    rows = await db.fetch("SELECT id, name FROM badges WHERE id = ANY($1)", badge_ids)
    return {r['id']: r['name'] for r in rows}


async def purchase_badge(faction_id: int, world_id: int | None, badge_id: int, user_id: int):
    catalog = await get_badge_catalog()
    entry = catalog.get(badge_id)
    if not entry:
        raise ValueError(f"Badge {badge_id} is not a purchasable badge.")
    await deduct_resources(faction_id, world_id, entry['costs'])
    await db.execute(
        "UPDATE users SET badge_ids = array_append(badge_ids, $1) WHERE id = $2",
        badge_id, user_id
    )


async def get_badge_progress(user_id: int, badge_id: int) -> dict | None:
    row = await db.fetchrow(
        "SELECT current_amount, updated_at FROM badge_progress WHERE user_id = $1 AND badge_id = $2",
        user_id, badge_id
    )
    return dict(row) if row else None


async def log_badge_progress(
    user_id: int,
    badge_id: int,
    faction_id: int,
    world_id: int | None,
    amount: int,
    catalog_entry: dict,
) -> dict:
    resource_name = next(iter(catalog_entry['costs']))
    target = catalog_entry['costs'][resource_name]

    await deduct_resources(faction_id, world_id, {resource_name: amount})

    row = await db.fetchrow(
        """
        INSERT INTO badge_progress (user_id, badge_id, current_amount, updated_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, badge_id)
        DO UPDATE SET current_amount = badge_progress.current_amount + $3,
                      updated_at = CURRENT_TIMESTAMP
        RETURNING current_amount
        """,
        user_id, badge_id, amount
    )
    current = row['current_amount']

    if current >= target:
        await add_badge_to_user(user_id, badge_id)
        await db.execute(
            "DELETE FROM badge_progress WHERE user_id = $1 AND badge_id = $2",
            user_id, badge_id
        )
        return {'current': current, 'target': target, 'resource_name': resource_name, 'completed': True}

    return {'current': current, 'target': target, 'resource_name': resource_name, 'completed': False}
