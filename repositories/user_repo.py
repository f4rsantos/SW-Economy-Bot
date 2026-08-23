# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional

from database.db_manager import db
from dtos.user import User


async def create_user(user_id: int, access_level: int = 0) -> Optional[User]:
    row = await db.fetchrow(
        "INSERT INTO users (id, access_level) VALUES ($1, $2) RETURNING *",
        user_id,
        access_level,
    )
    return User.from_row(row) if row else None


async def update_user_access_level(user_id: int, access_level: int) -> Optional[User]:
    row = await db.fetchrow(
        "UPDATE users SET access_level = $2 WHERE id = $1 RETURNING *",
        user_id,
        access_level,
    )
    return User.from_row(row) if row else None


async def set_user_ephemeral(user_id: int, value: bool) -> Optional[User]:
    row = await db.fetchrow(
        "UPDATE users SET ephemeral_commands = $2 WHERE id = $1 RETURNING *",
        user_id,
        value,
    )
    return User.from_row(row) if row else None
