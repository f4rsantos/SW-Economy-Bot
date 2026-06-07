import asyncpg
from typing import Optional
from database.db_manager import db


async def create_comet(name: str, message: str, discoverer: int) -> dict:
    try:
        row = await db.fetchrow(
            "SELECT * FROM sp_create_comet($1, $2, $3)",
            name, message, discoverer
        )
        return dict(row)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_comets(limit: int = 50, offset: int = 0) -> list[dict]:
    rows = await db.fetch(
        "SELECT * FROM sp_get_comets($1, $2)",
        limit, offset
    )
    return [dict(r) for r in rows]


async def get_comet(comet_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT * FROM sp_get_comet($1)",
        comet_id
    )
    return dict(row) if row else None
