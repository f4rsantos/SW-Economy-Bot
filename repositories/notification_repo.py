# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional

from database.db_manager import db
from dtos.user import User


async def get_interested_leader_rows(world_id: int, acting_faction_id: Optional[int]) -> List[dict]:
    rows = await db.fetch(
        """
        SELECT DISTINCT f.leader_id
        FROM factions f
        WHERE f.leader_id IS NOT NULL
          AND ($2::integer IS NULL OR f.id <> $2)
          AND (
            EXISTS (
              SELECT 1 FROM world_factions wf
              WHERE wf.world_id = $1 AND wf.faction_id = f.id
            )
            OR EXISTS (
              SELECT 1 FROM fleets fl
              JOIN fleet_vehicles fv ON fv.fleet_id = fl.id
              WHERE fl.faction_id = f.id AND fl.position = $1
            )
          )
        """,
        world_id,
        acting_faction_id,
    )
    return [dict(row) for row in rows]


async def get_fleet_vehicle_count(fleet_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM fleet_vehicles WHERE fleet_id = $1",
        fleet_id,
    )
    return int(row["total"]) if row else 0


async def set_user_notify_mode(user_id: int, mode: str, channel_id: Optional[int]) -> Optional[User]:
    row = await db.fetchrow(
        "UPDATE users SET notify_mode = $2, notify_channel_id = $3 WHERE id = $1 RETURNING *",
        user_id,
        mode,
        channel_id,
    )
    return User.from_row(row) if row else None


async def set_user_notify_events(
    user_id: int,
    transfers: bool,
    movements: bool,
    origin: bool,
    destination: bool,
) -> Optional[User]:
    row = await db.fetchrow(
        """
        UPDATE users
        SET notify_transfers = $2,
            notify_movements = $3,
            notify_origin = $4,
            notify_destination = $5
        WHERE id = $1
        RETURNING *
        """,
        user_id,
        transfers,
        movements,
        origin,
        destination,
    )
    return User.from_row(row) if row else None
