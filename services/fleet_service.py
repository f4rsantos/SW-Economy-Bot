import asyncpg
import math
from typing import Optional
from database.db_manager import db
from services.building_efficiency_service import calculate_effective_efficiency


async def create_fleet(faction_id: int, name: Optional[str], world_id: int) -> dict:
    try:
        row = await db.fetchrow(
            "SELECT * FROM sp_create_fleet($1, $2, $3)",
            faction_id, name, world_id
        )
        return dict(row)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def set_fleet_status(fleet_id: int, status_name: str):
    try:
        await db.execute("SELECT sp_set_fleet_status($1, $2)", fleet_id, status_name)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def move_fleet(fleet_id: int, destination_id: int, moved_since):
    try:
        await db.execute("SELECT sp_move_fleet($1, $2, $3)", fleet_id, destination_id, moved_since)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def add_vehicle_to_fleet(fleet_id: int, vehicle_id: int, amount: int):
    try:
        await db.execute("SELECT sp_add_vehicle_to_fleet($1, $2, $3)", fleet_id, vehicle_id, amount)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def refund_vehicle(fleet_id: int, vehicle_id: int, amount: int, refund_faction_id: int, refund_pct: float):
    try:
        await db.execute(
            "SELECT sp_refund_vehicle($1, $2, $3, $4, $5)",
            fleet_id, vehicle_id, amount, refund_faction_id, refund_pct
        )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def salvage_fleet(salvager_faction_id: int, debris_fleet_id: int) -> dict:
    try:
        row = await db.fetchrow(
            "SELECT sp_salvage_fleet($1, $2) as result",
            salvager_faction_id, debris_fleet_id
        )
        return dict(row['result'])
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_fleet(fleet_id: int) -> Optional[dict]:
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
    return dict(row) if row else None


async def get_unit_vehicle_resource_totals(unit_id: int) -> dict:
    rows = await db.fetch("""
        SELECT r.name, COALESCE(SUM(vc.amount * fv.amount), 0) as total
        FROM fleet_vehicles fv
        JOIN vehicle_costs vc ON vc.vehicle_id = fv.vehicle_id
        JOIN resources r ON vc.resource_id = r.id
        WHERE fv.fleet_id = $1
        GROUP BY r.name
    """, unit_id)
    return {row['name']: int(row['total']) for row in rows}


async def buy_vehicle(faction_id: int, world_id: int, fleet_id: int, vehicle_id: int,
                      amount: int, factory_space: int, completion, costs: list) -> int:
    import json
    from datetime import datetime, timedelta, timezone
    try:
        row = await db.fetchrow(
            "SELECT sp_buy_vehicle($1,$2,$3,$4,$5,$6,$7,$8::jsonb) as order_id",
            faction_id, world_id, fleet_id, vehicle_id, amount, factory_space, completion,
            json.dumps(costs)
        )
        order_id = row['order_id']
        if hasattr(completion, 'tzinfo'):
            due = completion if completion.tzinfo else completion.replace(tzinfo=timezone.utc)
        else:
            due = completion
        from services.event_queue import event_queue
        await event_queue.push(due, 'construction_complete', {
            'order_id': order_id, 'fleet_id': fleet_id, 'vehicle_id': vehicle_id, 'quantity': amount
        })
        return order_id
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e



async def transfer_vehicle(from_fleet_id: int, to_fleet_id: int, vehicle_id: int, amount: int):
    try:
        await db.execute(
            "SELECT sp_transfer_vehicle($1, $2, $3, $4)",
            from_fleet_id, to_fleet_id, vehicle_id, amount
        )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_fleet_by_identifier(fleet_identifier: str, faction_id: int) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
               f.position, fs.name as status_name, w.name as position_name
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        JOIN worlds w ON f.position = w.id
        WHERE f.faction_id = $1 AND (f.faction_fleet_number::text = $2 OR LOWER(f.name) = LOWER($2))
    """, faction_id, fleet_identifier)


async def rename_fleet(fleet_id: int, new_name: str):
    await db.execute("UPDATE fleets SET name = $1 WHERE id = $2", new_name, fleet_id)


async def delete_fleet(fleet_id: int):
    await db.execute("DELETE FROM fleets WHERE id = $1", fleet_id)


async def get_fleet_vehicles(fleet_id: int) -> list:
    rows = await db.fetch("""
        SELECT v.id as vehicle_id, v.name as vehicle_name, v.designation,
               v.faction_vehicle_number, fv.amount, vt.name as type, v.vehicle_data
        FROM fleet_vehicles fv
        JOIN vehicles v ON fv.vehicle_id = v.id
        LEFT JOIN vehicle_types vt ON v.type = vt.id
        WHERE fv.fleet_id = $1
        ORDER BY v.id
    """, fleet_id)
    return [dict(r) for r in rows]


async def get_fleet_vehicle_count(fleet_id: int) -> int:
    row = await db.fetchrow("""
        SELECT COALESCE(SUM(fv.amount), 0) as total
        FROM fleet_vehicles fv
        JOIN vehicles v ON fv.vehicle_id = v.id
        LEFT JOIN vehicle_types vt ON v.type = vt.id
        WHERE fv.fleet_id = $1 AND LOWER(COALESCE(vt.name, '')) != 'missile'
    """, fleet_id)
    return row['total'] or 0


async def get_factory_progress(faction_id: int, world_id: Optional[int] = None) -> list:
    if world_id:
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
        rows = await db.fetch(query, faction_id, world_id)
    else:
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
        rows = await db.fetch(query, faction_id)
    return [dict(r) for r in rows]


async def get_fleets(faction_id: Optional[int] = None, world_id: Optional[int] = None) -> list:
    conditions = []
    args = []
    if faction_id:
        conditions.append(f"f.faction_id = ${len(args) + 1}")
        args.append(faction_id)
    if world_id:
        conditions.append(f"f.position = ${len(args) + 1}")
        args.append(world_id)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await db.fetch(
        f"""SELECT f.id, f.name, f.faction_fleet_number, fs.name as status,
                  w.name as position, w2.name as moving_to_name, f.moving_since,
                  f.health, f.total_cs, f.faction_id,
                  ft.name as type_name,
                  fac.name as faction_name, fac.color as faction_color
           FROM fleets f
           JOIN fleet_status fs ON f.status_id = fs.id
           JOIN worlds w ON f.position = w.id
           JOIN factions fac ON f.faction_id = fac.id
           LEFT JOIN worlds w2 ON f.moving_to = w2.id
           LEFT JOIN fleet_types ft ON f.fleet_type_id = ft.id
           {where} ORDER BY f.faction_fleet_number""",
        *args
    )
    return [dict(r) for r in rows]


async def get_fleet_for_damage(fleet_identifier: str, faction_id: Optional[int]) -> Optional[dict]:
    if faction_id:
        return await db.fetchrow("""
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
    return await db.fetchrow("""
        SELECT f.id, f.name, f.faction_id,
               COALESCE(fa.formal_name, fa.name) as faction_name,
               fa.color as faction_color,
               f.health, f.total_cs, fs.name as status_name
        FROM fleets f
        JOIN factions fa ON f.faction_id = fa.id
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE (f.id::text = $1 OR LOWER(f.name) = LOWER($1))
    """, fleet_identifier)


async def list_debris_fleets(faction_id: Optional[int] = None, world_id: Optional[int] = None) -> list[dict]:
    query = """
        SELECT f.id, f.name, f.faction_fleet_number,
               fac.name as faction_name, w.name as world_name, f.total_cs
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
    rows = await db.fetch(query, *args)
    return [dict(r) for r in rows]


async def get_factory_info(world_id: int, faction_id: int, is_large: bool) -> tuple[int, int]:
    target_building = 'Mega Factory' if is_large else 'Factory'
    capacity_per_level = 1000 if is_large else 300

    cap_row = await db.fetchrow("""
        SELECT COALESCE(SUM(
            CASE WHEN b.name = $3 THEN fwb.amount * fwb.level * $4 ELSE 0 END
        ), 0) as total_capacity
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        WHERE fwb.world_id = $1 AND fwb.faction_id = $2
    """, world_id, faction_id, target_building, capacity_per_level)

    used_row = await db.fetchrow("""
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

    eff = await calculate_effective_efficiency(faction_id, building_type='factory')
    total = math.floor((cap_row['total_capacity'] or 0) * eff)
    used = used_row['used_space'] or 0
    return int(total), int(used)



async def get_vehicle_length(vehicle_id: int) -> float:
    from services.vehicle_service import get_vehicle_definition
    defn = await get_vehicle_definition(vehicle_id)
    return defn['length'] if defn else 100.0


async def get_vehicle_cost_rows(vehicle_id: int) -> list:
    from services.vehicle_service import get_vehicle_definition
    defn = await get_vehicle_definition(vehicle_id)
    if not defn:
        return []
    return [{'name': name, 'amount': amt} for name, amt in defn['costs'].items()]


async def set_unit_type(unit_id: int, type_name: str):
    from database.static_cache import static_cache
    type_id = static_cache.get_fleet_type_id(type_name)
    if not type_id:
        type_row = await db.fetchrow("SELECT id FROM fleet_types WHERE LOWER(name) = LOWER($1)", type_name)
        if not type_row:
            raise ValueError(f"Unit type '{type_name}' not found.")
        type_id = type_row['id']
    await db.execute("UPDATE fleets SET fleet_type_id = $1 WHERE id = $2", type_id, unit_id)


async def get_total_faction_infantry(faction_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COALESCE(SUM(infantry_count), 0) as total FROM fleets WHERE faction_id = $1",
        faction_id
    )
    return int(row['total']) if row else 0


async def recruit_infantry_to_unit(unit_id: int, faction_id: int, amount: int, costs: dict, completion) -> int:
    async with db.get_connection() as conn:
        async with conn.transaction():
            pop_id = await conn.fetchval("SELECT id FROM resources WHERE name = 'Population'")
            available_pop = await conn.fetchval(
                "SELECT COALESCE(SUM(amount), 0) FROM local_treasury WHERE faction_id = $1 AND resource_id = $2",
                faction_id, pop_id
            )
            if available_pop < amount:
                raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient Population — need {amount:,}, have {available_pop:,}")

            await conn.execute("""
                UPDATE local_treasury lt
                SET amount = lt.amount - FLOOR((lt.amount::FLOAT / $3) * $4)
                WHERE lt.faction_id = $1 AND lt.resource_id = $2 AND lt.amount > 0
            """, faction_id, pop_id, available_pop, amount)

            local_resources = {'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS'}
            for res_name, per_unit in costs.items():
                total_cost = per_unit * amount
                res_id = await conn.fetchval("SELECT id FROM resources WHERE name = $1", res_name)
                if not res_id:
                    raise ValueError(f"RESOURCE_NOT_FOUND: Unknown resource {res_name}")
                if res_name in local_resources:
                    available = await conn.fetchval(
                        "SELECT COALESCE(SUM(amount), 0) FROM local_treasury WHERE faction_id = $1 AND resource_id = $2",
                        faction_id, res_id
                    )
                    if available < total_cost:
                        raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient {res_name} — need {total_cost:,}, have {available:,}")
                    await conn.execute("""
                        UPDATE local_treasury lt
                        SET amount = lt.amount - FLOOR((lt.amount::FLOAT / $3) * $4)
                        WHERE lt.faction_id = $1 AND lt.resource_id = $2 AND lt.amount > 0
                    """, faction_id, res_id, available, total_cost)
                else:
                    available = await conn.fetchval(
                        "SELECT COALESCE(amount, 0) FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
                        faction_id, res_id
                    )
                    if available < total_cost:
                        raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient {res_name} — need {total_cost:,}, have {available:,}")
                    await conn.execute(
                        "UPDATE faction_treasury SET amount = amount - $3 WHERE faction_id = $1 AND resource_id = $2",
                        faction_id, res_id, total_cost
                    )

            rec_id = await conn.fetchval("""
                INSERT INTO military_recruitment (faction_id, amount, role_name, start_time, completion_time, status, fleet_id)
                VALUES ($1, $2, 'soldiers', CURRENT_TIMESTAMP, $3, 'training', $4)
                RETURNING id
            """, faction_id, amount, completion, unit_id)
            return rec_id


async def dismiss_infantry_from_unit(unit_id: int, faction_id: int, amount: int):
    async with db.get_connection() as conn:
        async with conn.transaction():
            current = await conn.fetchval(
                "SELECT infantry_count FROM fleets WHERE id = $1 AND faction_id = $2",
                unit_id, faction_id
            )
            if current is None:
                raise ValueError("Unit not found.")
            if current < amount:
                raise ValueError(f"INSUFFICIENT_INFANTRY: Unit has {current:,} infantry, cannot dismiss {amount:,}.")

            await conn.execute(
                "UPDATE fleets SET infantry_count = infantry_count - $1 WHERE id = $2",
                amount, unit_id
            )

            pop_id = await conn.fetchval("SELECT id FROM resources WHERE name = 'Population'")
            total_pop = await conn.fetchval(
                "SELECT COALESCE(SUM(amount), 0) FROM local_treasury WHERE faction_id = $1 AND resource_id = $2",
                faction_id, pop_id
            )
            if total_pop > 0:
                await conn.execute("""
                    UPDATE local_treasury lt
                    SET amount = lt.amount + FLOOR((lt.amount::FLOAT / $3) * $4)
                    WHERE lt.faction_id = $1 AND lt.resource_id = $2 AND lt.amount > 0
                """, faction_id, pop_id, total_pop, amount)
            else:
                territories = await conn.fetch(
                    "SELECT world_id, territory FROM world_factions WHERE faction_id = $1 AND territory > 0",
                    faction_id
                )
                total_territory = sum(t['territory'] for t in territories)
                if total_territory > 0:
                    for t in territories:
                        share = (t['territory'] / total_territory) * amount
                        await conn.execute("""
                            INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (faction_id, world_id, resource_id)
                            DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount
                        """, faction_id, t['world_id'], pop_id, int(share))


async def transfer_infantry_between_units(from_unit_id: int, to_unit_id: int, faction_id: int, amount: int):
    async with db.get_connection() as conn:
        async with conn.transaction():
            from_infantry = await conn.fetchval(
                "SELECT infantry_count FROM fleets WHERE id = $1 AND faction_id = $2",
                from_unit_id, faction_id
            )
            if from_infantry is None:
                raise ValueError("Source unit not found or does not belong to this faction.")
            if from_infantry < amount:
                raise ValueError(f"Source unit only has {from_infantry:,} infantry.")

            to_check = await conn.fetchval(
                "SELECT id FROM fleets WHERE id = $1 AND faction_id = $2",
                to_unit_id, faction_id
            )
            if not to_check:
                raise ValueError("Destination unit not found or does not belong to this faction.")

            await conn.execute(
                "UPDATE fleets SET infantry_count = infantry_count - $1 WHERE id = $2",
                amount, from_unit_id
            )
            await conn.execute(
                "UPDATE fleets SET infantry_count = infantry_count + $1 WHERE id = $2",
                amount, to_unit_id
            )
