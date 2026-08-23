# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from datetime import datetime
from database.db_manager import db


async def get_settings() -> dict:
    row = await db.fetchrow("SELECT last_income, income_day FROM settings LIMIT 1")
    return dict(row) if row else None


async def get_due_transfers(horizon: datetime) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT rt.id, rt.to_faction_id, rt.to_world_id
        FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        WHERE ts.name = 'in_transit' AND rt.arrival_time <= $1
        """,
        horizon
    )
    return [dict(r) for r in rows]


async def get_due_constructions(horizon: datetime) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, fleet_id, vehicle_id, quantity FROM vehicle_construction WHERE completion_date <= $1",
        horizon
    )
    return [dict(r) for r in rows]


async def get_due_recruitments(horizon: datetime) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, faction_id, amount, role_name, fleet_id FROM military_recruitment WHERE status = 'training' AND completion_time <= $1",
        horizon
    )
    return [dict(r) for r in rows]


async def get_moving_fleets() -> list[dict]:
    rows = await db.fetch(
        """
        SELECT f.id, f.moving_since, f.moving_to, w1.name as from_world, w2.name as to_world
        FROM fleets f
        JOIN worlds w1 ON f.position = w1.id
        JOIN worlds w2 ON f.moving_to = w2.id
        WHERE f.moving_to IS NOT NULL AND f.moving_since IS NOT NULL
        """
    )
    return [dict(r) for r in rows]


async def get_transfer_arrival_time(transfer_id: int):
    return await db.fetchval("SELECT arrival_time FROM resource_transfers WHERE id = $1", transfer_id)


async def get_construction_completion_date(order_id: int):
    return await db.fetchval("SELECT completion_date FROM vehicle_construction WHERE id = $1", order_id)


async def get_recruitment_completion_time(recruitment_id: int):
    return await db.fetchval("SELECT completion_time FROM military_recruitment WHERE id = $1", recruitment_id)
