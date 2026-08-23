# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Dict, List, Optional, Tuple

from database.db_manager import db
from dtos.vehicle import Vehicle, VehicleCostRow


def get_connection():
    return db.get_connection()


async def get_vehicle_row_and_costs(vehicle_id: int) -> Tuple[Optional[Vehicle], List[VehicleCostRow]]:
    row = await db.fetchrow(
        "SELECT v.*, vt.name as type_name FROM vehicles v LEFT JOIN vehicle_types vt ON v.type = vt.id WHERE v.id = $1",
        vehicle_id
    )
    costs = await db.fetch(
        "SELECT r.name, vc.amount FROM vehicle_costs vc JOIN resources r ON vc.resource_id = r.id WHERE vc.vehicle_id = $1",
        vehicle_id
    )
    return (Vehicle.from_row(row) if row else None), VehicleCostRow.from_rows(costs)


async def get_vehicle_type_id_by_name(type_name: str) -> Optional[int]:
    result = await db.fetchrow("SELECT id FROM vehicle_types WHERE LOWER(name) = LOWER($1)", type_name)
    return result['id'] if result else None


async def get_vehicle_by_name(faction_id: int, vehicle_name: str) -> Optional[Vehicle]:
    query = """
        SELECT id, name, designation, type
        FROM vehicles
        WHERE faction_id = $1 AND LOWER(name) = LOWER($2)
    """
    result = await db.fetchrow(query, faction_id, vehicle_name)
    return Vehicle.from_row(result) if result else None


async def lock_vehicle_number(conn, lock_id: int, faction_id: int) -> None:
    await conn.execute("SELECT pg_advisory_xact_lock($1, $2)", lock_id, faction_id)


async def insert_vehicle(conn, faction_id: int, type_id: int, vehicle_name: str, designation: Optional[str],
                          next_number: int, vehicle_data_array) -> Vehicle:
    vehicle = await conn.fetchrow(
        """
        INSERT INTO vehicles (faction_id, type, name, designation, faction_vehicle_number, vehicle_data)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, faction_id, type, name, designation, faction_vehicle_number
        """,
        faction_id, type_id, vehicle_name, designation, next_number, vehicle_data_array
    )
    return Vehicle.from_row(vehicle)


async def insert_vehicle_costs_conn(conn, vehicle_id: int, cost_rows: list) -> None:
    if not cost_rows:
        return
    await conn.executemany(
        "INSERT INTO vehicle_costs (vehicle_id, resource_id, amount) VALUES ($1, $2, $3)",
        cost_rows
    )


async def insert_vehicle_costs(vehicle_id: int, cost_rows: list) -> None:
    if not cost_rows:
        return
    await db.executemany(
        "INSERT INTO vehicle_costs (vehicle_id, resource_id, amount) VALUES ($1, $2, $3)",
        cost_rows
    )


async def update_vehicle_row(designation: Optional[str], vehicle_data_array, vehicle_id: int) -> Vehicle:
    query = """
        UPDATE vehicles
        SET designation = $1, vehicle_data = $2
        WHERE id = $3
        RETURNING id, faction_id, type, name, designation
    """
    vehicle = await db.fetchrow(query, designation, vehicle_data_array, vehicle_id)
    return Vehicle.from_row(vehicle)


async def delete_vehicle_costs(vehicle_id: int) -> None:
    await db.execute("DELETE FROM vehicle_costs WHERE vehicle_id = $1", vehicle_id)


async def recalc_fleet_cs_for_vehicle(vehicle_id: int) -> None:
    await db.execute("""
        UPDATE fleets
        SET total_cs = (
            SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
            FROM fleet_vehicles fv
            JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
            JOIN resources r ON vc.resource_id = r.id AND r.name = 'CS'
            WHERE fv.fleet_id = fleets.id
        )
        WHERE id IN (
            SELECT DISTINCT fleet_id FROM fleet_vehicles WHERE vehicle_id = $1
        )
    """, vehicle_id)


async def get_vehicle_costs(vehicle_id: int) -> List[VehicleCostRow]:
    query = """
        SELECT r.name, vc.amount
        FROM vehicle_costs vc
        JOIN resources r ON vc.resource_id = r.id
        WHERE vc.vehicle_id = $1
    """
    rows = await db.fetch(query, vehicle_id)
    return VehicleCostRow.from_rows(rows)


async def list_vehicles(faction_id: int) -> list:
    rows = await db.fetch("""
        SELECT v.id, v.name, v.designation, v.faction_vehicle_number,
               vt.name as type_name, v.vehicle_data,
               COALESCE(
                   json_agg(json_build_object('resource', r.name, 'amount', vc.amount) ORDER BY r.name)
                   FILTER (WHERE vc.vehicle_id IS NOT NULL), '[]'
               ) as costs
        FROM vehicles v
        LEFT JOIN vehicle_types vt ON v.type = vt.id
        LEFT JOIN vehicle_costs vc ON v.id = vc.vehicle_id
        LEFT JOIN resources r ON vc.resource_id = r.id
        WHERE v.faction_id = $1
        GROUP BY v.id, v.name, v.designation, v.faction_vehicle_number, vt.name, v.vehicle_data
        ORDER BY v.id
    """, faction_id)
    return [dict(r) for r in rows]


async def find_vehicle_name_conflict(faction_id: int, new_name: str, vehicle_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT id FROM vehicles WHERE faction_id = $1 AND LOWER(name) = LOWER($2) AND id != $3",
        faction_id, new_name, vehicle_id
    )
    return dict(row) if row else None


async def update_vehicle_name_designation(new_name: Optional[str], designation: Optional[str], vehicle_id: int) -> None:
    await db.execute(
        "UPDATE vehicles SET name = COALESCE($1, name), designation = COALESCE($2, designation) WHERE id = $3",
        new_name, designation, vehicle_id
    )


async def update_vehicle_type(vehicle_id: int, type_id: int) -> None:
    await db.execute("UPDATE vehicles SET type = $1 WHERE id = $2", type_id, vehicle_id)


async def get_fleet_vehicle_total(vehicle_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT SUM(amount) as total FROM fleet_vehicles WHERE vehicle_id = $1", vehicle_id)
    return dict(row) if row else None


async def get_vehicle_construction_total(vehicle_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT SUM(quantity) as total FROM vehicle_construction WHERE vehicle_id = $1 AND completion_date > CURRENT_TIMESTAMP", vehicle_id
    )
    return dict(row) if row else None


async def delete_vehicle(vehicle_id: int) -> None:
    await db.execute("DELETE FROM vehicles WHERE id = $1", vehicle_id)


async def get_vehicle_details(vehicle_id: int) -> Tuple[Optional[Vehicle], List[VehicleCostRow], list]:
    full_vehicle = await db.fetchrow(
        "SELECT v.*, vt.name as type_name FROM vehicles v LEFT JOIN vehicle_types vt ON v.type = vt.id WHERE v.id = $1",
        vehicle_id
    )
    costs = await db.fetch(
        "SELECT r.name, vc.amount FROM vehicle_costs vc JOIN resources r ON vc.resource_id = r.id WHERE vc.vehicle_id = $1",
        vehicle_id
    )
    fleets_with_vehicle = await db.fetch(
        "SELECT f.faction_fleet_number, f.name as fleet_name, fv.amount FROM fleet_vehicles fv JOIN fleets f ON fv.fleet_id = f.id WHERE fv.vehicle_id = $1 ORDER BY f.faction_fleet_number",
        vehicle_id
    )
    return (Vehicle.from_row(full_vehicle) if full_vehicle else None), VehicleCostRow.from_rows(costs), fleets_with_vehicle
