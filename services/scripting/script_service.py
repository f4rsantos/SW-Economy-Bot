from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from database.db_manager import db
from .runtime import ExecutionResult

MAX_SCRIPTS_PER_FACTION = 10


async def get_active_scripts(faction_id: int) -> list[dict]:
    rows = await db.fetch(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by
           FROM faction_scripts
           WHERE faction_id = $1 AND is_active = TRUE
           ORDER BY created_at""",
        faction_id,
    )
    return [dict(r) for r in rows]


async def get_script_by_name(faction_id: int, name: str) -> Optional[dict]:
    row = await db.fetchrow(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by
           FROM faction_scripts
           WHERE faction_id = $1 AND LOWER(name) = LOWER($2) AND is_active = TRUE""",
        faction_id, name,
    )
    return dict(row) if row else None


async def get_manual_script_by_name(faction_id: int, name: str) -> Optional[dict]:
    row = await db.fetchrow(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by
           FROM faction_scripts
           WHERE faction_id = $1 AND LOWER(name) = LOWER($2) AND is_active = TRUE
             AND trigger_type = 'manual'""",
        faction_id, name,
    )
    return dict(row) if row else None


async def get_script_by_id(script_id: int, faction_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """SELECT id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                  last_run_at, run_count, is_active, created_by
           FROM faction_scripts
           WHERE id = $1 AND faction_id = $2""",
        script_id, faction_id,
    )
    return dict(row) if row else None


async def count_active_scripts(faction_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM faction_scripts WHERE faction_id = $1 AND is_active = TRUE",
        faction_id,
    )
    return int(row["cnt"]) if row else 0


async def create_script(
    faction_id: int,
    name: str,
    script_text: str,
    trigger_day: Optional[str],
    created_by: int,
    trigger_type: Optional[str] = None,
) -> dict:
    count = await count_active_scripts(faction_id)
    if count >= MAX_SCRIPTS_PER_FACTION:
        raise ValueError(f"Maximum of {MAX_SCRIPTS_PER_FACTION} active scripts per faction")

    if len(script_text) > 4000:
        raise ValueError("Script exceeds 4000 character limit")

    existing = await get_script_by_name(faction_id, name)
    if existing:
        raise ValueError(f"A script named '{name}' already exists for this faction")

    row = await db.fetchrow(
        """INSERT INTO faction_scripts (faction_id, name, script_text, trigger_day, trigger_type, created_by)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                     last_run_at, run_count, is_active, created_by""",
        faction_id, name, script_text, trigger_day, trigger_type, created_by,
    )
    return dict(row)


async def update_script(
    script_id: int,
    faction_id: int,
    script_text: str,
    trigger_day: Optional[str],
    trigger_type: Optional[str] = None,
) -> dict:
    if len(script_text) > 4000:
        raise ValueError("Script exceeds 4000 character limit")

    row = await db.fetchrow(
        """UPDATE faction_scripts
           SET script_text = $1, trigger_day = $2, trigger_type = $3, updated_at = NOW()
           WHERE id = $4 AND faction_id = $5 AND is_active = TRUE
           RETURNING id, name, script_text, trigger_day, trigger_type, created_at, updated_at,
                     last_run_at, run_count, is_active, created_by""",
        script_text, trigger_day, trigger_type, script_id, faction_id,
    )
    if not row:
        raise ValueError("Script not found or does not belong to your faction")
    return dict(row)


async def deactivate_script(script_id: int, faction_id: int) -> bool:
    result = await db.execute(
        "UPDATE faction_scripts SET is_active = FALSE WHERE id = $1 AND faction_id = $2 AND is_active = TRUE",
        script_id, faction_id,
    )
    return result == "UPDATE 1"


async def get_scripts_for_income_day(income_weekday_name: str) -> list[dict]:
    """Return active scripts that should run on income day (trigger_day NULL or matching the income weekday)."""
    rows = await db.fetch(
        """SELECT fs.id, fs.faction_id, fs.script_text, fs.trigger_day,
                  (f.faction_type = 1) as is_company
           FROM faction_scripts fs
           JOIN factions f ON fs.faction_id = f.id
           WHERE fs.is_active = TRUE
             AND (fs.trigger_day IS NULL OR fs.trigger_day = $1)""",
        income_weekday_name,
    )
    return [dict(r) for r in rows]


async def get_scripts_for_scheduled_day(today: str, current_time: datetime) -> list[dict]:
    """Return active scripts with trigger_day = today that haven't run this week."""
    week_ago = current_time - timedelta(days=7)
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
    return [dict(r) for r in rows]


async def record_execution(
    script_id: int,
    faction_id: int,
    result: ExecutionResult,
    execution_ms: int,
) -> None:
    now = datetime.now(timezone.utc)

    await db.execute(
        """INSERT INTO script_execution_log
           (script_id, faction_id, executed_at, actions_taken, skipped, aborted, dry_run,
            errors, warnings, execution_ms)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
        script_id, faction_id, now,
        result.actions_taken,
        result.skipped,
        result.aborted,
        result.dry_run,
        result.errors or [],
        result.warnings or [],
        execution_ms,
    )

    if not result.dry_run:
        await db.execute(
            """UPDATE faction_scripts
               SET last_run_at = $1, run_count = run_count + 1
               WHERE id = $2""",
            now, script_id,
        )


async def get_last_execution(script_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """SELECT id, executed_at, actions_taken, skipped, aborted, dry_run,
                  errors, warnings, execution_ms
           FROM script_execution_log
           WHERE script_id = $1
           ORDER BY executed_at DESC
           LIMIT 1""",
        script_id,
    )
    return dict(row) if row else None
