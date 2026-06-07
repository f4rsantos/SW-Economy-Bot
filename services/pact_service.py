from typing import Optional, List
from database.db_manager import db
from services.income_executor import calculate_influence_usage
from services.income_queries import fetch_hex_count, fetch_current_influence
from services.income_calculator import calculate_influence_income


async def get_pact_type(pact_type: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, name, influence_cost FROM pact_types WHERE name = $1", pact_type)
    return dict(row) if row else None


async def get_pact_type_names() -> List[str]:
    rows = await db.fetch("SELECT name FROM pact_types ORDER BY name")
    return [r['name'] for r in rows]


async def get_pact(pact_id: int) -> Optional[dict]:
    row = await db.fetchrow("""
        SELECT p.id, p.name, pt.name as pact_type, p.leader_id, p.date_created,
               COALESCE(f.formal_name, f.name) as leader_name, f.color
        FROM pacts p
        JOIN pact_types pt ON p.pact_type_id = pt.id
        JOIN factions f ON p.leader_id = f.id
        WHERE p.id = $1
    """, pact_id)
    return dict(row) if row else None


async def get_pact_members(pact_id: int) -> list:
    rows = await db.fetch("""
        SELECT COALESCE(f.formal_name, f.name) as faction_name, pm.date_joined
        FROM pact_members pm JOIN factions f ON pm.faction_id = f.id
        WHERE pm.pact_id = $1 ORDER BY pm.date_joined
    """, pact_id)
    return [dict(r) for r in rows]


async def is_pact_member(pact_id: int, faction_id: int) -> bool:
    row = await db.fetchrow("SELECT faction_id FROM pact_members WHERE pact_id = $1 AND faction_id = $2", pact_id, faction_id)
    return row is not None


async def get_faction_pacts(faction_id: int) -> dict:
    led = await db.fetch("""
        SELECT p.id, p.name, pt.name as pact_type, COUNT(pm.faction_id) as member_count
        FROM pacts p JOIN pact_types pt ON p.pact_type_id = pt.id
        LEFT JOIN pact_members pm ON p.id = pm.pact_id
        WHERE p.leader_id = $1 GROUP BY p.id, p.name, pt.name ORDER BY p.name
    """, faction_id)
    member = await db.fetch("""
        SELECT p.id, p.name, pt.name as pact_type, COALESCE(f.formal_name, f.name) as leader_name
        FROM pact_members pm JOIN pacts p ON pm.pact_id = p.id
        JOIN pact_types pt ON p.pact_type_id = pt.id JOIN factions f ON p.leader_id = f.id
        WHERE pm.faction_id = $1 AND p.leader_id != $1 ORDER BY p.name
    """, faction_id)
    return {'led': [dict(r) for r in led], 'member': [dict(r) for r in member]}


async def get_all_pact_types() -> list:
    rows = await db.fetch("SELECT id, name, description, influence_cost FROM pact_types ORDER BY id")
    return [dict(r) for r in rows]


async def create_pact(pact_name: str, pact_type_id: int, faction_id: int) -> dict:
    hex_count = await fetch_hex_count(faction_id)
    current_influence = await fetch_current_influence(faction_id)
    influence_usage = await calculate_influence_usage(faction_id)
    income = calculate_influence_income(hex_count, influence_usage, current_influence)
    if income < 0:
        raise ValueError(f"Influence income is {income:,} per week. Cannot create new pacts with negative influence income.")
    pact_row = await db.fetchrow("INSERT INTO pacts (name, pact_type_id, leader_id) VALUES ($1, $2, $3) RETURNING id", pact_name, pact_type_id, faction_id)
    pact_id = pact_row['id']
    await db.execute("INSERT INTO pact_members (pact_id, faction_id) VALUES ($1, $2)", pact_id, faction_id)
    return {'pact_id': pact_id}


async def join_pact(pact_id: int, faction_id: int, pact_data: dict) -> dict:
    if await is_pact_member(pact_id, faction_id):
        raise ValueError("Faction is already a member of this pact.")
    hex_result = await db.fetchrow("SELECT COALESCE(SUM(territory), 0) as total_hexes FROM world_factions WHERE faction_id = $1", pact_data['leader_id'])
    total_hexes = hex_result['total_hexes'] or 0
    raw_generation = max(2500 - 0.25 * total_hexes, 50)
    pact_type_row = await db.fetchrow("SELECT influence_cost FROM pact_types WHERE name = $1", pact_data['pact_type'])
    pact_cost_per_member = pact_type_row['influence_cost'] if pact_type_row else 0
    current_pact_costs = await calculate_influence_usage(pact_data['leader_id'])
    new_net_income = raw_generation - (current_pact_costs + pact_cost_per_member)
    if new_net_income < 0:
        raise ValueError(f"Pact leader's influence income would become {int(new_net_income):,} per week. The pact leader cannot afford additional members.")
    await db.execute("INSERT INTO pact_members (pact_id, faction_id) VALUES ($1, $2)", pact_id, faction_id)
    count_result = await db.fetchrow("SELECT COUNT(*) as member_count FROM pact_members WHERE pact_id = $1", pact_id)
    return {'member_count': count_result['member_count']}


async def end_pact(pact_id: int, faction_id: int) -> dict:
    pact_data = await get_pact(pact_id)
    if not pact_data:
        raise ValueError("Pact not found.")
    if pact_data['leader_id'] != faction_id:
        raise ValueError("Only the pact leader can dissolve this pact.")
    await db.execute("DELETE FROM pact_members WHERE pact_id = $1", pact_id)
    await db.execute("DELETE FROM pacts WHERE id = $1", pact_id)
    return {'name': pact_data['name'], 'pact_type': pact_data['pact_type']}


async def leave_pact(pact_id: int, faction_id: int) -> dict:
    pact_data = await get_pact(pact_id)
    if not pact_data:
        raise ValueError("Pact not found.")
    if pact_data['leader_id'] == faction_id:
        raise ValueError("Pact leader cannot leave. Use end-pact to dissolve it instead.")
    if not await is_pact_member(pact_id, faction_id):
        raise ValueError("Faction is not a member of this pact.")
    await db.execute("DELETE FROM pact_members WHERE pact_id = $1 AND faction_id = $2", pact_id, faction_id)
    return {'name': pact_data['name'], 'pact_type': pact_data['pact_type'], 'leader_name': pact_data['leader_name']}


async def remove_pact_member(pact_id: int, leader_faction_id: int, target_faction_id: int) -> dict:
    pact_data = await get_pact(pact_id)
    if not pact_data:
        raise ValueError("Pact not found.")
    if pact_data['leader_id'] != leader_faction_id:
        raise ValueError("Only the pact leader can remove members.")
    if target_faction_id == leader_faction_id:
        raise ValueError("Leader cannot be removed. Use end-pact to dissolve the pact.")
    if not await is_pact_member(pact_id, target_faction_id):
        raise ValueError(f"Faction is not a member of pact {pact_id}.")
    await db.execute("DELETE FROM pact_members WHERE pact_id = $1 AND faction_id = $2", pact_id, target_faction_id)
    return {'name': pact_data['name'], 'pact_type': pact_data['pact_type']}
