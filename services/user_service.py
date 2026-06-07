from typing import Optional, Dict
from database.db_manager import db
from database.cache_manager import cache_manager


async def get_user(user_id: int) -> Optional[Dict]:
    return cache_manager.get_user(user_id)


async def check_user_exists(user_id: int) -> bool:
    return await get_user(user_id) is not None


async def create_user(user_id: int, access_level: int = 0) -> Dict:
    result = await db.fetchrow(
        "INSERT INTO users (id, access_level) VALUES ($1, $2) RETURNING id, access_level",
        user_id, access_level
    )
    user_data = {'id': result['id'], 'access_level': result['access_level']}
    cache_manager.users[user_id] = user_data
    return user_data


async def update_user_access_level(user_id: int, access_level: int) -> Dict:
    result = await db.fetchrow(
        "UPDATE users SET access_level = $2 WHERE id = $1 RETURNING id, access_level",
        user_id, access_level
    )
    user_data = {'id': result['id'], 'access_level': result['access_level']}
    cache_manager.users[user_id] = user_data
    return user_data


async def get_user_access_level(user_id: int) -> int:
    user = await get_user(user_id)
    if user is None:
        return -2
    return user['access_level']
