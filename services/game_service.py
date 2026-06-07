from typing import Optional
from database.db_manager import db


async def get_high_score(game_type: str) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT user_id, score FROM games WHERE game_type = $1 ORDER BY score DESC LIMIT 1",
        game_type,
    )
    return dict(row) if row else None


async def set_high_score(game_type: str, user_id: int, score: int):
    await db.execute("DELETE FROM games WHERE game_type = $1", game_type)
    await db.execute(
        "INSERT INTO games (user_id, game_type, score) VALUES ($1, $2, $3)",
        user_id,
        game_type,
        score,
    )


async def set_high_score_if_higher(game_type: str, user_id: int, score: int) -> Optional[int]:
    current = await get_high_score(game_type)
    if not current or score > current['score']:
        previous = current['score'] if current else 0
        await set_high_score(game_type, user_id, score)
        return previous
    return None
