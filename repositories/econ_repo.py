# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
import json
from datetime import datetime
from typing import Optional
from database.db_manager import db


async def get_producible_resource_by_name_upper(resource_upper: str) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT r.id, r.name FROM resources r
        WHERE UPPER(r.name) = $1
          AND EXISTS (SELECT 1 FROM buildings_generators bg WHERE bg.resource_id = r.id LIMIT 1)
        """,
        resource_upper,
    )
    return dict(row) if row else None


async def get_storable_resource_by_name_upper(resource_upper: str) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT r.id, r.name FROM resources r
        WHERE UPPER(r.name) = $1
          AND EXISTS (SELECT 1 FROM buildings_storages bs WHERE bs.resource_id = r.id LIMIT 1)
        """,
        resource_upper,
    )
    return dict(row) if row else None


async def get_resource_ids_by_names(resource_names: list[str]) -> dict[str, dict]:
    lower_names = [n.lower() for n in resource_names]
    rows = await db.fetch("SELECT id, name, is_transferable FROM resources WHERE LOWER(name) = ANY($1)", lower_names)
    return {r['name']: {'id': r['id'], 'is_transferable': r['is_transferable']} for r in rows}


async def get_world_capacities_for_resource(faction_id: int, resource_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT w.name AS world_name, bg.is_refinery, bg.percentage_affects, bg.production,
               COALESCE(SUM(fwb.amount * fwb.level), 0) AS total_buildings,
               COALESCE(wr.percentage, 100) AS resource_percentage
        FROM worlds w
        JOIN world_factions wf ON wf.world_id = w.id AND wf.faction_id = $1
        LEFT JOIN faction_world_buildings fwb ON fwb.world_id = w.id AND fwb.faction_id = $1
        LEFT JOIN buildings_generators bg ON bg.building_id = fwb.building_id AND bg.resource_id = $2
        LEFT JOIN world_resources wr ON wr.world_id = w.id AND wr.resource_id = $2
        GROUP BY w.id, w.name, bg.is_refinery, bg.percentage_affects, bg.production, wr.percentage
        ORDER BY w.name
        """,
        faction_id,
        resource_id,
    )
    return [dict(r) for r in rows]


async def get_capacity_rows_for_world(faction_id: int, world_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT r.name, bg.is_refinery, bg.percentage_affects, bg.production,
               COALESCE(SUM(fwb.amount * fwb.level), 0) as total_buildings,
               COALESCE(wr.percentage, 100) as resource_percentage
        FROM resources r
        LEFT JOIN buildings_generators bg ON r.id = bg.resource_id
        LEFT JOIN faction_world_buildings fwb ON bg.building_id = fwb.building_id AND fwb.faction_id = $1 AND fwb.world_id = $2
        LEFT JOIN world_resources wr ON wr.world_id = $2 AND wr.resource_id = r.id
        WHERE r.name IN ('CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS')
        GROUP BY r.id, r.name, bg.is_refinery, bg.percentage_affects, bg.production, wr.percentage
        ORDER BY r.id
        """,
        faction_id,
        world_id,
    )
    return [dict(r) for r in rows]


async def get_capacity_rows_overall(faction_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT r.name, bg.is_refinery, bg.percentage_affects, bg.production, fwb.world_id,
               COALESCE(SUM(fwb.amount * fwb.level), 0) as total_buildings,
               COALESCE(wr.percentage, 100) as resource_percentage
        FROM resources r
        LEFT JOIN buildings_generators bg ON r.id = bg.resource_id
        LEFT JOIN faction_world_buildings fwb ON bg.building_id = fwb.building_id AND fwb.faction_id = $1
        LEFT JOIN world_resources wr ON wr.world_id = fwb.world_id AND wr.resource_id = r.id
        WHERE r.name IN ('CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS')
        GROUP BY r.id, r.name, bg.is_refinery, bg.percentage_affects, bg.production, fwb.world_id, wr.percentage
        ORDER BY r.name
        """,
        faction_id,
    )
    return [dict(r) for r in rows]


async def get_factory_capacity(faction_id: int, world_id: Optional[int] = None) -> int:
    if world_id is not None:
        row = await db.fetchrow(
            """
            SELECT COALESCE(SUM(fwb.amount * fwb.level * 200), 0) as c FROM faction_world_buildings fwb
            JOIN buildings b ON fwb.building_id = b.id
            WHERE fwb.faction_id = $1 AND fwb.world_id = $2 AND b.name LIKE '%Factory%' AND b.name != 'Mega Factory'
            """,
            faction_id,
            world_id,
        )
    else:
        row = await db.fetchrow(
            """
            SELECT COALESCE(SUM(fwb.amount * fwb.level * 200), 0) as c FROM faction_world_buildings fwb
            JOIN buildings b ON fwb.building_id = b.id
            WHERE fwb.faction_id = $1 AND b.name LIKE '%Factory%' AND b.name != 'Mega Factory'
            """,
            faction_id,
        )
    return row['c'] or 0


async def get_mega_factory_capacity(faction_id: int, world_id: Optional[int] = None) -> int:
    if world_id is not None:
        row = await db.fetchrow(
            """
            SELECT COALESCE(SUM(fwb.amount * fwb.level * 1000), 0) as c FROM faction_world_buildings fwb
            JOIN buildings b ON fwb.building_id = b.id
            WHERE fwb.faction_id = $1 AND fwb.world_id = $2 AND b.name = 'Mega Factory'
            """,
            faction_id,
            world_id,
        )
    else:
        row = await db.fetchrow(
            """
            SELECT COALESCE(SUM(fwb.amount * fwb.level * 1000), 0) as c FROM faction_world_buildings fwb
            JOIN buildings b ON fwb.building_id = b.id
            WHERE fwb.faction_id = $1 AND b.name = 'Mega Factory'
            """,
            faction_id,
        )
    return row['c'] or 0


async def get_world_storage_for_resource(faction_id: int, resource_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT w.name AS world_name,
               COALESCE(SUM(bs.storage * fwb.amount * fwb.level), 0) AS capacity
        FROM worlds w
        JOIN world_factions wf ON wf.world_id = w.id AND wf.faction_id = $1
        LEFT JOIN faction_world_buildings fwb ON fwb.world_id = w.id AND fwb.faction_id = $1
        LEFT JOIN buildings_storages bs ON bs.building_id = fwb.building_id AND bs.resource_id = $2
        GROUP BY w.id, w.name
        ORDER BY capacity DESC, w.name
        """,
        faction_id,
        resource_id,
    )
    return [dict(r) for r in rows]


async def get_storage_rows_for_world(faction_id: int, world_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT r.name, COALESCE(SUM(bs.storage * fwb.amount * fwb.level), 0) as capacity
        FROM resources r
        LEFT JOIN buildings_storages bs ON r.id = bs.resource_id
        LEFT JOIN faction_world_buildings fwb ON bs.building_id = fwb.building_id
            AND fwb.faction_id = $1 AND fwb.world_id = $2
        WHERE r.name IN ('CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS')
        GROUP BY r.id, r.name ORDER BY r.id
        """,
        faction_id,
        world_id,
    )
    return [dict(r) for r in rows]


async def get_storage_rows_overall(faction_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT r.name, COALESCE(SUM(bs.storage * fwb.amount * fwb.level), 0) as capacity
        FROM resources r
        LEFT JOIN buildings_storages bs ON r.id = bs.resource_id
        LEFT JOIN faction_world_buildings fwb ON bs.building_id = fwb.building_id AND fwb.faction_id = $1
        WHERE r.name IN ('CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS')
        GROUP BY r.id, r.name ORDER BY r.id
        """,
        faction_id,
    )
    return [dict(r) for r in rows]


async def get_max_population_capacity(faction_id: int, world_id: Optional[int] = None) -> int:
    if world_id is not None:
        row = await db.fetchrow(
            """
            SELECT
                COALESCE(wf.territory, 0) * COALESCE(w.population_capacity_per_hex, 0)
                + COALESCE((
                    SELECT SUM(500000 * fwb.amount * fwb.level)
                    FROM faction_world_buildings fwb
                    WHERE fwb.faction_id = $1 AND fwb.world_id = $2 AND fwb.building_id = 1
                ), 0) AS max_pop
            FROM world_factions wf
            JOIN worlds w ON w.id = wf.world_id
            WHERE wf.faction_id = $1 AND wf.world_id = $2
            """,
            faction_id,
            world_id,
        )
    else:
        row = await db.fetchrow(
            """
            SELECT
                COALESCE(SUM(COALESCE(wf.territory, 0) * COALESCE(w.population_capacity_per_hex, 0)), 0)
                + COALESCE((
                    SELECT SUM(500000 * fwb.amount * fwb.level)
                    FROM faction_world_buildings fwb
                    WHERE fwb.faction_id = $1 AND fwb.building_id = 1
                ), 0) AS max_pop
            FROM world_factions wf
            JOIN worlds w ON w.id = wf.world_id
            WHERE wf.faction_id = $1
            """,
            faction_id,
        )
    return row['max_pop'] if row else 0


async def get_resource_treasury_scope(resource_upper: str) -> dict:
    local_check = await db.fetchrow(
        """
        SELECT r.id FROM resources r WHERE UPPER(r.name) = $1
        AND EXISTS (SELECT 1 FROM local_treasury lt WHERE lt.resource_id = r.id LIMIT 1)
        """,
        resource_upper,
    )
    global_check = await db.fetchrow(
        """
        SELECT r.id FROM resources r WHERE UPPER(r.name) = $1
        AND EXISTS (SELECT 1 FROM faction_treasury ft WHERE ft.resource_id = r.id LIMIT 1)
        """,
        resource_upper,
    )
    return {'is_local': local_check is not None, 'is_global': global_check is not None}


async def get_local_resource_by_world(faction_id: int, resource_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT w.name AS world_name, COALESCE(lt.amount, 0) AS amount
        FROM worlds w
        JOIN world_factions wf ON wf.world_id = w.id AND wf.faction_id = $1
        LEFT JOIN local_treasury lt ON lt.world_id = w.id AND lt.faction_id = $1 AND lt.resource_id = $2
        ORDER BY amount DESC, w.name
        """,
        faction_id,
        resource_id,
    )
    return [dict(r) for r in rows]


async def get_global_resource_amount(faction_id: int, resource_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COALESCE(amount, 0) AS amount FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id,
        resource_id,
    )
    return row['amount'] if row else 0


async def get_local_treasury_for_world(faction_id: int, world_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT r.name, COALESCE(lt.amount, 0) as amount
        FROM local_treasury lt
        JOIN resources r ON r.id = lt.resource_id
        WHERE lt.faction_id = $1 AND lt.world_id = $2
        ORDER BY r.id
        """,
        faction_id,
        world_id,
    )
    return [dict(r) for r in rows]


async def get_global_treasury(faction_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT r.name, COALESCE(ft.amount, 0) as amount
        FROM faction_treasury ft
        JOIN resources r ON r.id = ft.resource_id
        WHERE ft.faction_id = $1
        ORDER BY r.id
        """,
        faction_id,
    )
    return [dict(r) for r in rows]


async def get_local_treasury_aggregated(faction_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT r.name, COALESCE(SUM(lt.amount), 0) as amount
        FROM local_treasury lt
        JOIN resources r ON r.id = lt.resource_id
        WHERE lt.faction_id = $1
        GROUP BY r.id, r.name
        ORDER BY r.id
        """,
        faction_id,
    )
    return [dict(r) for r in rows]


async def get_population_rows_by_faction(faction_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT lt.world_id, COALESCE(lt.amount, 0) as population
        FROM local_treasury lt JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
        """,
        faction_id,
    )
    return [dict(r) for r in rows]


async def recruit_military(faction_id: int, personnel_amount: int, role_name: str, costs: dict, completion: datetime):
    try:
        await db.execute(
            "SELECT sp_recruit_military($1, $2, $3, $4::jsonb, $5)",
            faction_id,
            personnel_amount,
            role_name,
            json.dumps(costs),
            completion,
        )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def dismiss_military(faction_id: int, personnel_amount: int):
    try:
        await db.execute("SELECT sp_dismiss_military($1, $2)", faction_id, personnel_amount)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def execute_vesta_trade(faction_id: int, world_id: int, expected_resource: str, total_in: int, gain_amount: int, gain: str):
    try:
        await db.execute(
            "SELECT sp_vesta_trade($1, $2, $3, $4, $5, $6)",
            faction_id,
            world_id,
            expected_resource,
            total_in,
            gain_amount,
            gain,
        )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e
