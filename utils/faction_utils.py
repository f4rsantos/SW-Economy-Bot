# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db
from database.cache_manager import cache_manager
from dtos.faction import Faction


_FACTION_QUERY = """
    SELECT * FROM factions
"""

FACTION_TYPE_NATION = 0
FACTION_TYPE_COMPANY = 1
FACTION_TYPE_PIRATE = 2

FACTION_TYPE_LABELS = {0: "Nation", 1: "Company", 2: "Pirate"}


def is_company(faction_type: int) -> bool:
    return faction_type == FACTION_TYPE_COMPANY


def is_pirate(faction_type: int) -> bool:
    return faction_type == FACTION_TYPE_PIRATE


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
        if (f.name or '').lower() == name_lower:
            return f
    row = await db.fetchrow(_FACTION_QUERY + "WHERE LOWER(name) = LOWER($1)", name)
    if not row:
        return None
    faction = Faction.from_row(row)
    cache_manager.set_faction(faction.id, faction)
    return faction


async def get_faction_by_leader(leader_id: int):
    row = await db.fetchrow(_FACTION_QUERY + "WHERE leader_id = $1", leader_id)
    return Faction.from_row(row) if row else None


async def get_faction_by_id(faction_id: int):
    cached = cache_manager.get_faction(faction_id)
    if cached:
        return cached
    row = await db.fetchrow(_FACTION_QUERY + "WHERE id = $1", faction_id)
    if not row:
        return None
    faction = Faction.from_row(row)
    cache_manager.set_faction(faction.id, faction)
    return faction


async def get_faction(identifier):
    try:
        return await get_faction_by_id(int(identifier))
    except (ValueError, TypeError):
        return await get_faction_by_name(str(identifier))


async def is_faction_leader(user_id: int, faction, allow_staff: bool = True) -> bool:
    if faction is None:
        return False
    if faction.leader_id == user_id:
        return True
    if not allow_staff:
        return False
    from services.user_service import get_user_access_level
    return await get_user_access_level(user_id) >= 4


async def leads_faction_named(user_id: int, faction_name: str) -> bool:
    if not faction_name:
        return False

    target = str(faction_name).strip().lower()
    factions = cache_manager.get_all_factions()
    if factions:
        for f in factions.values():
            if f.leader_id != user_id:
                continue
            name = (f.name or '').lower()
            formal = (f.formal_name or f.name or '').lower()
            if target in (name, formal):
                return True
        return False

    row = await db.fetchrow(
        """
        SELECT 1 FROM factions
        WHERE leader_id = $1
          AND (LOWER(name) = LOWER($2) OR LOWER(COALESCE(formal_name, name)) = LOWER($2))
        """,
        user_id, str(faction_name).strip()
    )
    return row is not None
