import json
from typing import Optional
from database.db_manager import db
from services.building_efficiency_service import (
    get_faction_building_count_unweighted,
    get_faction_building_count_actual,
    calculate_building_cap,
    get_faction_total_hexes,
)


MEGA_FACTORY_BUILDING_ID = 18
MEGA_FACTORY_SCALE_RATE = 0.075


def _calculate_mega_factory_cost(base_costs: dict, current_count: int, amount: int, level: int) -> dict:
    upgrade_factor = 1.0
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        cost = 0
        for i in range(amount):
            scale = (1 + MEGA_FACTORY_SCALE_RATE) ** (current_count + i)
            cost += base * scale + base * sum_n(level - 1) * upgrade_factor
        total[resource] = int(cost)
    return total


def _calculate_building_cost(base_costs: dict, current_actual: int, amount: int, level: int, building_id: int) -> dict:
    scarcity_rate = 0.02
    upgrade_factor = 1.0
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        cost = 0
        for i in range(amount):
            idx = current_actual + i
            cost += base * (1 + scarcity_rate * idx) + base * sum_n(level - 1) * upgrade_factor
        total[resource] = int(cost)
    return total


def _calculate_refund(base_costs: dict, current_actual: int, amount: int, level: int, week: bool, building_id: int) -> dict:
    refund_rate = 1.0 if week else 0.3
    scarcity_rate = 0.02
    upgrade_factor = 1.0
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        refund = 0
        for i in range(amount):
            idx = current_actual - 1 - i
            refund += (base * (1 + scarcity_rate * idx) + base * sum_n(level - 1) * upgrade_factor) * refund_rate
        total[resource] = int(refund)
    return total


def _calculate_mega_factory_refund(base_costs: dict, current_count: int, amount: int, level: int, week: bool) -> dict:
    refund_rate = 1.0 if week else 0.3
    upgrade_factor = 1.0
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        refund = 0
        for i in range(amount):
            scale = (1 + MEGA_FACTORY_SCALE_RATE) ** (current_count - 1 - i)
            refund += (base * scale + base * sum_n(level - 1) * upgrade_factor) * refund_rate
        total[resource] = int(refund)
    return total


async def get_building(building_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, name FROM buildings WHERE id = $1", building_id)
    return dict(row) if row else None


async def get_building_by_name(building_name: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, name FROM buildings WHERE LOWER(name) = LOWER($1)", building_name)
    return dict(row) if row else None


async def get_buildings_catalog() -> list:
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
    return [dict(r) for r in rows]


async def get_all_building_cost_rows() -> list:
    rows = await db.fetch("""
        SELECT bc.building_id, r.name, bc.amount FROM building_costs bc
        JOIN resources r ON bc.resource_id = r.id ORDER BY bc.building_id, r.name
    """)
    return [dict(r) for r in rows]


async def get_faction_mega_factory_count(faction_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COALESCE(SUM(amount), 0) as total FROM faction_world_buildings WHERE faction_id = $1 AND building_id = $2",
        faction_id, MEGA_FACTORY_BUILDING_ID
    )
    return int(row['total'])


async def get_building_base_costs(building_id: int) -> dict:
    rows = await db.fetch("""
        SELECT r.name, bc.amount FROM building_costs bc
        JOIN resources r ON bc.resource_id = r.id
        WHERE bc.building_id = $1
    """, building_id)
    return {r['name']: r['amount'] for r in rows}


async def get_company_er(faction_id: int) -> int:
    row = await db.fetchrow("""
        SELECT COALESCE(SUM(ft.amount), 0) as total FROM faction_treasury ft
        JOIN resources r ON ft.resource_id = r.id
        WHERE ft.faction_id = $1 AND r.name = 'ER'
    """, faction_id)
    return row['total'] or 0


def _company_building_cap(er: int) -> int:
    if er >= 10_000_000_000_000:
        return 600
    elif er >= 5_000_000_000_000:
        return 500
    elif er >= 1_000_000_000_000:
        return 300
    elif er >= 500_000_000_000:
        return 200
    return 100


async def buy_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int, is_company: bool) -> dict:
    building = await get_building(building_id)
    if not building:
        raise ValueError("Building not found.")
    if is_company and building['name'].lower() == 'city':
        raise ValueError("Companies cannot build cities.")
    if is_company:
        await db.execute(
            "INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, 0) ON CONFLICT DO NOTHING",
            world_id, faction_id
        )
    else:
        if not await db.fetchrow("SELECT 1 FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id):
            raise ValueError("Faction has no presence on this world.")
    base_costs = await get_building_base_costs(building_id)
    current_weighted = await get_faction_building_count_unweighted(faction_id)
    if is_company:
        er = await get_company_er(faction_id)
        building_cap = _company_building_cap(er)
    else:
        building_cap = await calculate_building_cap(faction_id)
    new_total = current_weighted + (amount * level)
    if new_total > building_cap:
        raise ValueError(f"Building cap exceeded. Cap: {building_cap:,}, Current: {current_weighted:,}, Adding: {amount * level:,}")
    if building_id == MEGA_FACTORY_BUILDING_ID:
        current_mega = await get_faction_mega_factory_count(faction_id)
        total_costs = _calculate_mega_factory_cost(base_costs, current_mega, amount, level)
    else:
        current_actual = await get_faction_building_count_actual(faction_id)
        scaling_count = max(0, current_actual - 27)
        total_costs = _calculate_building_cost(base_costs, scaling_count, amount, level, building_id)
    try:
        await db.execute(
            "SELECT sp_buy_building($1, $2, $3, $4, $5, $6::jsonb)",
            faction_id, world_id, building_id, amount, level, json.dumps(total_costs)
        )
    except Exception as e:
        raise ValueError(str(e)) from e
    return {'building_name': building['name'], 'costs': total_costs}


async def destroy_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int) -> dict:
    building = await get_building(building_id)
    if not building:
        raise ValueError("Building not found.")
    try:
        await db.execute(
            "SELECT sp_destroy_building($1, $2, $3, $4, $5)",
            faction_id, world_id, building_id, amount, level
        )
    except Exception as e:
        raise ValueError(str(e)) from e
    return {'building_name': building['name']}


async def refund_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int, week: bool) -> dict:
    building = await get_building(building_id)
    if not building:
        raise ValueError("Building not found.")
    base_costs = await get_building_base_costs(building_id)
    if building_id == MEGA_FACTORY_BUILDING_ID:
        current_mega = await get_faction_mega_factory_count(faction_id)
        refunds = _calculate_mega_factory_refund(base_costs, current_mega, amount, level, week)
    else:
        current_actual = await get_faction_building_count_actual(faction_id)
        refunds = _calculate_refund(base_costs, current_actual, amount, level, week, building_id)
    try:
        await db.execute(
            "SELECT sp_refund_building($1, $2, $3, $4, $5, $6::jsonb)",
            faction_id, world_id, building_id, amount, level, json.dumps(refunds)
        )
    except Exception as e:
        raise ValueError(str(e)) from e
    return {'building_name': building['name'], 'refunds': refunds}


async def get_building_cap_info(faction_id: int, is_company: bool) -> dict:
    building_count = await get_faction_building_count_unweighted(faction_id)
    total_hexes = await get_faction_total_hexes(faction_id)
    if is_company:
        er = await get_company_er(faction_id)
        building_cap = _company_building_cap(er)
        return {'building_count': building_count, 'building_cap': building_cap, 'total_hexes': total_hexes, 'er': er, 'is_company': True}
    building_cap = await calculate_building_cap(faction_id)
    return {'building_count': building_count, 'building_cap': building_cap, 'total_hexes': total_hexes, 'is_company': False}


async def list_faction_buildings(
    faction_id: int,
    world_id: Optional[int] = None,
    building_id: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT b.id, b.name, fwb.amount, fwb.level, w.name as world_name
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
