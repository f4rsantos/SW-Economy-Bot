# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db
from database.static_cache import static_cache
from typing import Dict, List, Optional


INTELLIGENCE_SHARING_PACT_TYPE = 'Intelligence Sharing'
INTELLIGENCE_SHARING_INFLUENCE_SINGLE_MODE = 10
INTELLIGENCE_SHARING_INFLUENCE_BOTH_MODES = 15


async def fetch_pact_types_for_faction(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT pt.name as pact_type,
            CASE WHEN pt.name = $2::text THEN
                (CASE WHEN pis.domestic AND pis.foreign_alerts THEN $4::bigint ELSE $3::bigint END)
                * COALESCE(pw.world_count, 0)
                * GREATEST(COALESCE(pmc.member_count, 1) - 1, 0)
            ELSE pt.influence_cost END as influence_cost
        FROM pact_members pm
        JOIN pacts p ON pm.pact_id = p.id
        JOIN pact_types pt ON p.pact_type_id = pt.id
        LEFT JOIN pact_intelligence_sharing pis ON pis.pact_id = p.id
        LEFT JOIN (
            SELECT pact_id, COUNT(*) as world_count FROM pact_worlds GROUP BY pact_id
        ) pw ON pw.pact_id = p.id
        LEFT JOIN (
            SELECT pact_id, COUNT(*) as member_count FROM pact_members GROUP BY pact_id
        ) pmc ON pmc.pact_id = p.id
        WHERE pm.faction_id = $1
    """, faction_id, INTELLIGENCE_SHARING_PACT_TYPE,
         INTELLIGENCE_SHARING_INFLUENCE_SINGLE_MODE, INTELLIGENCE_SHARING_INFLUENCE_BOTH_MODES)


async def fetch_fleet_cs_by_status(faction_id: int, status_ids: dict) -> Dict:
    idle_id       = status_ids.get('idle', -1)
    defence_id    = status_ids.get('defence', -1)
    patrol_id     = status_ids.get('patrol', -1)
    travelling_id = status_ids.get('travelling', -1)
    ftl_supply_id = status_ids.get('ftl supply', -1)
    battle_id     = status_ids.get('battle', -1)
    mothballed_id = status_ids.get('mothballed', -1)
    debris_id     = status_ids.get('debris', -1)

    query = f"""
        SELECT
            COALESCE(SUM(CASE WHEN status_id = {idle_id} THEN total_cs ELSE 0 END), 0) as idle_cs,
            COALESCE(SUM(CASE WHEN status_id IN ({defence_id}, {patrol_id}, {travelling_id}, {ftl_supply_id}) THEN total_cs ELSE 0 END), 0) as defence_patrol_cs,
            COALESCE(SUM(CASE WHEN status_id = {battle_id} THEN total_cs ELSE 0 END), 0) as battle_cs,
            COALESCE(SUM(CASE WHEN status_id = {mothballed_id} THEN total_cs ELSE 0 END), 0) as mothballed_cs
        FROM fleets
        WHERE faction_id = $1 AND status_id != {debris_id}
    """
    return await db.fetchrow(query, faction_id)


async def fetch_fleet_cs_rows(faction_id: int, debris_status_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT id, position, status_id, total_cs
        FROM fleets
        WHERE faction_id = $1 AND status_id != $2
    """, faction_id, debris_status_id)


async def fetch_status_ids() -> Dict[str, int]:
    rows = await db.fetch("SELECT id, name FROM fleet_status")
    return {r['name'].lower(): r['id'] for r in rows}


async def fetch_non_debris_fleets(faction_id: int, debris_status_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT f.id, f.name, f.health, f.total_cs, f.status_id, f.position, fs.name as status_name
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE f.faction_id = $1 AND f.status_id != $2
        ORDER BY
            CASE
                WHEN fs.name IN ('battle', 'in combat', 'blockading') THEN 1
                WHEN fs.name IN ('defence', 'patrol') THEN 2
                WHEN fs.name = 'idle' THEN 3
                WHEN fs.name = 'mothballed' THEN 4
                ELSE 5
            END,
            f.total_cs DESC
    """, faction_id, debris_status_id)


async def fetch_population_cs_by_world(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT lt.world_id, COALESCE(lt.amount, 0) as population
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """, faction_id)


async def fetch_outgoing_trades(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT td.id, td.receiver_faction_id, td.amount, r.name as resource_name, r.id as resource_id
        FROM trade_deals td
        JOIN resources r ON td.resource_id = r.id
        WHERE td.sender_faction_id = $1
        ORDER BY td.id ASC
    """, faction_id)


async def fetch_external_incoming_trades(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT td.id, td.sender_faction_id, td.amount, r.name as resource_name, r.id as resource_id
        FROM trade_deals td
        JOIN resources r ON td.resource_id = r.id
        WHERE td.receiver_faction_id = $1 AND td.sender_faction_id != $1
        ORDER BY td.id ASC
    """, faction_id)


async def fetch_all_trade_deals(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT td.id, td.receiver_faction_id, td.sender_world_id, td.receiver_world_id,
               td.escort_fleet_id,
               td.amount, r.name as resource_name, r.id as resource_id
        FROM trade_deals td
        JOIN resources r ON td.resource_id = r.id
        WHERE td.sender_faction_id = $1
        ORDER BY td.id ASC
    """, faction_id)


async def fetch_unrefined_production_data(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT
            fwb.world_id,
            r.name as resource_name,
            wr.percentage,
            COALESCE(SUM(fwb.amount * fwb.level * bg.production), 0) as total_production
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        JOIN buildings_generators bg ON b.id = bg.building_id
        JOIN resources r ON bg.resource_id = r.id
        JOIN world_resources wr ON fwb.world_id = wr.world_id AND wr.resource_id = r.id
        WHERE fwb.faction_id = $1 AND b.name LIKE '%Extractor%'
        GROUP BY fwb.world_id, r.name, wr.percentage
    """, faction_id)


async def fetch_refined_capacity_data(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT
            fwb.world_id,
            r.name as resource_name,
            COALESCE(SUM(fwb.amount * fwb.level * bg.production), 0) as total_capacity
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        JOIN buildings_generators bg ON b.id = bg.building_id
        JOIN resources r ON bg.resource_id = r.id
        WHERE fwb.faction_id = $1 AND bg.is_refinery = true
        GROUP BY fwb.world_id, r.name
    """, faction_id)


async def fetch_local_stock(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT lt.world_id, r.name, lt.amount
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name IN ('U-CM', 'U-EL', 'U-CS', 'CM', 'EL', 'CS')
    """, faction_id)


async def fetch_refined_stock(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT lt.world_id, r.name, lt.amount
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name IN ('CM', 'EL', 'CS')
    """, faction_id)


async def fetch_storage_capacities(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT
            fwb.world_id,
            r.name as resource_name,
            COALESCE(SUM(bs.storage * fwb.amount * fwb.level), 0) as total_storage
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        JOIN buildings_storages bs ON b.id = bs.building_id
        JOIN resources r ON bs.resource_id = r.id
        WHERE fwb.faction_id = $1
        GROUP BY fwb.world_id, r.name
    """, faction_id)


async def fetch_er_treasury(faction_id: int) -> int:
    result = await db.fetchrow("""
        SELECT COALESCE(SUM(ft.amount), 0) as treasury
        FROM faction_treasury ft
        JOIN resources r ON ft.resource_id = r.id
        WHERE ft.faction_id = $1 AND r.name = 'ER'
    """, faction_id)
    return int(result['treasury'] or 0)


async def fetch_total_population(faction_id: int) -> int:
    result = await db.fetchrow("""
        SELECT COALESCE(SUM(lt.amount), 0) as total_population
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """, faction_id)
    return int(result['total_population'] or 0)


async def fetch_faction_population_limit(faction_id: int) -> Optional[int]:
    result = await db.fetchrow("SELECT population_limit FROM factions WHERE id = $1", faction_id)
    return result['population_limit'] if result and result['population_limit'] is not None else None


async def fetch_total_army(faction_id: int) -> int:
    result = await db.fetchrow("""
        SELECT COALESCE(SUM(lt.amount), 0) as total_army
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Military'
    """, faction_id)
    return int(result['total_army'] or 0)


async def fetch_faction_flags(faction_id: int) -> Dict:
    return await db.fetchrow("SELECT faction_type, capital_world_id, (faction_type = 1) as is_company FROM factions WHERE id = $1", faction_id)


async def fetch_hex_count(faction_id: int) -> int:
    result = await db.fetchrow("""
        SELECT COALESCE(SUM(territory), 0) as total_hexes
        FROM world_factions WHERE faction_id = $1
    """, faction_id)
    return int(result['total_hexes'] or 0)


async def fetch_weighted_hex_count(faction_id: int) -> int:
    capital_row = await db.fetchrow("SELECT capital_world_id FROM factions WHERE id = $1", faction_id)
    capital_world_id = capital_row['capital_world_id'] if capital_row else None
    if capital_world_id is None:
        return await fetch_hex_count(faction_id)
    result = await db.fetchrow("""
        WITH RECURSIVE capital_root AS (
            SELECT id, orbit_of FROM worlds WHERE id = $2
            UNION ALL
            SELECT w.id, w.orbit_of FROM worlds w INNER JOIN capital_root cr ON w.id = cr.orbit_of
        ),
        root AS (SELECT id FROM capital_root WHERE orbit_of IS NULL LIMIT 1),
        capital_system AS (
            SELECT id FROM worlds WHERE id = (SELECT id FROM root)
            UNION ALL
            SELECT w.id FROM worlds w INNER JOIN capital_system cs ON w.orbit_of = cs.id
        )
        SELECT COALESCE(SUM(
            CASE WHEN wf.world_id IN (SELECT id FROM capital_system) THEN wf.territory
                 ELSE wf.territory * 5 END
        ), 0) as weighted_hexes
        FROM world_factions wf
        WHERE wf.faction_id = $1
    """, faction_id, capital_world_id)
    return int(result['weighted_hexes'] or 0)


async def fetch_current_influence(faction_id: int) -> int:
    result = await db.fetchrow("""
        SELECT COALESCE(amount, 0) as current
        FROM faction_treasury ft
        JOIN resources r ON ft.resource_id = r.id
        WHERE ft.faction_id = $1 AND r.name = 'Influence'
    """, faction_id)
    return int(result['current'] if result else 0)


async def fetch_world_population(faction_id: int, world_id: int) -> int:
    result = await db.fetchrow("""
        SELECT COALESCE(lt.amount, 0) as population
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND lt.world_id = $2 AND r.name = 'Population'
    """, faction_id, world_id)
    return int(result['population'] if result else 0)


async def fetch_blockaded_world_ids(faction_id: int) -> set:
    rows = await db.fetch("""
        SELECT DISTINCT b.world_id
        FROM blockades b
        JOIN blockade_targets bt ON b.id = bt.blockade_id
        WHERE bt.faction_id = $1 AND b.date_end IS NULL
    """, faction_id)
    return {r['world_id'] for r in rows}


async def fetch_worlds_with_cs(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT lt.world_id, COALESCE(lt.amount, 0) as cs_amount
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'CS' AND lt.amount > 0
        ORDER BY lt.amount DESC
    """, faction_id)


async def fetch_stored_cs(faction_id: int, cs_resource_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT world_id, amount FROM local_treasury
        WHERE faction_id = $1 AND resource_id = $2
    """, faction_id, cs_resource_id)


async def fetch_world_data_for_income(faction_id: int, is_company: bool) -> Dict[int, Dict]:
    rows = await db.fetch("""
        SELECT
            wf.world_id,
            COALESCE(lt_pop.amount, 0) AS population,
            COALESCE(lt_army.amount, 0) AS army,
            COALESCE(wf.territory, 0) * COALESCE(w.population_capacity_per_hex, 0)
            + COALESCE((
                SELECT SUM(500000 * fwb2.amount * fwb2.level)
                FROM faction_world_buildings fwb2
                WHERE fwb2.faction_id = $1 AND fwb2.world_id = wf.world_id AND fwb2.building_id = (SELECT id FROM buildings WHERE name = 'City')
            ), 0) AS pop_cap
        FROM world_factions wf
        JOIN worlds w ON w.id = wf.world_id
        LEFT JOIN (
            SELECT lt.world_id, lt.amount FROM local_treasury lt
            JOIN resources r ON lt.resource_id = r.id
            WHERE lt.faction_id = $1 AND r.name = 'Population'
        ) lt_pop ON lt_pop.world_id = wf.world_id
        LEFT JOIN (
            SELECT lt.world_id, lt.amount FROM local_treasury lt
            JOIN resources r ON lt.resource_id = r.id
            WHERE lt.faction_id = $1 AND r.name = 'Military'
        ) lt_army ON lt_army.world_id = wf.world_id
        WHERE wf.faction_id = $1
    """, faction_id)

    world_data: Dict[int, Dict] = {
        r['world_id']: {
            'population': r['population'],
            'army': r['army'],
            'pop_cap': r['pop_cap'],
        }
        for r in rows
    }

    if is_company:
        building_rows = await db.fetch("""
            SELECT DISTINCT world_id FROM faction_world_buildings WHERE faction_id = $1
        """, faction_id)
        for bw in building_rows:
            if bw['world_id'] not in world_data:
                world_data[bw['world_id']] = {'population': 0, 'army': 0, 'pop_cap': 0}

    return world_data


async def fetch_all_world_names() -> Dict[int, str]:
    rows = await db.fetch("SELECT id, name FROM worlds")
    return {r['id']: r['name'] for r in rows}


async def fetch_best_destination_worlds(faction_ids: list) -> Dict[int, int]:
    if not faction_ids:
        return {}

    population_rows = await db.fetch("""
        SELECT DISTINCT ON (lt.faction_id) lt.faction_id, lt.world_id
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = ANY($1) AND r.name = 'Population'
        ORDER BY lt.faction_id, lt.amount DESC
    """, faction_ids)
    destinations = {r['faction_id']: r['world_id'] for r in population_rows}

    remaining = [fid for fid in faction_ids if fid not in destinations]
    if not remaining:
        return destinations

    building_rows = await db.fetch("""
        SELECT DISTINCT ON (faction_id) faction_id, world_id
        FROM (
            SELECT faction_id, world_id, COUNT(*) as building_count
            FROM faction_world_buildings
            WHERE faction_id = ANY($1)
            GROUP BY faction_id, world_id
        ) counts
        ORDER BY faction_id, building_count DESC
    """, remaining)
    for row in building_rows:
        destinations[row['faction_id']] = row['world_id']

    return destinations


async def fetch_best_destination_world(faction_id: int):
    result = await db.fetchrow("""
        SELECT lt.world_id FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
        ORDER BY lt.amount DESC LIMIT 1
    """, faction_id)
    if result:
        return result['world_id']

    result = await db.fetchrow("""
        SELECT world_id FROM faction_world_buildings
        WHERE faction_id = $1
        GROUP BY world_id ORDER BY COUNT(*) DESC LIMIT 1
    """, faction_id)
    if result:
        return result['world_id']

    result = await db.fetchrow("""
        SELECT world_id FROM world_factions WHERE faction_id = $1 LIMIT 1
    """, faction_id)
    return result['world_id'] if result else None


async def fetch_resource_map() -> Dict[str, int]:
    if static_cache.loaded:
        return {r['name']: r['id'] for r in static_cache.resources_by_id.values()}
    rows = await db.fetch("SELECT id, name FROM resources")
    return {r['name']: r['id'] for r in rows}


async def fetch_population_rows_by_world(faction_id: int) -> List[Dict]:
    return await db.fetch("""
        SELECT lt.world_id, COALESCE(lt.amount, 0) as population
        FROM local_treasury lt JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """, faction_id)


async def fetch_city_levels_by_world(faction_id: int) -> Dict[int, List[int]]:
    rows = await db.fetch("""
        SELECT fwb.world_id, fwb.level, fwb.amount
        FROM faction_world_buildings fwb
        JOIN buildings b ON b.id = fwb.building_id
        WHERE fwb.faction_id = $1 AND b.name = 'City'
    """, faction_id)
    result: Dict[int, List[int]] = {}
    for row in rows:
        levels = result.setdefault(row['world_id'], [])
        levels.extend([row['level']] * row['amount'])
    return result


async def fetch_level_10_building_count(faction_id: int) -> int:
    result = await db.fetchrow("""
        SELECT COALESCE(SUM(amount), 0) as total_count
        FROM faction_world_buildings
        WHERE faction_id = $1 AND level = 10
    """, faction_id)
    return int(result['total_count'] or 0)


async def fetch_debris_status_id() -> Optional[int]:
    row = await db.fetchrow("SELECT id FROM fleet_status WHERE LOWER(name) = 'debris'")
    return row['id'] if row else None


async def apply_fleet_damage(updates: list) -> None:
    await db.executemany("UPDATE fleets SET health = $1 WHERE id = $2", updates)


async def mark_fleets_as_debris(debris_status_id: int, fleet_ids: list) -> None:
    await db.executemany(
        "UPDATE fleets SET health = 0, status_id = $1 WHERE id = $2",
        [(debris_status_id, fleet_id) for fleet_id in fleet_ids],
    )


async def apply_income_cycle(faction_id: int, er_delta, influence_delta,
                             local_deltas: str, population_deltas: str,
                             transfers_payload: str) -> None:
    await db.execute(
        "SELECT sp_apply_income_cycle($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb)",
        faction_id,
        er_delta,
        influence_delta,
        local_deltas,
        population_deltas,
        transfers_payload,
    )


async def fetch_all_population_by_world(faction_id: int) -> Dict[int, int]:
    rows = await db.fetch("""
        SELECT lt.world_id, COALESCE(lt.amount, 0) as pop
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """, faction_id)
    return {r['world_id']: r['pop'] for r in rows}
