# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.db_manager import db
from dtos.comet import Comet


async def create_comet(name: str, message: str, discoverer: int) -> Comet:
    row = await db.fetchrow(
        "SELECT * FROM sp_create_comet($1, $2, $3)",
        name, message, discoverer
    )
    return Comet.from_row(row)


async def get_comets(limit: int = 50, offset: int = 0) -> list[Comet]:
    rows = await db.fetch(
        "SELECT * FROM sp_get_comets($1, $2)",
        limit, offset
    )
    return Comet.from_rows(rows)


async def get_comet(comet_id: int) -> Optional[Comet]:
    row = await db.fetchrow(
        "SELECT * FROM sp_get_comet($1)",
        comet_id
    )
    return Comet.from_row(row) if row else None
