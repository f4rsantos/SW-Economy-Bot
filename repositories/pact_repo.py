# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional, List
from database.db_manager import db
from dtos.pact import PactType, Pact, PactMember, FactionPact


async def get_pact_type(pact_type: str) -> Optional[PactType]:
    row = await db.fetchrow("SELECT id, name, influence_cost FROM pact_types WHERE name = $1", pact_type)
    return PactType.from_row(row) if row else None


async def get_pact_type_names() -> List[str]:
    rows = await db.fetch("SELECT name FROM pact_types ORDER BY name")
    return [r['name'] for r in rows]


async def get_pact(pact_id: int) -> Optional[Pact]:
    row = await db.fetchrow("""
        SELECT p.id, p.name, pt.name as pact_type, p.leader_id, p.date_created,
               COALESCE(f.formal_name, f.name) as leader_name, f.color
        FROM pacts p
        JOIN pact_types pt ON p.pact_type_id = pt.id
        JOIN factions f ON p.leader_id = f.id
        WHERE p.id = $1
    """, pact_id)
    return Pact.from_row(row) if row else None


async def get_pact_members(pact_id: int) -> List[PactMember]:
    rows = await db.fetch("""
        SELECT COALESCE(f.formal_name, f.name) as faction_name, pm.date_joined
        FROM pact_members pm JOIN factions f ON pm.faction_id = f.id
        WHERE pm.pact_id = $1 ORDER BY pm.date_joined
    """, pact_id)
    return PactMember.from_rows(rows)


async def is_pact_member(pact_id: int, faction_id: int) -> bool:
    row = await db.fetchrow("SELECT faction_id FROM pact_members WHERE pact_id = $1 AND faction_id = $2", pact_id, faction_id)
    return row is not None


async def get_faction_pacts_led(faction_id: int) -> List[FactionPact]:
    rows = await db.fetch("""
        SELECT p.id, p.name, pt.name as pact_type, COUNT(pm.faction_id) as member_count
        FROM pacts p JOIN pact_types pt ON p.pact_type_id = pt.id
        LEFT JOIN pact_members pm ON p.id = pm.pact_id
        WHERE p.leader_id = $1 GROUP BY p.id, p.name, pt.name ORDER BY p.name
    """, faction_id)
    return FactionPact.from_rows(rows)


async def get_faction_pacts_member(faction_id: int) -> List[FactionPact]:
    rows = await db.fetch("""
        SELECT p.id, p.name, pt.name as pact_type, COALESCE(f.formal_name, f.name) as leader_name
        FROM pact_members pm JOIN pacts p ON pm.pact_id = p.id
        JOIN pact_types pt ON p.pact_type_id = pt.id JOIN factions f ON p.leader_id = f.id
        WHERE pm.faction_id = $1 AND p.leader_id != $1 ORDER BY p.name
    """, faction_id)
    return FactionPact.from_rows(rows)


async def get_all_pact_types() -> List[PactType]:
    rows = await db.fetch("SELECT id, name, description, influence_cost FROM pact_types ORDER BY id")
    return PactType.from_rows(rows)


async def insert_pact(pact_name: str, pact_type_id: int, faction_id: int) -> int:
    pact_row = await db.fetchrow("INSERT INTO pacts (name, pact_type_id, leader_id) VALUES ($1, $2, $3) RETURNING id", pact_name, pact_type_id, faction_id)
    return pact_row['id']


async def insert_pact_member(pact_id: int, faction_id: int) -> None:
    await db.execute("INSERT INTO pact_members (pact_id, faction_id) VALUES ($1, $2)", pact_id, faction_id)


async def get_faction_total_hexes(faction_id: int) -> int:
    hex_result = await db.fetchrow("SELECT COALESCE(SUM(territory), 0) as total_hexes FROM world_factions WHERE faction_id = $1", faction_id)
    return hex_result['total_hexes'] or 0


async def get_pact_member_count(pact_id: int) -> int:
    count_result = await db.fetchrow("SELECT COUNT(*) as member_count FROM pact_members WHERE pact_id = $1", pact_id)
    return count_result['member_count']


async def delete_pact_members(pact_id: int) -> None:
    await db.execute("DELETE FROM pact_members WHERE pact_id = $1", pact_id)


async def delete_pact(pact_id: int) -> None:
    await db.execute("DELETE FROM pacts WHERE id = $1", pact_id)


async def delete_pact_member(pact_id: int, faction_id: int) -> None:
    await db.execute("DELETE FROM pact_members WHERE pact_id = $1 AND faction_id = $2", pact_id, faction_id)


async def get_pact_type_influence_cost(pact_type: str) -> Optional[dict]:
    return await db.fetchrow("SELECT influence_cost FROM pact_types WHERE name = $1", pact_type)
