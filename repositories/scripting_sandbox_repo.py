# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.db_manager import db


async def get_local_resource_total(faction_id: int, res_upper: str) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT COALESCE(SUM(lt.amount), 0) as total
           FROM local_treasury lt
           JOIN resources r ON lt.resource_id = r.id
           WHERE lt.faction_id = $1 AND UPPER(r.name) = $2""",
        faction_id, res_upper,
    )


async def get_faction_resource_total(faction_id: int, res_upper: str) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT COALESCE(ft.amount, 0) as total
           FROM faction_treasury ft
           JOIN resources r ON ft.resource_id = r.id
           WHERE ft.faction_id = $1 AND UPPER(r.name) = $2""",
        faction_id, res_upper,
    )


async def get_fleet_health(faction_id: int, fleet_id: int) -> Optional[dict]:
    return await db.fetchrow(
        "SELECT health FROM fleets WHERE id = $1 AND faction_id = $2",
        fleet_id, faction_id,
    )


async def get_fleet_status_name(faction_id: int, fleet_id: int) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT fs.name FROM fleets f
           JOIN fleet_status fs ON f.status_id = fs.id
           WHERE f.id = $1 AND f.faction_id = $2""",
        fleet_id, faction_id,
    )


async def get_building_count(faction_id: int, building_id: int, world_id: int) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT COALESCE(amount, 0) as total
           FROM faction_world_buildings
           WHERE faction_id = $1 AND building_id = $2 AND world_id = $3""",
        faction_id, building_id, world_id,
    )


async def get_war_participation(faction_id: int) -> Optional[dict]:
    return await db.fetchrow(
        "SELECT 1 FROM war_participants WHERE faction_id = $1 LIMIT 1",
        faction_id,
    )


async def get_fleet_by_ref(faction_id: int, ref) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
                  f.position, fs.name as status_name, w.name as world_name
           FROM fleets f
           JOIN fleet_status fs ON f.status_id = fs.id
           JOIN worlds w ON f.position = w.id
           WHERE f.faction_id = $1 AND (f.id = $2 OR f.faction_fleet_number = $2)""",
        faction_id, ref,
    )


async def get_fleet_by_name(faction_id: int, name: str) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
                  f.position, fs.name as status_name, w.name as world_name
           FROM fleets f
           JOIN fleet_status fs ON f.status_id = fs.id
           JOIN worlds w ON f.position = w.id
           WHERE f.faction_id = $1 AND LOWER(f.name) = LOWER($2)""",
        faction_id, name,
    )


async def get_vehicle_by_number(faction_id: int, number: int) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT v.id, v.name, v.designation, v.faction_vehicle_number
           FROM vehicles v
           WHERE v.faction_id = $1 AND v.faction_vehicle_number = $2""",
        faction_id, number,
    )


async def get_vehicle_by_name(faction_id: int, name: str) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT v.id, v.name, v.designation, v.faction_vehicle_number
           FROM vehicles v
           WHERE v.faction_id = $1
             AND (LOWER(v.name) = LOWER($2)
               OR LOWER(CONCAT(v.name, ' ', v.designation)) = LOWER($2))""",
        faction_id, name,
    )


async def get_fleet_ids_at_world(faction_id: int, world_id: int):
    return await db.fetch(
        "SELECT id FROM fleets WHERE faction_id = $1 AND position = $2 ORDER BY faction_fleet_number",
        faction_id, world_id,
    )


async def get_fleet_vehicle_count(fleet_id: int) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT COALESCE(SUM(fv.amount), 0) as total
           FROM fleet_vehicles fv
           JOIN vehicles v ON fv.vehicle_id = v.id
           LEFT JOIN vehicle_types vt ON v.type = vt.id
           WHERE fv.fleet_id = $1 AND LOWER(COALESCE(vt.name, '')) != 'missile'""",
        fleet_id,
    )


async def get_world_resource_amount(faction_id: int, world_id: int, resource_upper: str) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT COALESCE(lt.amount, 0) as total
           FROM local_treasury lt
           JOIN resources r ON lt.resource_id = r.id
           WHERE lt.faction_id = $1 AND lt.world_id = $2 AND UPPER(r.name) = $3""",
        faction_id, world_id, resource_upper,
    )


async def get_resource_id(resource_upper: str) -> Optional[dict]:
    return await db.fetchrow(
        "SELECT id FROM resources WHERE UPPER(name) = $1",
        resource_upper,
    )


async def get_local_treasury_world_with_amount(faction_id: int, resource_id: int, total_cost) -> Optional[dict]:
    return await db.fetchrow(
        """SELECT world_id FROM local_treasury
           WHERE faction_id = $1 AND resource_id = $2 AND amount >= $3
           ORDER BY amount DESC LIMIT 1""",
        faction_id, resource_id, total_cost,
    )


async def debit_local_treasury(faction_id: int, world_id: int, resource_id: int, total_cost) -> None:
    await db.execute(
        "UPDATE local_treasury SET amount = amount - $1 WHERE faction_id = $2 AND world_id = $3 AND resource_id = $4",
        total_cost, faction_id, world_id, resource_id,
    )


async def get_faction_treasury_amount(faction_id: int, resource_id: int) -> Optional[dict]:
    return await db.fetchrow(
        "SELECT amount FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id,
    )


async def debit_faction_treasury(faction_id: int, resource_id: int, total_cost) -> None:
    await db.execute(
        "UPDATE faction_treasury SET amount = amount - $1 WHERE faction_id = $2 AND resource_id = $3",
        total_cost, faction_id, resource_id,
    )
