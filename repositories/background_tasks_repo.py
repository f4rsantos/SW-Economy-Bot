# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional

from database.db_manager import db


def get_connection():
    return db.get_connection()


async def get_transfer_status(transfer_id: int):
    return await db.fetchrow("""
        SELECT ts.name FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        WHERE rt.id = $1
    """, transfer_id)


async def get_transfer_resources(transfer_id: int):
    return await db.fetch("SELECT resource_id, amount FROM transfer_resources WHERE transfer_id = $1", transfer_id)


async def deposit_local_treasury(to_faction_id: int, to_world_id: int, resource_id: int, amount: int) -> None:
    await db.execute(
        """
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount
        """,
        to_faction_id, to_world_id, resource_id, amount
    )


async def delete_transfer_resources(transfer_id: int) -> None:
    await db.execute("DELETE FROM transfer_resources WHERE transfer_id = $1", transfer_id)


async def delete_resource_transfer(transfer_id: int) -> str:
    return await db.execute("DELETE FROM resource_transfers WHERE id = $1", transfer_id)


async def complete_fleet_arrival(fleet_id: int) -> None:
    await db.execute(
        """
        UPDATE fleets
        SET position = moving_to, moving_to = NULL, moving_since = NULL, status_id = 1
        WHERE id = $1 AND moving_to IS NOT NULL
        """,
        fleet_id
    )


async def add_fleet_vehicles(conn, fleet_id: int, vehicle_id: int, quantity: int) -> None:
    await conn.execute(
        """
        INSERT INTO fleet_vehicles (fleet_id, vehicle_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT (fleet_id, vehicle_id)
        DO UPDATE SET amount = fleet_vehicles.amount + EXCLUDED.amount
        """,
        fleet_id, vehicle_id, quantity
    )


async def recalc_fleet_cs(conn, fleet_id: int) -> None:
    await conn.execute(
        """
        UPDATE fleets
        SET total_cs = (
            SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
            FROM fleet_vehicles fv
            JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
            JOIN resources r ON vc.resource_id = r.id
            WHERE fv.fleet_id = fleets.id AND r.name = 'CS'
        )
        WHERE id = $1
        """,
        fleet_id
    )


async def delete_construction_order(conn, order_id: int) -> str:
    return await conn.execute("DELETE FROM vehicle_construction WHERE id = $1", order_id)


async def delete_completed_recruitment(recruitment_id: int) -> str:
    return await db.execute("DELETE FROM military_recruitment WHERE id = $1 AND status = 'training'", recruitment_id)


async def add_fleet_infantry(fleet_id: int, amount: int) -> None:
    await db.execute("UPDATE fleets SET infantry_count = infantry_count + $1 WHERE id = $2", amount, fleet_id)


async def get_settings() -> Optional[dict]:
    return await db.fetchrow("SELECT last_income, income_day FROM settings LIMIT 1")


async def insert_initial_settings(income_date) -> None:
    await db.execute("INSERT INTO settings (last_income, income_day) VALUES ($1, 6)", income_date)


async def set_last_income(income_date) -> None:
    await db.execute("UPDATE settings SET last_income = $1", income_date)


async def get_factions() -> list:
    return await db.fetch("SELECT id, name, (faction_type = 1) as is_company FROM factions")
