from database.db_manager import db
from database.cache_manager import cache_manager


_FACTION_QUERY = """
    SELECT id, name, COALESCE(formal_name, name) as display_name,
           color, is_company, leader_id, leader
    FROM factions
"""


def hex_to_int(hex_color: str) -> int:
    if hex_color and hex_color.startswith('#'):
        try:
            return int(hex_color[1:], 16)
        except ValueError:
            pass
    return 0x2ecc71


async def get_faction_by_name(name: str):
    name_lower = name.lower()
    for f in cache_manager.get_all_factions().values():
        if f.get('name', '').lower() == name_lower:
            return f
    row = await db.fetchrow(_FACTION_QUERY + "WHERE LOWER(name) = LOWER($1)", name)
    if row:
        cache_manager.set_faction(row['id'], dict(row))
    return row


async def get_faction_by_leader(leader_id: int):
    return await db.fetchrow(_FACTION_QUERY + "WHERE leader_id = $1", leader_id)


async def get_faction_by_id(faction_id: int):
    cached = cache_manager.get_faction(faction_id)
    if cached:
        return cached
    row = await db.fetchrow(_FACTION_QUERY + "WHERE id = $1", faction_id)
    if row:
        cache_manager.set_faction(row['id'], dict(row))
    return row


async def get_faction(identifier):
    try:
        return await get_faction_by_id(int(identifier))
    except (ValueError, TypeError):
        return await get_faction_by_name(str(identifier))
