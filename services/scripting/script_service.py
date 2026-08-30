# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from repositories import script_repo
from .runtime import ExecutionResult

MAX_SCRIPTS_PER_FACTION = 10


async def get_active_scripts(faction_id: int) -> list[dict]:
    return await script_repo.get_active_scripts(faction_id)


async def get_script_by_name(faction_id: int, name: str) -> Optional[dict]:
    return await script_repo.get_script_by_name(faction_id, name)


async def get_manual_script_by_name(faction_id: int, name: str) -> Optional[dict]:
    return await script_repo.get_manual_script_by_name(faction_id, name)


async def get_script_by_id(script_id: int, faction_id: int) -> Optional[dict]:
    return await script_repo.get_script_by_id(script_id, faction_id)


async def count_active_scripts(faction_id: int) -> int:
    return await script_repo.count_active_scripts(faction_id)


async def create_script(
    faction_id: int,
    name: str,
    script_text: str,
    trigger_day: Optional[str],
    created_by: int,
    trigger_type: Optional[str] = None,
    is_auto_econ: bool = False,
) -> dict:
    count = await count_active_scripts(faction_id)
    if count >= MAX_SCRIPTS_PER_FACTION:
        raise ValueError(f"Maximum of {MAX_SCRIPTS_PER_FACTION} active scripts per faction")

    if len(script_text) > 4000:
        raise ValueError("Script exceeds 4000 character limit")

    existing = await get_script_by_name(faction_id, name)
    if existing:
        raise ValueError(f"A script named '{name}' already exists for this faction")

    return await script_repo.insert_script(
        faction_id, name, script_text, trigger_day, trigger_type, created_by, is_auto_econ
    )


async def update_script(
    script_id: int,
    faction_id: int,
    script_text: str,
    trigger_day: Optional[str],
    trigger_type: Optional[str] = None,
) -> dict:
    if len(script_text) > 4000:
        raise ValueError("Script exceeds 4000 character limit")

    row = await script_repo.update_script(script_id, faction_id, script_text, trigger_day, trigger_type)
    if not row:
        raise ValueError("Script not found or does not belong to your faction")
    return row


async def delete_script(script_id: int, faction_id: int) -> bool:
    return await script_repo.delete_script(script_id, faction_id)


async def deactivate_script(script_id: int, faction_id: int) -> bool:
    """Permanently stop a script from running again, preserving its history. Idempotent."""
    return await script_repo.deactivate_script(script_id, faction_id)


async def get_scripts_for_income_day(income_weekday_name: str) -> list[dict]:
    """Return active scripts that should run on income day (trigger_day NULL or matching the income weekday)."""
    return await script_repo.get_scripts_for_income_day(income_weekday_name)


async def get_scripts_for_scheduled_day(today: str, current_time: datetime) -> list[dict]:
    """Return active scripts with trigger_day = today that haven't run this week."""
    week_ago = current_time - timedelta(days=7)
    return await script_repo.get_scripts_for_scheduled_day(today, week_ago)


async def record_execution(
    script_id: int,
    faction_id: int,
    result: ExecutionResult,
    execution_ms: int,
) -> None:
    if not result.dry_run:
        now = datetime.now(timezone.utc)
        await script_repo.update_script_run_stats(script_id, now)
