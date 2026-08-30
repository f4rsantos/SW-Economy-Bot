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
        SELECT DISTINCT f.id as faction_id, f.leader_id as user_id, true as is_leader,
               ($2::integer IS NOT NULL AND f.id = $2) as is_own
        FROM factions f
        WHERE f.leader_id IS NOT NULL
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

        UNION ALL

        SELECT DISTINCT f.id as faction_id, u.id as user_id, false as is_leader,
               ($2::integer IS NOT NULL AND f.id = $2) as is_own
        FROM factions f
        JOIN users u ON u.allegiance = COALESCE(NULLIF(f.formal_name, ''), f.name)
        WHERE (f.leader_id IS NULL OR u.id != f.leader_id)
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


async def get_faction_recipient_rows(faction_id: int) -> List[dict]:
    rows = await db.fetch(
        """
        SELECT f.id as faction_id, f.leader_id as user_id, true as is_leader
        FROM factions f
        WHERE f.id = $1 AND f.leader_id IS NOT NULL

        UNION ALL

        SELECT f.id as faction_id, u.id as user_id, false as is_leader
        FROM factions f
        JOIN users u ON u.allegiance = COALESCE(NULLIF(f.formal_name, ''), f.name)
        WHERE f.id = $1
          AND (f.leader_id IS NULL OR u.id != f.leader_id)
        """,
        faction_id,
    )
    return [dict(row) for row in rows]


async def get_recruitment_context(recruitment_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT faction_id FROM military_recruitment WHERE id = $1",
        recruitment_id,
    )
    return dict(row) if row else None


async def get_fleet_context(fleet_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT f.faction_id, f.name as fleet_name, w.id as world_id, w.name as world_name
        FROM fleets f
        JOIN worlds w ON w.id = f.position
        WHERE f.id = $1
        """,
        fleet_id,
    )
    return dict(row) if row else None


async def get_foreign_sharing_partner_leader_ids(faction_id: int, exclude_leader_id: int) -> List[dict]:
    rows = await db.fetch(
        """
        SELECT DISTINCT f.id as faction_id, f.leader_id
        FROM pact_members pm
        JOIN pacts p ON pm.pact_id = p.id
        JOIN pact_intelligence_sharing pis ON pis.pact_id = p.id
        JOIN pact_members other_pm ON other_pm.pact_id = p.id AND other_pm.faction_id != pm.faction_id
        JOIN factions f ON f.id = other_pm.faction_id
        WHERE pm.faction_id = $1 AND pis.foreign_alerts = true
          AND f.leader_id IS NOT NULL AND f.leader_id != $2
        """,
        faction_id,
        exclude_leader_id,
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
    own: bool,
) -> Optional[User]:
    row = await db.fetchrow(
        """
        UPDATE users
        SET notify_transfers = $2,
            notify_movements = $3,
            notify_origin = $4,
            notify_destination = $5,
            notify_own = $6
        WHERE id = $1
        RETURNING *
        """,
        user_id,
        transfers,
        movements,
        origin,
        destination,
        own,
    )
    return User.from_row(row) if row else None


async def set_user_notify_activity(
    user_id: int,
    recruitment: bool,
    fleet_arrival: bool,
    battle: bool,
    income: bool,
) -> Optional[User]:
    row = await db.fetchrow(
        """
        UPDATE users
        SET notify_recruitment = $2,
            notify_fleet_arrival = $3,
            notify_battle = $4,
            notify_income = $5
        WHERE id = $1
        RETURNING *
        """,
        user_id,
        recruitment,
        fleet_arrival,
        battle,
        income,
    )
    return User.from_row(row) if row else None
