# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from dtos.game import HighScore
from repositories import game_repo


async def get_high_score(game_type: str) -> Optional[HighScore]:
    return await game_repo.get_high_score(game_type)


async def set_high_score(game_type: str, user_id: int, score: int):
    await game_repo.set_high_score(game_type, user_id, score)


async def set_high_score_if_higher(game_type: str, user_id: int, score: int) -> Optional[int]:
    current = await get_high_score(game_type)
    if not current or score > current.score:
        previous = current.score if current else 0
        await set_high_score(game_type, user_id, score)
        return previous
    return None
