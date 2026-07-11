from database.db_manager import db
from services.national_spirit_service import get_active_factory_efficiency_bonus
from typing import Dict, Tuple
import math


async def get_faction_building_count_unweighted(faction_id: int) -> int:
    query = """
        SELECT COALESCE(SUM(fwb.amount * fwb.level), 0) as total_count
        FROM faction_world_buildings fwb
        WHERE fwb.faction_id = $1
    """
    result = await db.fetchrow(query, faction_id)
    return int(result['total_count']) if result else 0


async def get_faction_building_count_actual(faction_id: int) -> int:
    query = """
        SELECT COALESCE(SUM(fwb.amount), 0) as total_count
        FROM faction_world_buildings fwb
        WHERE fwb.faction_id = $1
    """
    result = await db.fetchrow(query, faction_id)
    return int(result['total_count']) if result else 0


async def get_faction_building_count_split(faction_id: int) -> Tuple[int, int]:
    query = """
        SELECT
            COALESCE(SUM(CASE WHEN b.name LIKE '%Factory%' THEN fwb.amount * fwb.level ELSE 0 END), 0) as factory_count,
            COALESCE(SUM(CASE WHEN b.name LIKE '%Factory%' THEN 0 ELSE fwb.amount * fwb.level END), 0) as other_count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        WHERE fwb.faction_id = $1
    """
    result = await db.fetchrow(query, faction_id)
    if not result:
        return 0, 0
    return int(result['factory_count']), int(result['other_count'])


async def get_faction_building_count_weighted(faction_id: int) -> int:
    query = """
        SELECT
            SUM(
                CASE
                    WHEN bg.is_refinery THEN fwb.amount * fwb.level * 1.5
                    WHEN bs.building_id IS NOT NULL THEN fwb.amount * fwb.level * 5
                    WHEN b.name LIKE '%Mega Factory%' THEN fwb.amount * fwb.level * 5
                    WHEN b.name LIKE '%Factory%' THEN fwb.amount * fwb.level * 2
                    ELSE fwb.amount * fwb.level
                END
            ) as total_count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        WHERE fwb.faction_id = $1
    """
    result = await db.fetchrow(query, faction_id)
    return int(result['total_count']) if result and result['total_count'] else 0


async def get_faction_total_population(faction_id: int) -> int:
    query = """
        SELECT COALESCE(SUM(lt.amount), 0) as total_population
        FROM local_treasury lt
        INNER JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """
    result = await db.fetchrow(query, faction_id)
    return int(result['total_population']) if result else 0


async def get_faction_total_hexes(faction_id: int) -> int:
    query = """
        SELECT COALESCE(SUM(territory), 0) as total_hexes
        FROM world_factions
        WHERE faction_id = $1
    """
    result = await db.fetchrow(query, faction_id)
    return int(result['total_hexes']) if result else 0


async def calculate_building_cap(faction_id: int) -> int:
    total_hexes = await get_faction_total_hexes(faction_id)
    if total_hexes == 0:
        return 0
    cap = 172 * math.pow(total_hexes, 0.2)
    return int(cap)


async def calculate_efficiency(faction_id: int) -> float:
    factory_count, other_count = await get_faction_building_count_split(faction_id)
    building_count = factory_count + other_count

    if building_count <= 500:
        return 1.0

    other_free = min(other_count, 500)
    other_over = other_count - other_free
    factory_over = max(factory_count - (500 - other_free), 0)

    decline = other_over * 0.001 + factory_over * 0.0005
    linear_value = 1.0 - decline
    if linear_value >= 0.10:
        return linear_value

    total_over = other_over + factory_over
    avg_rate = decline / total_over if total_over else 0.001
    over = (decline - 0.90) / avg_rate if avg_rate else 0
    return max(0.05 + 0.05 * math.exp(-avg_rate * over), 0.001)


async def get_building_breakdown(faction_id: int) -> Dict[str, int]:
    resource_query = """
        SELECT
            COALESCE(rg.name, rs.name) as resource_name,
            SUM(fwb.amount * fwb.level) as count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN resources rg ON bg.resource_id = rg.id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        LEFT JOIN resources rs ON bs.resource_id = rs.id
        WHERE fwb.faction_id = $1
        AND COALESCE(rg.name, rs.name) IS NOT NULL
        GROUP BY COALESCE(rg.name, rs.name)
    """
    resource_results = await db.fetch(resource_query, faction_id)

    by_resource = {}
    for row in resource_results:
        base_resource = row['resource_name'].replace('U-', '')
        by_resource[base_resource] = by_resource.get(base_resource, 0) + int(row['count'])

    resource_weighted_query = """
        SELECT
            COALESCE(rg.name, rs.name) as resource_name,
            SUM(
                CASE
                    WHEN bg.is_refinery THEN fwb.amount * fwb.level * 1.5
                    WHEN bs.building_id IS NOT NULL THEN fwb.amount * fwb.level * 5
                    WHEN b.name LIKE '%Mega Factory%' THEN fwb.amount * fwb.level * 5
                    WHEN b.name LIKE '%Factory%' THEN fwb.amount * fwb.level * 2
                    ELSE fwb.amount * fwb.level
                END
            ) as count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        LEFT JOIN resources rg ON bg.resource_id = rg.id
        LEFT JOIN resources rs ON bs.resource_id = rs.id
        WHERE fwb.faction_id = $1
        AND COALESCE(rg.name, rs.name) IS NOT NULL
        GROUP BY COALESCE(rg.name, rs.name)
    """
    resource_weighted_results = await db.fetch(resource_weighted_query, faction_id)

    by_resource_weighted = {}
    for row in resource_weighted_results:
        base_resource = row['resource_name'].replace('U-', '')
        by_resource_weighted[base_resource] = by_resource_weighted.get(base_resource, 0) + int(row['count'])

    type_query = """
        SELECT
            CASE
                WHEN b.name = 'City' THEN 'city'
                WHEN bg.is_refinery THEN 'refinery'
                WHEN bg.building_id IS NOT NULL AND NOT bg.is_refinery THEN 'extractor'
                WHEN bs.building_id IS NOT NULL THEN 'storage'
                WHEN b.name LIKE '%Factory%' THEN 'factory'
                ELSE 'other'
            END as building_type,
            SUM(fwb.amount * fwb.level) as count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        WHERE fwb.faction_id = $1
        GROUP BY building_type
    """
    type_results = await db.fetch(type_query, faction_id)
    by_type = {row['building_type']: int(row['count']) for row in type_results}

    type_weighted_query = """
        SELECT
            CASE
                WHEN b.name = 'City' THEN 'city'
                WHEN bg.is_refinery THEN 'refinery'
                WHEN bg.building_id IS NOT NULL AND NOT bg.is_refinery THEN 'extractor'
                WHEN bs.building_id IS NOT NULL THEN 'storage'
                WHEN b.name LIKE '%Factory%' THEN 'factory'
                ELSE 'other'
            END as building_type,
            SUM(
                CASE
                    WHEN bg.is_refinery THEN fwb.amount * fwb.level * 1.5
                    WHEN bs.building_id IS NOT NULL THEN fwb.amount * fwb.level * 5
                    WHEN b.name LIKE '%Mega Factory%' THEN fwb.amount * fwb.level * 5
                    WHEN b.name LIKE '%Factory%' THEN fwb.amount * fwb.level * 2
                    ELSE fwb.amount * fwb.level
                END
            ) as count
        FROM faction_world_buildings fwb
        JOIN buildings b ON fwb.building_id = b.id
        LEFT JOIN buildings_generators bg ON b.id = bg.building_id
        LEFT JOIN buildings_storages bs ON b.id = bs.building_id
        WHERE fwb.faction_id = $1
        GROUP BY building_type
    """
    type_weighted_results = await db.fetch(type_weighted_query, faction_id)
    by_type_weighted = {row['building_type']: int(row['count']) for row in type_weighted_results}

    total_unweighted = await get_faction_building_count_unweighted(faction_id)

    return {
        'total': total_unweighted,
        'by_resource': by_resource,
        'by_type': by_type,
        'by_resource_weighted': by_resource_weighted,
        'by_type_weighted': by_type_weighted
    }


async def detect_specialization(faction_id: int) -> Tuple[bool, str, float]:
    breakdown = await get_building_breakdown(faction_id)
    total_weighted = await get_faction_building_count_weighted(faction_id)

    if total_weighted == 0:
        return False, '', 0.0

    threshold = total_weighted * 0.5

    for resource, count in breakdown['by_resource_weighted'].items():
        if count >= threshold:
            return True, resource, 0.075

    for building_type, count in breakdown['by_type_weighted'].items():
        if building_type != 'other' and count >= threshold:
            return True, building_type, 0.075

    return False, '', 0.0


async def calculate_effective_efficiency(faction_id: int, building_type: str = None, resource_name: str = None) -> float:
    base_efficiency = await calculate_efficiency(faction_id)
    is_specialized, spec_type, bonus = await detect_specialization(faction_id)
    factory_bonus = await get_active_factory_efficiency_bonus(faction_id) if building_type == 'factory' else 0.0

    if not is_specialized:
        return max(base_efficiency + factory_bonus, 0.001)

    matches_specialization = False
    if resource_name and spec_type in ['CM', 'EL', 'CS']:
        if resource_name.replace('U-', '') == spec_type:
            matches_specialization = True
    if building_type and spec_type == building_type:
        matches_specialization = True

    if matches_specialization:
        return max(base_efficiency + 0.15 + factory_bonus, 0.001)
    else:
        return max(base_efficiency + 0.075 + factory_bonus, 0.001)


async def get_faction_efficiency_map(faction_id: int) -> Dict[tuple, float]:
    base = await calculate_efficiency(faction_id)
    is_specialized, spec_type, _ = await detect_specialization(faction_id)
    factory_bonus = await get_active_factory_efficiency_bonus(faction_id)

    if not is_specialized:
        def _eff(building_type, resource_name):
            bonus = factory_bonus if building_type == 'factory' else 0.0
            return max(base + bonus, 0.001)
        return _eff

    general = base + 0.075
    matching = base + 0.15
    general_factory = base + 0.075 + factory_bonus
    matching_factory = base + 0.15 + factory_bonus

    def _eff(building_type, resource_name):
        is_factory = building_type == 'factory'
        if resource_name and spec_type in ('CM', 'EL', 'CS'):
            if resource_name.replace('U-', '') == spec_type:
                return matching_factory if is_factory else matching
        if building_type and spec_type == building_type:
            return matching_factory if is_factory else matching
        return general_factory if is_factory else general

    return _eff


async def get_efficiency_info(faction_id: int) -> Dict:
    building_count_unweighted = await get_faction_building_count_unweighted(faction_id)
    building_count_weighted = await get_faction_building_count_weighted(faction_id)
    building_cap = await calculate_building_cap(faction_id)
    base_efficiency = await calculate_efficiency(faction_id)
    is_specialized, spec_type, bonus = await detect_specialization(faction_id)
    breakdown = await get_building_breakdown(faction_id)
    total_hexes = await get_faction_total_hexes(faction_id)

    return {
        'building_count': building_count_unweighted,
        'building_count_weighted': building_count_weighted,
        'building_cap': building_cap,
        'total_hexes': total_hexes,
        'base_efficiency': base_efficiency,
        'is_specialized': is_specialized,
        'specialization_type': spec_type,
        'specialization_bonus': bonus,
        'breakdown': breakdown,
        'over_cap': building_count_unweighted > building_cap
    }
