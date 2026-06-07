from typing import Optional
from database.db_manager import db


async def get_world(world_name: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, name, hex_count, population_capacity_per_hex FROM worlds WHERE LOWER(name) = LOWER($1)", world_name)
    return dict(row) if row else None


async def get_world_by_id(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, name, hex_count, population_capacity_per_hex FROM worlds WHERE id = $1", world_id)
    return dict(row) if row else None


async def get_worlds_by_ids(world_ids: list[int]) -> list[dict]:
    if not world_ids:
        return []
    rows = await db.fetch("SELECT id, name FROM worlds WHERE id = ANY($1::int[])", world_ids)
    return [dict(r) for r in rows]


async def search_world_names(current: str, limit: int = 25) -> list[str]:
    rows = await db.fetch(
        "SELECT name FROM worlds WHERE LOWER(name) LIKE $1 ORDER BY name LIMIT $2",
        f"%{current.lower()}%",
        limit,
    )
    return [r['name'] for r in rows]


async def add_world(name: str, orbit_of_id: int, hex_count: int, population_capacity_per_hex: int,
                    background: Optional[str], resource_percentages: dict) -> dict:
    row = await db.fetchrow("""
        INSERT INTO worlds (name, orbit_of, background, population_capacity_per_hex, hex_count)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
    """, name, orbit_of_id, background, population_capacity_per_hex, hex_count)
    world_id = row['id']
    for res_name, percentage in resource_percentages.items():
        res_data = await db.fetchrow("SELECT id FROM resources WHERE name = $1", res_name)
        if res_data:
            await db.execute("INSERT INTO world_resources (world_id, resource_id, percentage) VALUES ($1, $2, $3)", world_id, res_data['id'], percentage)
    return {'world_id': world_id}


async def delete_world(world_id: int, world_name: str) -> dict:
    children = await db.fetchrow("SELECT COUNT(*) as count FROM worlds WHERE orbit_of = $1", world_id)
    if (children['count'] or 0) > 0:
        raise ValueError(f"{children['count']} world(s) orbit {world_name}. Delete them first.")
    fleets_count = await db.fetchrow("SELECT COUNT(*) as count FROM fleets WHERE position = $1", world_id)
    fleet_count = fleets_count['count'] or 0
    if fleet_count > 0:
        await db.execute("DELETE FROM fleets WHERE position = $1", world_id)
    await db.execute("DELETE FROM worlds WHERE id = $1", world_id)
    return {'fleets_deleted': fleet_count}


async def get_world_asset_counts(world_id: int) -> dict:
    fleets_data = await db.fetchrow("SELECT COUNT(*) as count FROM fleets WHERE position = $1", world_id)
    terr_data = await db.fetchrow("SELECT COUNT(*) as count FROM world_factions WHERE world_id = $1", world_id)
    bldg_data = await db.fetchrow("SELECT COALESCE(SUM(amount), 0) as count FROM faction_world_buildings WHERE world_id = $1", world_id)
    return {
        'fleets': fleets_data['count'] or 0,
        'territory': terr_data['count'] or 0,
        'buildings': bldg_data['count'] or 0,
    }


async def rename_world(world_id: int, new_name: str):
    if await db.fetchrow("SELECT id FROM worlds WHERE LOWER(name) = LOWER($1)", new_name):
        raise ValueError(f"World named '{new_name}' already exists.")
    await db.execute("UPDATE worlds SET name = $2 WHERE id = $1", world_id, new_name)


async def modify_world(world_id: int, world_data: dict, hex_count: Optional[int], population_capacity_per_hex: Optional[int],
                       background: Optional[str], orbit_of_id: Optional[int], resource_updates: dict):
    if hex_count is not None and hex_count < world_data['hex_count']:
        claimed_data = await db.fetchrow("SELECT COALESCE(SUM(territory), 0) as claimed FROM world_factions WHERE world_id = $1", world_id)
        if hex_count < (claimed_data['claimed'] or 0):
            raise ValueError(f"Cannot reduce hex count to {hex_count:,}. {claimed_data['claimed']:,} hexes already claimed.")
    updates = []
    params = [world_id]
    param_count = 2
    if hex_count is not None:
        updates.append(f"hex_count = ${param_count}")
        params.append(hex_count)
        param_count += 1
    if population_capacity_per_hex is not None:
        updates.append(f"population_capacity_per_hex = ${param_count}")
        params.append(population_capacity_per_hex)
        param_count += 1
    if background is not None:
        updates.append(f"background = ${param_count}")
        params.append(background)
        param_count += 1
    if orbit_of_id is not None:
        if orbit_of_id == world_id:
            raise ValueError("World cannot orbit itself.")
        updates.append(f"orbit_of = ${param_count}")
        params.append(orbit_of_id)
        param_count += 1
    if updates:
        await db.execute(f"UPDATE worlds SET {', '.join(updates)} WHERE id = $1", *params)
    for res_name, percentage in resource_updates.items():
        res_data = await db.fetchrow("SELECT id FROM resources WHERE name = $1", res_name)
        if res_data:
            await db.execute("""
                INSERT INTO world_resources (world_id, resource_id, percentage) VALUES ($1, $2, $3)
                ON CONFLICT (world_id, resource_id) DO UPDATE SET percentage = $3
            """, world_id, res_data['id'], percentage)


async def claim_hex(faction_id: int, world_id: int, world_name: str, max_hexes: int, hexes: int) -> dict:
    current_territory = await db.fetchrow("SELECT COALESCE(territory, 0) as territory FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id)
    has_presence = current_territory and current_territory['territory'] > 0
    if not has_presence:
        fleet_check = await db.fetchrow("SELECT EXISTS (SELECT 1 FROM fleets f WHERE f.faction_id = $1 AND f.position = $2) as has_fleet", faction_id, world_id)
        if not fleet_check['has_fleet']:
            raise ValueError(f"To claim your first hex on {world_name}, you need a fleet present on the world.")
    influence_cost = hexes * 20
    influence_data = await db.fetchrow("""
        SELECT COALESCE(amount, 0) as influence FROM faction_treasury ft
        JOIN resources r ON ft.resource_id = r.id
        WHERE ft.faction_id = $1 AND r.name = 'Influence'
    """, faction_id)
    current_influence = influence_data['influence'] if influence_data else 0
    if current_influence < influence_cost:
        raise ValueError(f"Need {influence_cost:,} Influence, have {current_influence:,}.")
    claimed_data = await db.fetchrow("SELECT COALESCE(SUM(territory), 0) as claimed FROM world_factions WHERE world_id = $1", world_id)
    current_claimed = claimed_data['claimed'] or 0
    if current_claimed + hexes > max_hexes:
        raise ValueError(f"Only {max_hexes - current_claimed} hex(es) available on {world_name}.")
    world_system = await db.fetchrow("""
        WITH RECURSIVE system_tree AS (
            SELECT id, orbit_of, name FROM worlds WHERE id = $1
            UNION ALL
            SELECT w.id, w.orbit_of, w.name FROM worlds w
            INNER JOIN system_tree st ON w.id = st.orbit_of
        )
        SELECT name FROM system_tree WHERE orbit_of IS NULL
    """, world_id)
    system_name = world_system['name'] if world_system else None
    if system_name:
        presence_check = await db.fetchrow("""
            SELECT EXISTS (
                SELECT 1 FROM world_factions wf JOIN worlds w ON wf.world_id = w.id
                WHERE wf.faction_id = $1 AND wf.territory > 0
                AND w.id IN (
                    WITH RECURSIVE system_worlds AS (
                        SELECT id FROM worlds WHERE orbit_of = (SELECT id FROM worlds WHERE name = $2 AND orbit_of IS NULL)
                        UNION ALL
                        SELECT w.id FROM worlds w INNER JOIN system_worlds sw ON w.orbit_of = sw.id
                    )
                    SELECT id FROM system_worlds
                    UNION ALL SELECT id FROM worlds WHERE name = $2 AND orbit_of IS NULL
                )
            ) as has_presence
        """, faction_id, system_name)
        has_local_presence = presence_check['has_presence'] if presence_check else False
        if not has_local_presence:
            elsewhere_check = await db.fetchrow("SELECT EXISTS (SELECT 1 FROM world_factions wf WHERE wf.faction_id = $1 AND wf.territory > 0) as has_hexes", faction_id)
            if elsewhere_check['has_hexes']:
                ftl_result = await db.fetchrow("""
                    SELECT
                        COALESCE(SUM(CASE WHEN COALESCE(((v.vehicle_data[1])::jsonb->>'ftl')::text, 'NONE') != 'NONE'
                            THEN COALESCE(((v.vehicle_data[1])::jsonb->>'length')::numeric, 0) * fv.amount ELSE 0 END), 0) as total_ftl_length,
                        COALESCE(SUM(CASE WHEN COALESCE(((v.vehicle_data[1])::jsonb->>'ftl')::text, 'NONE') != 'NONE'
                            THEN COALESCE(((v.vehicle_data[1])::jsonb->>'cargo')::numeric, 0) * fv.amount ELSE 0 END), 0) as total_ftl_cargo
                    FROM fleets f
                    JOIN fleet_vehicles fv ON f.id = fv.fleet_id
                    JOIN vehicles v ON fv.vehicle_id = v.id
                    WHERE f.faction_id = $1
                """, faction_id)
                total_ftl_length = ftl_result['total_ftl_length'] if ftl_result else 0
                total_ftl_cargo = ftl_result['total_ftl_cargo'] if ftl_result else 0
                if total_ftl_length < 1000 or total_ftl_cargo < 250000:
                    raise ValueError(
                        f"Claiming hexes in a new solar system requires at least 1,000m of FTL ship length "
                        f"(have: {total_ftl_length:,.0f}m) and 250,000 FTL cargo capacity (have: {total_ftl_cargo:,.0f})."
                    )
    influence_res = await db.fetchrow("SELECT id FROM resources WHERE name = 'Influence'")
    if influence_res:
        await db.execute("UPDATE faction_treasury SET amount = amount - $3 WHERE faction_id = $1 AND resource_id = $2", faction_id, influence_res['id'], influence_cost)
    await db.execute("""
        INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, $3)
        ON CONFLICT (world_id, faction_id) DO UPDATE SET territory = world_factions.territory + EXCLUDED.territory
    """, world_id, faction_id, hexes)
    new_total = (current_territory['territory'] if current_territory else 0) + hexes
    return {'influence_cost': influence_cost, 'new_total': new_total}


async def unclaim_hex(faction_id: int, world_id: int, world_name: str, hexes: int) -> dict:
    territory_data = await db.fetchrow("SELECT territory FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id)
    if not territory_data:
        raise ValueError(f"Faction has no hexes on {world_name}.")
    current_hexes = territory_data['territory']
    if hexes > current_hexes:
        raise ValueError(f"Cannot unclaim {hexes} hex(es). Only have {current_hexes} claimed.")
    buildings_data = await db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM faction_world_buildings WHERE faction_id = $1 AND world_id = $2", faction_id, world_id)
    total_buildings = buildings_data['total'] or 0
    remaining_hexes = current_hexes - hexes
    if remaining_hexes < total_buildings:
        raise ValueError(f"Cannot unclaim {hexes} hex(es). Need at least {total_buildings} hex(es) for {total_buildings} building(s).")
    if remaining_hexes == 0:
        await db.execute("DELETE FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id)
    else:
        await db.execute("UPDATE world_factions SET territory = territory - $3 WHERE world_id = $1 AND faction_id = $2", world_id, faction_id, hexes)
    return {'remaining_hexes': remaining_hexes, 'total_buildings': total_buildings}


async def get_faction_land(faction_id: int) -> list:
    rows = await db.fetch("""
        SELECT w.name, wf.territory FROM world_factions wf
        JOIN worlds w ON wf.world_id = w.id
        WHERE wf.faction_id = $1 AND wf.territory > 0
        ORDER BY wf.territory DESC, w.name
    """, faction_id)
    return [dict(r) for r in rows]


async def get_world_factions(world_id: int) -> list:
    rows = await db.fetch("""
        SELECT COALESCE(f.formal_name, f.name) as display_name, wf.territory, f.color
        FROM world_factions wf
        JOIN factions f ON wf.faction_id = f.id
        WHERE wf.world_id = $1 AND wf.territory > 0
        ORDER BY wf.territory DESC, display_name
    """, world_id)
    return [dict(r) for r in rows]


async def has_faction_presence(world_id: int, faction_id: int) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM world_factions WHERE world_id = $1 AND faction_id = $2",
        world_id,
        faction_id,
    )
    return row is not None
