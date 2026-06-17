import asyncpg
from database.db_manager import db


async def conquer_hexes(conqueror_faction_id: int, target_faction_id: int, world_id: int, hexes: int, grant_resources: bool) -> dict:
    try:
        row = await db.fetchrow(
            "SELECT * FROM sp_conquer_hexes($1, $2, $3, $4, $5)",
            conqueror_faction_id, target_faction_id, world_id, hexes, grant_resources
        )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e
    return dict(row)
