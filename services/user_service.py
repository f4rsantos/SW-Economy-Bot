# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.cache_manager import cache_manager
from dtos.user import User
from repositories import user_repo


async def get_user(user_id: int) -> Optional[User]:
    return cache_manager.get_user(user_id)


async def check_user_exists(user_id: int) -> bool:
    return await get_user(user_id) is not None


async def create_user(user_id: int, access_level: int = 0) -> User:
    user_data = await user_repo.create_user(user_id, access_level)
    cache_manager.users[user_id] = user_data
    return user_data


async def update_user_access_level(user_id: int, access_level: int) -> User:
    user_data = await user_repo.update_user_access_level(user_id, access_level)
    cache_manager.users[user_id] = user_data
    return user_data


async def get_user_access_level(user_id: int) -> int:
    user = await get_user(user_id)
    if user is None:
        return -2
    return user.access_level


async def get_user_ephemeral(user_id: int) -> bool:
    user = await get_user(user_id)
    if user is None:
        return False
    return user.ephemeral_commands


async def set_user_ephemeral(user_id: int, value: bool) -> User:
    user_data = await user_repo.set_user_ephemeral(user_id, value)
    if user_data is None:
        raise ValueError("You are not registered in the database yet.")
    cache_manager.users[user_id] = user_data
    return user_data
