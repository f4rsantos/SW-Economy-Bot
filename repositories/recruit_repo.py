# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from datetime import datetime
from database.db_manager import db
from dtos.recruit import Recruitment


async def insert_recruitment(faction_id: int, amount: int, role_name: str, start_time: datetime, completion_time: datetime):
    return await db.fetchrow("""
        INSERT INTO military_recruitment (faction_id, amount, role_name, start_time, completion_time, status)
        VALUES ($1, $2, $3, $4, $5, 'training')
        RETURNING id, faction_id, amount, role_name, start_time, completion_time, status
    """, faction_id, amount, role_name, start_time, completion_time)


async def get_pending_recruitments(faction_id: int) -> list[Recruitment]:
    return Recruitment.from_rows(await db.fetch("""
        SELECT mr.id, mr.faction_id, mr.amount, mr.role_name,
               mr.start_time, mr.completion_time, mr.status, mr.fleet_id,
               f.name as unit_name, f.faction_fleet_number as unit_number
        FROM military_recruitment mr
        LEFT JOIN fleets f ON mr.fleet_id = f.id
        WHERE mr.faction_id = $1 AND mr.status = 'training'
        ORDER BY mr.completion_time ASC
    """, faction_id))


async def get_all_pending_recruitments() -> list[Recruitment]:
    return Recruitment.from_rows(await db.fetch("""
        SELECT mr.id, mr.faction_id, mr.amount, mr.role_name,
               mr.start_time, mr.completion_time, mr.status, mr.fleet_id,
               fac.name as faction_name, f.name as unit_name, f.faction_fleet_number as unit_number
        FROM military_recruitment mr
        JOIN factions fac ON mr.faction_id = fac.id
        LEFT JOIN fleets f ON mr.fleet_id = f.id
        WHERE mr.status = 'training'
        ORDER BY mr.completion_time ASC
    """))


async def get_completed_recruitments(current_time: datetime) -> list[Recruitment]:
    return Recruitment.from_rows(await db.fetch(
        "SELECT id, faction_id, amount, role_name, fleet_id FROM military_recruitment WHERE status = 'training' AND completion_time <= $1",
        current_time
    ))


async def add_fleet_infantry(fleet_id: int, amount: int) -> None:
    await db.execute(
        "UPDATE fleets SET infantry_count = infantry_count + $1 WHERE id = $2",
        amount, fleet_id
    )


async def delete_recruitment(recruitment_id: int) -> None:
    await db.execute("DELETE FROM military_recruitment WHERE id = $1", recruitment_id)


async def cancel_recruitment(recruitment_id: int, faction_id: int):
    return await db.fetchrow("""
        DELETE FROM military_recruitment
        WHERE id = $1 AND faction_id = $2 AND status = 'training'
        RETURNING id, amount, role_name
    """, recruitment_id, faction_id)
