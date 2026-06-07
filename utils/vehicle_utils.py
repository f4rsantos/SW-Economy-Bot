from database.db_manager import db
from typing import Optional


async def get_vehicle_by_display_id(faction_id: int, display_id: int) -> Optional[dict]:
    query = """
        SELECT *,
               COALESCE((
                   SELECT (elem->>'length')::int
                   FROM unnest(vehicle_data) elem
                   WHERE elem->>'length' IS NOT NULL
                   LIMIT 1
               ), 0) as length
        FROM vehicles
        WHERE faction_id = $1 AND faction_vehicle_number = $2
    """
    return await db.fetchrow(query, faction_id, display_id)


async def get_next_vehicle_number(faction_id: int) -> int:
    query = """
        SELECT COALESCE(MAX(faction_vehicle_number), 0) + 1 as next_number
        FROM vehicles
        WHERE faction_id = $1
    """
    result = await db.fetchrow(query, faction_id)
    return result['next_number']
