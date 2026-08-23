# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional

from database.cache_manager import cache_manager
from dtos.user import User
from repositories import utility_repo


async def get_operator_for_player(discord_id: int) -> Optional[dict]:
    return await utility_repo.get_operator_for_player(discord_id)


async def get_user_access_row(user_id: int) -> Optional[User]:
    return await utility_repo.get_user_access_row(user_id)


async def set_custom_message_for_user(target_user_id: int, message: str, created_by: int):
    await utility_repo.set_custom_message_for_user(target_user_id, message, created_by)
    cache_manager.set_custom_message(target_user_id, message)


async def delete_custom_message_for_user(target_user_id: int):
    await utility_repo.delete_custom_message_for_user(target_user_id)
    cache_manager.set_custom_message(target_user_id, None)


async def get_custom_message_for_user(target_user_id: int) -> Optional[str]:
    return await utility_repo.get_custom_message_for_user(target_user_id)


async def get_badge_by_identifier(badge: str) -> Optional[dict]:
    try:
        return await utility_repo.get_badge_by_id(int(badge))
    except ValueError:
        return await utility_repo.get_badge_by_name(badge)


async def badge_name_exists(name: str) -> bool:
    return await utility_repo.badge_name_exists(name)


async def create_badge(name: str) -> int:
    return await utility_repo.create_badge(name)


async def get_all_badges() -> list[dict]:
    return await utility_repo.get_all_badges()


async def add_badge_to_user(user_id: int, badge_id: int):
    await utility_repo.add_badge_to_user(user_id, badge_id)


async def remove_badge_from_user(user_id: int, badge_id: int):
    await utility_repo.remove_badge_from_user(user_id, badge_id)


async def get_badge_names_for_user(user_id: int) -> list[str]:
    return await utility_repo.get_badge_names_for_user(user_id)


async def get_recent_completed_transfers_count(minutes: int = 5) -> int:
    return await utility_repo.get_recent_completed_transfers_count(minutes)


async def get_all_factions_min() -> list[dict]:
    return await utility_repo.get_all_factions_min()


async def get_status_resource_cache() -> dict:
    return await utility_repo.get_status_resource_cache()


async def recalc_fleet_cs_for_faction(faction_id: int) -> int:
    return await utility_repo.recalc_fleet_cs_for_faction(faction_id)


async def get_public_table_names_for_backup() -> list[str]:
    return await utility_repo.get_public_table_names_for_backup()


async def get_all_rows_for_table(table_name: str, allowed_tables: list[str] = None) -> list[dict]:
    if allowed_tables is None:
        allowed_tables = await get_public_table_names_for_backup()
    if table_name not in allowed_tables:
        raise ValueError(f"Table '{table_name}' is not available for backup.")
    quoted = table_name.replace('"', '""')
    return await utility_repo.fetch_all_rows_for_quoted_table(quoted)
