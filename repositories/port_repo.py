# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.db_manager import db
from dtos.ports import Port, PortLane, PortAccessRule

PORT_TYPE_CODE = 'interplanetary_port'


async def get_faction_ports(faction_id: int) -> list[Port]:
    rows = await db.fetch(
        """
        SELECT fm.id, fm.faction_id, f.name AS faction_name,
               fm.world_id, w.name AS world_name, fm.is_active
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        JOIN factions f ON f.id = fm.faction_id
        JOIN worlds w ON w.id = fm.world_id
        WHERE mt.code = $1 AND fm.faction_id = $2
        ORDER BY fm.built_at ASC
        """,
        PORT_TYPE_CODE, faction_id,
    )
    return Port.from_rows(rows)


async def get_port_by_world(faction_id: int, world_id: int) -> Optional[Port]:
    row = await db.fetchrow(
        """
        SELECT fm.id, fm.faction_id, f.name AS faction_name,
               fm.world_id, w.name AS world_name, fm.is_active
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        JOIN factions f ON f.id = fm.faction_id
        JOIN worlds w ON w.id = fm.world_id
        WHERE mt.code = $1 AND fm.faction_id = $2 AND fm.world_id = $3
        """,
        PORT_TYPE_CODE, faction_id, world_id,
    )
    return Port.from_row(row) if row else None


async def get_port_by_id(port_id: int) -> Optional[Port]:
    row = await db.fetchrow(
        """
        SELECT fm.id, fm.faction_id, f.name AS faction_name,
               fm.world_id, w.name AS world_name, fm.is_active
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        JOIN factions f ON f.id = fm.faction_id
        JOIN worlds w ON w.id = fm.world_id
        WHERE mt.code = $1 AND fm.id = $2
        """,
        PORT_TYPE_CODE, port_id,
    )
    return Port.from_row(row) if row else None


async def get_all_active_ports() -> list[Port]:
    rows = await db.fetch(
        """
        SELECT fm.id, fm.faction_id, f.name AS faction_name,
               fm.world_id, w.name AS world_name, fm.is_active
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        JOIN factions f ON f.id = fm.faction_id
        JOIN worlds w ON w.id = fm.world_id
        WHERE mt.code = $1 AND fm.is_active = true
        """,
        PORT_TYPE_CODE,
    )
    return Port.from_rows(rows)


async def insert_lane(conn, faction_id: int, port_a_id: int, port_b_id: int) -> int:
    executor = conn if conn is not None else db
    row = await executor.fetchrow(
        """
        INSERT INTO port_lanes (faction_id, port_a_id, port_b_id)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        faction_id, port_a_id, port_b_id,
    )
    return row["id"]


async def get_lane_between(port_a_id: int, port_b_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT id, faction_id, port_a_id, port_b_id
        FROM port_lanes
        WHERE (port_a_id = $1 AND port_b_id = $2) OR (port_a_id = $2 AND port_b_id = $1)
        """,
        port_a_id, port_b_id,
    )
    return dict(row) if row else None


async def get_faction_lanes(faction_id: int) -> list[PortLane]:
    rows = await db.fetch(
        """
        SELECT pl.id, pl.faction_id, pl.port_a_id, pl.port_b_id,
               pa.world_id AS world_a_id, pb.world_id AS world_b_id,
               wa.name AS world_a_name, wb.name AS world_b_name
        FROM port_lanes pl
        JOIN faction_megaprojects pa ON pa.id = pl.port_a_id
        JOIN faction_megaprojects pb ON pb.id = pl.port_b_id
        JOIN worlds wa ON wa.id = pa.world_id
        JOIN worlds wb ON wb.id = pb.world_id
        WHERE pl.faction_id = $1
        ORDER BY pl.built_at ASC
        """,
        faction_id,
    )
    return PortLane.from_rows(rows)


async def get_all_active_lanes() -> list[PortLane]:
    rows = await db.fetch(
        """
        SELECT pl.id, pl.faction_id, pl.port_a_id, pl.port_b_id,
               pa.world_id AS world_a_id, pb.world_id AS world_b_id,
               wa.name AS world_a_name, wb.name AS world_b_name
        FROM port_lanes pl
        JOIN faction_megaprojects pa ON pa.id = pl.port_a_id
        JOIN faction_megaprojects pb ON pb.id = pl.port_b_id
        JOIN worlds wa ON wa.id = pa.world_id
        JOIN worlds wb ON wb.id = pb.world_id
        WHERE pa.is_active = true AND pb.is_active = true
        """
    )
    return PortLane.from_rows(rows)


async def upsert_access_rule(port_id: int, faction_id: Optional[int], traffic_type: str, policy: str) -> int:
    row = await db.fetchrow(
        """
        INSERT INTO port_access_rules (port_id, faction_id, traffic_type, policy)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (port_id, traffic_type, COALESCE(faction_id, 0))
        DO UPDATE SET policy = EXCLUDED.policy
        RETURNING id
        """,
        port_id, faction_id, traffic_type, policy,
    )
    return row["id"]


async def delete_access_rule(port_id: int, faction_id: Optional[int], traffic_type: str) -> str:
    if faction_id is None:
        return await db.execute(
            "DELETE FROM port_access_rules WHERE port_id = $1 AND faction_id IS NULL AND traffic_type = $2",
            port_id, traffic_type,
        )
    return await db.execute(
        "DELETE FROM port_access_rules WHERE port_id = $1 AND faction_id = $2 AND traffic_type = $3",
        port_id, faction_id, traffic_type,
    )


async def get_rules_for_port(port_id: int) -> list[PortAccessRule]:
    rows = await db.fetch(
        """
        SELECT par.id, par.port_id, par.faction_id, f.name AS faction_name,
               par.traffic_type, par.policy
        FROM port_access_rules par
        LEFT JOIN factions f ON f.id = par.faction_id
        WHERE par.port_id = $1
        ORDER BY par.faction_id NULLS LAST, par.traffic_type
        """,
        port_id,
    )
    return PortAccessRule.from_rows(rows)


async def get_all_rules_for_ports(port_ids: list[int]) -> list[PortAccessRule]:
    if not port_ids:
        return []
    rows = await db.fetch(
        """
        SELECT par.id, par.port_id, par.faction_id, f.name AS faction_name,
               par.traffic_type, par.policy
        FROM port_access_rules par
        LEFT JOIN factions f ON f.id = par.faction_id
        WHERE par.port_id = ANY($1::int[])
        """,
        port_ids,
    )
    return PortAccessRule.from_rows(rows)
