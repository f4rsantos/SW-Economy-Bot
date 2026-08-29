# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import logging
from typing import Optional
from database.cache_manager import cache_manager
from dtos.user import User
from dtos.allegiance_request import AllegianceRequest
from repositories import user_repo, allegiance_repo

logger = logging.getLogger(__name__)


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


async def get_user_allegiance(user_id: int) -> Optional[str]:
    user = await get_user(user_id)
    if user is None:
        return None
    return user.allegiance


async def get_user_treatment(user_id: int) -> Optional[str]:
    user = await get_user(user_id)
    if user is None:
        return None
    return user.treatment


async def set_user_allegiance(user_id: int, value: Optional[str]) -> User:
    user_data = await user_repo.set_user_allegiance(user_id, value)
    if user_data is None:
        raise ValueError("You are not registered in the database yet.")
    cache_manager.users[user_id] = user_data
    return user_data


async def clear_user_allegiance(user_id: int) -> User:
    return await set_user_allegiance(user_id, None)


async def request_user_allegiance(user_id: int, faction_id: int) -> AllegianceRequest:
    if not await get_user(user_id):
        raise ValueError("You are not registered in the database yet.")
    return await allegiance_repo.create_request(user_id, faction_id)


async def get_pending_allegiance_requests(faction_id: int) -> list:
    return await allegiance_repo.get_pending_requests_for_faction(faction_id)


async def approve_allegiance_request(request_id: int, resolved_by: int, display_name: str) -> User:
    request = await allegiance_repo.resolve_request(request_id, "approved", resolved_by)
    if request is None:
        raise ValueError("This request no longer needs action, it may have already been resolved.")
    user_data = await set_user_allegiance(request.user_id, display_name)

    try:
        from services.notification_service import notify_allegiance_resolved
        await notify_allegiance_resolved(request.user_id, display_name, approved=True)
    except Exception:
        logger.warning("Failed to notify user %s of allegiance approval", request.user_id, exc_info=True)

    return user_data


async def deny_allegiance_request(request_id: int, resolved_by: int, display_name: str) -> None:
    request = await allegiance_repo.resolve_request(request_id, "denied", resolved_by)
    if request is None:
        raise ValueError("This request no longer needs action, it may have already been resolved.")

    try:
        from services.notification_service import notify_allegiance_resolved
        await notify_allegiance_resolved(request.user_id, display_name, approved=False)
    except Exception:
        logger.warning("Failed to notify user %s of allegiance denial", request.user_id, exc_info=True)


async def set_user_treatment(user_id: int, value: Optional[str]) -> User:
    user_data = await user_repo.set_user_treatment(user_id, value)
    if user_data is None:
        raise ValueError("You are not registered in the database yet.")
    cache_manager.users[user_id] = user_data
    return user_data
