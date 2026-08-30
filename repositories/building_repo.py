# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import json
from typing import Dict, List, Optional, Tuple

from database.db_manager import db
from dtos.building import (
    Building,
    BuildingCostRow,
    CatalogBuilding,
    FactionBuildingStats,
)


WEIGHT_EXPRESSION = """
    CASE
        WHEN b.name = 'City' THEN fwb.amount * fwb.level * 0.1
        WHEN bg.is_refinery THEN fwb.amount * fwb.level * 1.5
        WHEN bs.building_id IS NOT NULL THEN fwb.amount * fwb.level * 5
        WHEN b.name LIKE '%Mega Factory%' THEN fwb.amount * fwb.level * 5
        WHEN b.name LIKE '%Factory%' THEN fwb.amount * fwb.level * 2
        ELSE fwb.amount * fwb.level
    END
"""

TYPE_EXPRESSION = """
    CASE
        WHEN b.name = 'City' THEN 'city'
        WHEN bg.is_refinery THEN 'refinery'
        WHEN bg.building_id IS NOT NULL AND NOT bg.is_refinery THEN 'extractor'
        WHEN bs.building_id IS NOT NULL THEN 'storage'
        WHEN b.name LIKE '%Factory%' THEN 'factory'
        ELSE 'other'
    END
"""


async def get_building(building_id: int) -> Optional[Building]:
    row = await db.fetchrow("SELECT id, name FROM buildings WHERE id = $1", building_id)
    return Building.from_row(row) if row else None


async def get_building_by_name(building_name: str) -> Optional[Building]:
    row = await db.fetchrow(
        "SELECT id, name FROM buildings WHERE LOWER(name) = LOWER($1)", building_name
    )
    return Building.from_row(row) if row else None


async def search_building_names(current: str, limit: int = 25) -> List[Building]:
    rows = await db.fetch(
        "SELECT id, name FROM buildings WHERE LOWER(name) LIKE $1 ORDER BY name LIMIT $2",
        f"%{current.lower()}%",
        limit,
    )
    return Building.from_rows(rows)


async def find_buildings_matching(text: str) -> List[Building]:
    rows = await db.fetch(
        "SELECT id, name FROM buildings WHERE name ILIKE $1 ORDER BY name", f"%{text}%"
    )
    return Building.from_rows(rows)


async def get_buildings_catalog() -> List[CatalogBuilding]:
    rows = await db.fetch("""
        SELECT b.id, b.name, b.description, b.is_generator,
               bg.production, bg.is_refinery, bg.percentage_affects,
               r.name as resource_name, bs.storage
        FROM buildings b
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        LEFT JOIN resources r ON bg.resource_id = r.id OR bs.resource_id = r.id
        ORDER BY b.id
    """)
    return CatalogBuilding.from_rows(rows)


async def get_all_building_cost_rows() -> List[BuildingCostRow]:
    rows = await db.fetch("""
        SELECT bc.building_id, r.name, bc.amount FROM building_costs bc
        JOIN resources r ON bc.resource_id = r.id ORDER BY bc.building_id, r.name
    """)
    return BuildingCostRow.from_rows(rows)


async def get_faction_building_ids_at_level(faction_id: int, level: int) -> set:
    rows = await db.fetch(
        "SELECT DISTINCT building_id FROM faction_world_buildings WHERE faction_id = $1 AND level = $2",
        faction_id,
        level,
    )
    return {r["building_id"] for r in rows}


async def get_building_ids_supporting_level(level: int) -> set:
    rows = await db.fetch("""
        SELECT building_id FROM buildings_generators WHERE max_levels >= $1
        UNION
        SELECT building_id FROM buildings_storages WHERE max_levels >= $1
    """, level)
    return {r["building_id"] for r in rows}


async def get_faction_mega_factory_count(faction_id: int) -> int:
    row = await db.fetchrow(
        """
        SELECT COALESCE(SUM(fwb.amount), 0) as total
        FROM faction_world_buildings fwb
        JOIN buildings b ON b.id = fwb.building_id
        WHERE fwb.faction_id = $1 AND b.name = 'Mega Factory'
        """,
        faction_id,
    )
    return int(row["total"]) if row else 0


async def get_building_base_costs(building_id: int) -> Dict[str, int]:
    rows = await db.fetch("""
        SELECT r.name, bc.amount FROM building_costs bc
        JOIN resources r ON bc.resource_id = r.id
        WHERE bc.building_id = $1
    """, building_id)
    return {r["name"]: r["amount"] for r in rows}


async def get_company_er(faction_id: int) -> int:
    row = await db.fetchrow("""
        SELECT COALESCE(SUM(ft.amount), 0) as total FROM faction_treasury ft
        JOIN resources r ON ft.resource_id = r.id
        WHERE ft.faction_id = $1 AND r.name = 'ER'
    """, faction_id)
    return (row["total"] or 0) if row else 0


async def get_faction_worlds_with_resource_percentages(faction_id: int) -> List[dict]:
    rows = await db.fetch("""
        SELECT w.id as world_id, w.name as world_name,
               substring(r.name from 3) as resource_name, wr.percentage
        FROM world_factions wf
        JOIN worlds w ON w.id = wf.world_id
        JOIN world_resources wr ON wr.world_id = w.id
        JOIN resources r ON r.id = wr.resource_id
        WHERE wf.faction_id = $1 AND r.name IN ('U-CM', 'U-EL', 'U-CS')
        ORDER BY w.name, r.name
    """, faction_id)
    return [dict(r) for r in rows]


async def faction_has_presence(world_id: int, faction_id: int) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM world_factions WHERE world_id = $1 AND faction_id = $2",
        world_id,
        faction_id,
    )
    return row is not None


async def ensure_world_presence(world_id: int, faction_id: int) -> None:
    await db.execute(
        "INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, 0) ON CONFLICT DO NOTHING",
        world_id,
        faction_id,
    )


async def get_faction_building_count_unweighted(faction_id: int) -> int:
    row = await db.fetchrow("""
        SELECT COALESCE(SUM(fwb.amount * fwb.level), 0) as total_count
        FROM faction_world_buildings fwb
        WHERE fwb.faction_id = $1
    """, faction_id)
    return int(row["total_count"]) if row else 0


async def get_faction_building_count_actual(faction_id: int) -> int:
    row = await db.fetchrow("""
        SELECT COALESCE(SUM(fwb.amount), 0) as total_count
        FROM faction_world_buildings fwb
        WHERE fwb.faction_id = $1
    """, faction_id)
    return int(row["total_count"]) if row else 0


async def get_faction_building_count_split(faction_id: int) -> Tuple[int, int]:
    row = await db.fetchrow("""
        SELECT
            COALESCE(SUM(CASE WHEN b.name LIKE '%Factory%' THEN fwb.amount * fwb.level ELSE 0 END), 0) as factory_count,
            COALESCE(SUM(CASE WHEN b.name LIKE '%Factory%' THEN 0 ELSE fwb.amount * fwb.level END), 0) as other_count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        WHERE fwb.faction_id = $1
    """, faction_id)
    if not row:
        return 0, 0
    return int(row["factory_count"]), int(row["other_count"])


async def get_faction_building_count_weighted(faction_id: int) -> int:
    row = await db.fetchrow(f"""
        SELECT SUM({WEIGHT_EXPRESSION}) as total_count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        WHERE fwb.faction_id = $1
    """, faction_id)
    return round(row["total_count"]) if row and row["total_count"] else 0


async def get_faction_total_population(faction_id: int) -> int:
    row = await db.fetchrow("""
        SELECT COALESCE(SUM(lt.amount), 0) as total_population
        FROM local_treasury lt
        INNER JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """, faction_id)
    return int(row["total_population"]) if row else 0


async def get_faction_total_hexes(faction_id: int) -> int:
    row = await db.fetchrow("""
        SELECT COALESCE(SUM(territory), 0) as total_hexes
        FROM world_factions
        WHERE faction_id = $1
    """, faction_id)
    return int(row["total_hexes"]) if row else 0


async def get_faction_population_by_world(faction_id: int) -> List[dict]:
    rows = await db.fetch("""
        SELECT lt.world_id, COALESCE(lt.amount, 0) as population
        FROM local_treasury lt
        JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """, faction_id)
    return [dict(r) for r in rows]


async def get_faction_infantry_count(faction_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COALESCE(SUM(infantry_count), 0) as total FROM fleets WHERE faction_id = $1",
        faction_id,
    )
    return int(row["total"]) if row else 0


async def get_faction_building_stats(faction_id: int) -> FactionBuildingStats:
    rows = await db.fetch(f"""
        SELECT
            COALESCE(rg.name, rs.name) as resource_name,
            {TYPE_EXPRESSION} as building_type,
            SUM(fwb.amount * fwb.level) as unweighted,
            SUM(fwb.amount) as actual,
            SUM({WEIGHT_EXPRESSION}) as weighted
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        LEFT JOIN resources rg ON bg.resource_id = rg.id
        LEFT JOIN resources rs ON bs.resource_id = rs.id
        WHERE fwb.faction_id = $1
        GROUP BY COALESCE(rg.name, rs.name), building_type
    """, faction_id)

    total_unweighted = 0
    total_weighted = 0
    total_actual = 0
    by_resource: Dict[str, int] = {}
    by_resource_weighted: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    by_type_weighted: Dict[str, int] = {}

    for row in rows:
        unweighted = int(row["unweighted"] or 0)
        weighted = round(row["weighted"] or 0)
        actual = int(row["actual"] or 0)

        total_unweighted += unweighted
        total_weighted += weighted
        total_actual += actual

        building_type = row["building_type"]
        by_type[building_type] = by_type.get(building_type, 0) + unweighted
        by_type_weighted[building_type] = by_type_weighted.get(building_type, 0) + weighted

        resource_name = row["resource_name"]
        if resource_name:
            base_resource = resource_name.replace("U-", "")
            by_resource[base_resource] = by_resource.get(base_resource, 0) + unweighted
            by_resource_weighted[base_resource] = by_resource_weighted.get(base_resource, 0) + weighted

    return FactionBuildingStats(
        total_unweighted=total_unweighted,
        total_weighted=total_weighted,
        total_actual=total_actual,
        by_resource=by_resource,
        by_resource_weighted=by_resource_weighted,
        by_type=by_type,
        by_type_weighted=by_type_weighted,
    )


async def buy_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int, total_costs: dict) -> None:
    await db.execute(
        "SELECT sp_buy_building($1, $2, $3, $4, $5, $6::jsonb)",
        faction_id,
        world_id,
        building_id,
        amount,
        level,
        json.dumps(total_costs),
    )


async def destroy_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int) -> None:
    await db.execute(
        "SELECT sp_destroy_building($1, $2, $3, $4, $5)",
        faction_id,
        world_id,
        building_id,
        amount,
        level,
    )


async def refund_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int, refunds: dict) -> None:
    await db.execute(
        "SELECT sp_refund_building($1, $2, $3, $4, $5, $6::jsonb)",
        faction_id,
        world_id,
        building_id,
        amount,
        level,
        json.dumps(refunds),
    )


async def list_faction_buildings(
    faction_id: int,
    world_id: Optional[int] = None,
    building_id: Optional[int] = None,
) -> List[dict]:
    query = """
        SELECT b.id, b.name, fwb.amount, fwb.level, fwb.world_id, w.name as world_name
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        JOIN worlds w ON fwb.world_id = w.id
        WHERE fwb.faction_id = $1
    """
    params = [faction_id]

    if world_id:
        query += f" AND fwb.world_id = ${len(params) + 1}"
        params.append(world_id)
    if building_id:
        query += f" AND fwb.building_id = ${len(params) + 1}"
        params.append(building_id)

    query += " ORDER BY w.name, b.name"
    rows = await db.fetch(query, *params)
    return [dict(r) for r in rows]


async def transfer_building(from_faction_id: int, to_faction_id: int, world_id: int, building_id: int, amount: int, level: int) -> None:
    await db.execute(
        "SELECT sp_transfer_building($1, $2, $3, $4, $5, $6)",
        from_faction_id,
        to_faction_id,
        world_id,
        building_id,
        amount,
        level,
    )
