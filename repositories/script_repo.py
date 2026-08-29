# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from database.db_manager import db
from dtos.script import Script


async def get_active_scripts(faction_id: int) -> list[Script]:
    rows = await db.fetch(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by, is_auto_econ
           FROM faction_scripts
           WHERE faction_id = $1 AND is_active = TRUE
           ORDER BY created_at""",
        faction_id,
    )
    return Script.from_rows(rows)


async def get_script_by_name(faction_id: int, name: str) -> Optional[Script]:
    row = await db.fetchrow(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by, is_auto_econ
           FROM faction_scripts
           WHERE faction_id = $1 AND LOWER(name) = LOWER($2) AND is_active = TRUE""",
        faction_id, name,
    )
    return Script.from_row(row) if row else None


async def get_manual_script_by_name(faction_id: int, name: str) -> Optional[Script]:
    row = await db.fetchrow(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by, is_auto_econ
           FROM faction_scripts
           WHERE faction_id = $1 AND LOWER(name) = LOWER($2) AND is_active = TRUE
             AND trigger_type = 'manual'""",
        faction_id, name,
    )
    return Script.from_row(row) if row else None


async def get_script_by_id(script_id: int, faction_id: int) -> Optional[Script]:
    row = await db.fetchrow(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by, is_auto_econ
           FROM faction_scripts
           WHERE id = $1 AND faction_id = $2""",
        script_id, faction_id,
    )
    return Script.from_row(row) if row else None


async def count_active_scripts(faction_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM faction_scripts WHERE faction_id = $1 AND is_active = TRUE",
        faction_id,
    )
    return int(row["cnt"]) if row else 0


async def insert_script(
    faction_id: int,
    name: str,
    script_text: str,
    trigger_day: Optional[str],
    trigger_type: Optional[str],
    created_by: int,
    is_auto_econ: bool = False,
) -> dict:
    row = await db.fetchrow(
        """INSERT INTO faction_scripts
                (faction_id, name, script_text, trigger_day, trigger_type, created_by, is_auto_econ)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                     last_run_at, run_count, is_active, created_by, is_auto_econ""",
        faction_id, name, script_text, trigger_day, trigger_type, created_by, is_auto_econ,
    )
    return dict(row)


async def update_script(
    script_id: int,
    faction_id: int,
    script_text: str,
    trigger_day: Optional[str],
    trigger_type: Optional[str],
) -> Optional[Script]:
    row = await db.fetchrow(
        """UPDATE faction_scripts
           SET script_text = $1, trigger_day = $2, trigger_type = $3, updated_at = NOW()
           WHERE id = $4 AND faction_id = $5 AND is_active = TRUE
           RETURNING id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                     last_run_at, run_count, is_active, created_by, is_auto_econ""",
        script_text, trigger_day, trigger_type, script_id, faction_id,
    )
    return Script.from_row(row) if row else None


async def update_auto_econ_script(
    script_id: int,
    faction_id: int,
    script_text: str,
    trigger_day: Optional[str],
) -> Optional[Script]:
    row = await db.fetchrow(
        """UPDATE faction_scripts
           SET script_text = $1, trigger_day = $2, trigger_type = NULL,
               is_auto_econ = TRUE, updated_at = NOW()
           WHERE id = $3 AND faction_id = $4 AND is_active = TRUE
           RETURNING id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                     last_run_at, run_count, is_active, created_by, is_auto_econ""",
        script_text, trigger_day, script_id, faction_id,
    )
    return Script.from_row(row) if row else None


async def delete_script(script_id: int, faction_id: int) -> bool:
    result = await db.execute(
        "DELETE FROM faction_scripts WHERE id = $1 AND faction_id = $2",
        script_id, faction_id,
    )
    return result == "DELETE 1"


async def deactivate_script(script_id: int, faction_id: int) -> bool:
    result = await db.execute(
        """UPDATE faction_scripts
           SET is_active = FALSE
           WHERE id = $1 AND faction_id = $2 AND is_active = TRUE""",
        script_id, faction_id,
    )
    return result == "UPDATE 1"


async def get_scripts_for_income_day(income_weekday_name: str) -> list[Script]:
    rows = await db.fetch(
        """SELECT fs.id, fs.faction_id, fs.script_text, fs.trigger_day,
                  (f.faction_type = 1) as is_company
           FROM faction_scripts fs
           JOIN factions f ON fs.faction_id = f.id
           WHERE fs.is_active = TRUE
             AND (fs.trigger_day IS NULL OR fs.trigger_day = $1)""",
        income_weekday_name,
    )
    return Script.from_rows(rows)


async def get_scripts_for_scheduled_day(today: str, week_ago: datetime) -> list[Script]:
    rows = await db.fetch(
        """SELECT fs.id, fs.faction_id, fs.script_text, fs.trigger_day,
                  (f.faction_type = 1) as is_company
           FROM faction_scripts fs
           JOIN factions f ON fs.faction_id = f.id
           WHERE fs.is_active = TRUE
             AND fs.trigger_day = $1
             AND (fs.last_run_at IS NULL OR fs.last_run_at < $2)""",
        today, week_ago,
    )
    return Script.from_rows(rows)


async def update_script_run_stats(script_id: int, now: datetime) -> None:
    await db.execute(
        """UPDATE faction_scripts
           SET last_run_at = $1, run_count = run_count + 1
           WHERE id = $2""",
        now, script_id,
    )
