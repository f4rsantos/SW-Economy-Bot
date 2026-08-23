# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.db_manager import db
from dtos.game import HighScore


async def get_high_score(game_type: str) -> Optional[HighScore]:
    row = await db.fetchrow(
        "SELECT user_id, score FROM games WHERE game_type = $1 ORDER BY score DESC LIMIT 1",
        game_type,
    )
    return HighScore.from_row(row) if row else None


async def set_high_score(game_type: str, user_id: int, score: int):
    await db.execute("DELETE FROM games WHERE game_type = $1", game_type)
    await db.execute(
        "INSERT INTO games (user_id, game_type, score) VALUES ($1, $2, $3)",
        user_id,
        game_type,
        score,
    )
