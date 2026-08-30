# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional
from database.db_manager import db
from dtos.fleet import Fleet, FleetDamageInfo, FleetListing


def get_connection():
    return db.get_connection()


async def call_create_fleet(faction_id: int, name: Optional[str], world_id: int) -> dict:
    row = await db.fetchrow(
        "SELECT * FROM sp_create_fleet($1, $2, $3)",
        faction_id, name, world_id
    )
    return dict(row)


async def call_set_fleet_status(fleet_id: int, status_name: str):
    await db.execute("SELECT sp_set_fleet_status($1, $2)", fleet_id, status_name)


async def call_move_fleet(fleet_id: int, destination_id: int, moved_since):
    await db.execute("SELECT sp_move_fleet($1, $2, $3)", fleet_id, destination_id, moved_since)


async def call_add_vehicle_to_fleet(fleet_id: int, vehicle_id: int, amount: int):
    await db.execute("SELECT sp_add_vehicle_to_fleet($1, $2, $3)", fleet_id, vehicle_id, amount)


async def call_refund_vehicle(fleet_id: int, vehicle_id: int, amount: int, refund_faction_id: int, refund_pct: float):
    await db.execute(
        "SELECT sp_refund_vehicle($1, $2, $3, $4, $5)",
        fleet_id, vehicle_id, amount, refund_faction_id, refund_pct
    )


async def call_salvage_fleet(salvager_faction_id: int, debris_fleet_id: int) -> dict:
    row = await db.fetchrow(
        "SELECT sp_salvage_fleet($1, $2) as result",
        salvager_faction_id, debris_fleet_id
    )
    return dict(row['result'])


async def get_fleet_row(fleet_id: int) -> Optional[Fleet]:
    row = await db.fetchrow("""
        SELECT f.id, f.name, f.faction_id, f.faction_fleet_number,
               f.health, f.total_cs, f.status_id, f.infantry_count,
               fs.name as status_name, w.name as position_name, f.position,
               w2.name as moving_to_name, f.moving_since, ft.name as type_name
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        JOIN worlds w ON f.position = w.id
        LEFT JOIN worlds w2 ON f.moving_to = w2.id
        LEFT JOIN fleet_types ft ON f.fleet_type_id = ft.id
        WHERE f.id = $1
    """, fleet_id)
    return Fleet.from_row(row) if row else None


async def get_unit_vehicle_resource_totals_rows(unit_id: int):
    return await db.fetch("""
        SELECT r.name, COALESCE(SUM(vc.amount * fv.amount), 0) as total
        FROM fleet_vehicles fv
        JOIN vehicle_costs vc ON vc.vehicle_id = fv.vehicle_id
        JOIN resources r ON vc.resource_id = r.id
        WHERE fv.fleet_id = $1
        GROUP BY r.name
    """, unit_id)


async def call_buy_vehicle(faction_id: int, world_id: int, fleet_id: int, vehicle_id: int,
                           amount: int, factory_space: int, completion, costs_json: str) -> dict:
    return await db.fetchrow(
        "SELECT sp_buy_vehicle($1,$2,$3,$4,$5,$6,$7,$8::jsonb) as order_id",
        faction_id, world_id, fleet_id, vehicle_id, amount, factory_space, completion,
        costs_json
    )


async def call_refit_vehicle(faction_id: int, fleet_id: int, vehicle_id: int, amount: int,
                             world_id: int, factory_space: int, completion, cost_deltas_json: str) -> dict:
    return await db.fetchrow(
        "SELECT sp_refit_vehicle($1,$2,$3,$4,$5,$6,$7,$8::jsonb) as order_id",
        faction_id, fleet_id, vehicle_id, amount, world_id, factory_space, completion,
        cost_deltas_json
    )


async def call_transfer_vehicle(from_fleet_id: int, to_fleet_id: int, vehicle_id: int, amount: int):
    await db.execute(
        "SELECT sp_transfer_vehicle($1, $2, $3, $4)",
        from_fleet_id, to_fleet_id, vehicle_id, amount
    )


async def get_fleet_by_identifier_row(fleet_identifier: str, faction_id: int) -> Optional[Fleet]:
    row = await db.fetchrow("""
        SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
               f.position, fs.name as status_name, w.name as position_name
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        JOIN worlds w ON f.position = w.id
        WHERE f.faction_id = $1 AND (f.faction_fleet_number::text = $2 OR LOWER(f.name) = LOWER($2))
    """, faction_id, fleet_identifier)
    return Fleet.from_row(row) if row else None


async def rename_fleet(fleet_id: int, new_name: str):
    await db.execute("UPDATE fleets SET name = $1 WHERE id = $2", new_name, fleet_id)


async def delete_fleet(fleet_id: int):
    await db.execute("DELETE FROM fleets WHERE id = $1", fleet_id)


async def get_fleet_vehicles_rows(fleet_id: int):
    return await db.fetch("""
        SELECT v.id as vehicle_id, v.name as vehicle_name, v.designation,
               v.faction_vehicle_number, fv.amount, vt.name as type, v.vehicle_data
        FROM fleet_vehicles fv
        JOIN vehicles v ON fv.vehicle_id = v.id
        LEFT JOIN vehicle_types vt ON v.type = vt.id
        WHERE fv.fleet_id = $1
        ORDER BY v.id
    """, fleet_id)


async def get_fleet_vehicle_count_row(fleet_id: int):
    return await db.fetchrow("""
        SELECT COALESCE(SUM(fv.amount), 0) as total
        FROM fleet_vehicles fv
        JOIN vehicles v ON fv.vehicle_id = v.id
        LEFT JOIN vehicle_types vt ON v.type = vt.id
        WHERE fv.fleet_id = $1 AND LOWER(COALESCE(vt.name, '')) != 'missile'
    """, fleet_id)


async def get_factory_progress_rows_for_world(faction_id: int, world_id: int):
    query = """
        SELECT vc.id, vc.quantity, vc.factory_space_used, vc.completion_date,
               v.name as vehicle_name, w.name as world_name,
               f.name as fleet_name, f.id as fleet_id
        FROM vehicle_construction vc
        JOIN vehicles v ON vc.vehicle_id = v.id
        JOIN worlds w ON vc.world_id = w.id
        JOIN fleets f ON vc.fleet_id = f.id
        WHERE vc.completion_date > CURRENT_TIMESTAMP AND f.faction_id = $1 AND vc.world_id = $2
        ORDER BY vc.completion_date
    """
    return await db.fetch(query, faction_id, world_id)


async def get_factory_progress_rows_all(faction_id: int):
    query = """
        SELECT vc.id, vc.quantity, vc.factory_space_used, vc.completion_date,
               v.name as vehicle_name, w.name as world_name,
               f.name as fleet_name, f.id as fleet_id
        FROM vehicle_construction vc
        JOIN vehicles v ON vc.vehicle_id = v.id
        JOIN worlds w ON vc.world_id = w.id
        JOIN fleets f ON vc.fleet_id = f.id
        WHERE vc.completion_date > CURRENT_TIMESTAMP AND f.faction_id = $1
        ORDER BY w.name, vc.completion_date
    """
    return await db.fetch(query, faction_id)


async def get_fleets(faction_id: Optional[int] = None, world_id: Optional[int] = None) -> List[FleetListing]:
    conditions = []
    args = []
    if faction_id:
        args.append(faction_id)
        conditions.append(f"f.faction_id = ${len(args)}")
    if world_id:
        args.append(world_id)
        conditions.append(f"f.position = ${len(args)}")
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await db.fetch(
        f"""SELECT f.id, f.name, f.faction_fleet_number, fs.name as status,
                  w.name as position, f.position as position_id,
                  w2.name as moving_to_name, f.moving_since,
                  f.health, f.total_cs, f.faction_id,
                  ft.name as type_name,
                  COALESCE(NULLIF(fac.formal_name, ''), fac.name) as faction_name, fac.color as faction_color
           FROM fleets f
           JOIN fleet_status fs ON f.status_id = fs.id
           JOIN worlds w ON f.position = w.id
           JOIN factions fac ON f.faction_id = fac.id
           LEFT JOIN worlds w2 ON f.moving_to = w2.id
           LEFT JOIN fleet_types ft ON f.fleet_type_id = ft.id
           {where} ORDER BY f.faction_fleet_number""",
        *args
    )
    return FleetListing.from_rows(rows)


async def get_fleet_for_damage_row_with_faction(fleet_identifier: str, faction_id) -> Optional[FleetDamageInfo]:
    row = await db.fetchrow("""
        SELECT f.id, f.name, f.faction_id,
               COALESCE(fa.formal_name, fa.name) as faction_name,
               fa.color as faction_color,
               f.health, f.total_cs, fs.name as status_name
        FROM fleets f
        JOIN factions fa ON f.faction_id = fa.id
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE (f.id::text = $1 OR LOWER(f.name) = LOWER($1))
          AND (LOWER(fa.name) = LOWER($2) OR LOWER(fa.formal_name) = LOWER($2))
    """, fleet_identifier, faction_id)
    return FleetDamageInfo.from_row(row) if row else None


async def get_fleet_for_damage_row(fleet_identifier: str) -> Optional[FleetDamageInfo]:
    row = await db.fetchrow("""
        SELECT f.id, f.name, f.faction_id,
               COALESCE(fa.formal_name, fa.name) as faction_name,
               fa.color as faction_color,
               f.health, f.total_cs, fs.name as status_name
        FROM fleets f
        JOIN factions fa ON f.faction_id = fa.id
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE (f.id::text = $1 OR LOWER(f.name) = LOWER($1))
    """, fleet_identifier)
    return FleetDamageInfo.from_row(row) if row else None


async def get_debris_fleets(faction_id: Optional[int] = None, world_id: Optional[int] = None):
    query = """
        SELECT f.id, f.name, f.faction_fleet_number,
               f.faction_id, f.position as world_id,
               COALESCE(NULLIF(fac.formal_name, ''), fac.name) as faction_name,
               w.name as world_name, f.total_cs
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        JOIN factions fac ON f.faction_id = fac.id
        JOIN worlds w ON f.position = w.id
        WHERE LOWER(fs.name) = 'debris'
    """
    args = []

    if faction_id is not None:
        args.append(faction_id)
        query += f" AND f.faction_id = ${len(args)}"

    if world_id is not None:
        args.append(world_id)
        query += f" AND f.position = ${len(args)}"

    query += " ORDER BY f.total_cs DESC"
    return await db.fetch(query, *args)


async def get_factory_capacity_row(world_id: int, faction_id: int, target_building: str, capacity_per_level: int):
    return await db.fetchrow("""
        SELECT COALESCE(SUM(
            CASE WHEN b.name = $3 THEN fwb.amount * fwb.level * $4 ELSE 0 END
        ), 0) as total_capacity
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        WHERE fwb.world_id = $1 AND fwb.faction_id = $2
    """, world_id, faction_id, target_building, capacity_per_level)


async def get_factory_used_space_row(world_id: int, faction_id: int, is_large: bool):
    return await db.fetchrow("""
        SELECT COALESCE(SUM(vc.factory_space_used), 0) as used_space
        FROM vehicle_construction vc
        JOIN vehicles v ON vc.vehicle_id = v.id
        JOIN fleets fl ON vc.fleet_id = fl.id
        WHERE vc.world_id = $1 AND fl.faction_id = $2
          AND vc.completion_date > CURRENT_TIMESTAMP
          AND (CASE WHEN $3 THEN
                   COALESCE(((v.vehicle_data[1])::jsonb->>'length')::numeric, 0) > 1000
               ELSE
                   COALESCE(((v.vehicle_data[1])::jsonb->>'length')::numeric, 0) <= 1000
               END)
    """, world_id, faction_id, is_large)


async def get_ftl_supply_capacity_row(faction_id: int):
    return await db.fetchrow("""
        SELECT COALESCE(SUM(
            CASE WHEN COALESCE(((v.vehicle_data[1])::jsonb->>'ftl')::text, 'NONE') != 'NONE'
                 THEN COALESCE(((v.vehicle_data[1])::jsonb->>'cargo')::numeric, 0) * fv.amount
                 ELSE 0 END
        ), 0) as total_cargo
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        JOIN fleet_vehicles fv ON f.id = fv.fleet_id
        JOIN vehicles v ON fv.vehicle_id = v.id
        WHERE f.faction_id = $1 AND LOWER(fs.name) = 'ftl supply'
    """, faction_id)


async def get_fleet_type_row_by_name(type_name: str):
    return await db.fetchrow("SELECT id FROM fleet_types WHERE LOWER(name) = LOWER($1)", type_name)


async def set_fleet_type(unit_id: int, type_id: int):
    await db.execute("UPDATE fleets SET fleet_type_id = $1 WHERE id = $2", type_id, unit_id)


async def get_total_faction_infantry_row(faction_id: int):
    return await db.fetchrow(
        "SELECT COALESCE(SUM(infantry_count), 0) as total FROM fleets WHERE faction_id = $1",
        faction_id
    )


async def get_resource_id_by_name(conn, name: str):
    return await conn.fetchval("SELECT id FROM resources WHERE name = $1", name)


async def get_local_treasury_total(conn, faction_id: int, resource_id: int):
    return await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM local_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id
    )


async def get_faction_treasury_amount(conn, faction_id: int, resource_id: int):
    return await conn.fetchval(
        "SELECT COALESCE(amount, 0) FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id
    )


async def debit_faction_treasury(conn, faction_id: int, resource_id: int, total_cost):
    await conn.execute(
        "UPDATE faction_treasury SET amount = amount - $3 WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id, total_cost
    )


async def insert_military_recruitment(conn, faction_id: int, amount: int, completion, unit_id: int):
    return await conn.fetchval("""
        INSERT INTO military_recruitment (faction_id, amount, role_name, start_time, completion_time, status, fleet_id)
        VALUES ($1, $2, 'soldiers', CURRENT_TIMESTAMP, $3, 'training', $4)
        RETURNING id
    """, faction_id, amount, completion, unit_id)


async def get_fleet_infantry_count(conn, unit_id: int, faction_id: int):
    return await conn.fetchval(
        "SELECT infantry_count FROM fleets WHERE id = $1 AND faction_id = $2",
        unit_id, faction_id
    )


async def adjust_fleet_infantry_count(conn, unit_id: int, delta: int):
    await conn.execute(
        "UPDATE fleets SET infantry_count = infantry_count - $1 WHERE id = $2",
        delta, unit_id
    )


async def increase_fleet_infantry_count(conn, unit_id: int, delta: int):
    await conn.execute(
        "UPDATE fleets SET infantry_count = infantry_count + $1 WHERE id = $2",
        delta, unit_id
    )


async def distribute_population_by_share(conn, faction_id: int, pop_id: int, total_pop, amount: int):
    await conn.execute("""
        UPDATE local_treasury lt
        SET amount = lt.amount + FLOOR((lt.amount::FLOAT / $3) * $4)
        WHERE lt.faction_id = $1 AND lt.resource_id = $2 AND lt.amount > 0
    """, faction_id, pop_id, total_pop, amount)


async def get_territories_with_population(conn, faction_id: int):
    return await conn.fetch(
        "SELECT world_id, territory FROM world_factions WHERE faction_id = $1 AND territory > 0",
        faction_id
    )


async def add_local_treasury_share(conn, faction_id: int, world_id: int, pop_id: int, share: int):
    await conn.execute("""
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount
    """, faction_id, world_id, pop_id, int(share))


async def fleet_exists_for_faction(conn, fleet_id: int, faction_id: int):
    return await conn.fetchval(
        "SELECT id FROM fleets WHERE id = $1 AND faction_id = $2",
        fleet_id, faction_id
    )
