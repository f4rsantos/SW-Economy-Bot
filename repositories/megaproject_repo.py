# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.db_manager import db
from dtos.megaproject import MegaprojectType, FactionMegaproject, MegaprojectProgressRow


def get_connection():
    return db.get_connection()


async def get_world_hex_count(world_id: int) -> Optional[int]:
    row = await db.fetchrow("SELECT hex_count FROM worlds WHERE id = $1", world_id)
    return row["hex_count"] if row else None


async def get_type_by_code(code: str) -> Optional[MegaprojectType]:
    row = await db.fetchrow(
        """
        SELECT id, code, name, description, is_world_scoped, one_per_world, one_per_faction, has_maintenance
        FROM megaproject_types WHERE code = $1
        """,
        code,
    )
    return MegaprojectType.from_row(row) if row else None


async def get_all_types() -> list[MegaprojectType]:
    rows = await db.fetch(
        """
        SELECT id, code, name, description, is_world_scoped, one_per_world, one_per_faction, has_maintenance
        FROM megaproject_types ORDER BY id
        """
    )
    return MegaprojectType.from_rows(rows)


async def get_faction_project_by_type(faction_id: int, megaproject_type_id: int, world_id: Optional[int] = None) -> Optional[dict]:
    if world_id is not None:
        row = await db.fetchrow(
            """
            SELECT id, faction_id, megaproject_type_id, world_id, is_active, built_at, disabled_at, data
            FROM faction_megaprojects
            WHERE faction_id = $1 AND megaproject_type_id = $2 AND world_id = $3
            """,
            faction_id, megaproject_type_id, world_id,
        )
    else:
        row = await db.fetchrow(
            """
            SELECT id, faction_id, megaproject_type_id, world_id, is_active, built_at, disabled_at, data
            FROM faction_megaprojects
            WHERE faction_id = $1 AND megaproject_type_id = $2 AND world_id IS NULL
            """,
            faction_id, megaproject_type_id,
        )
    return dict(row) if row else None


async def insert_project(conn, faction_id: int, megaproject_type_id: int, world_id: Optional[int]) -> int:
    executor = conn if conn is not None else db
    row = await executor.fetchrow(
        """
        INSERT INTO faction_megaprojects (faction_id, megaproject_type_id, world_id, is_active)
        VALUES ($1, $2, $3, true)
        RETURNING id
        """,
        faction_id, megaproject_type_id, world_id,
    )
    return row["id"]


async def list_faction_projects(faction_id: int) -> list[FactionMegaproject]:
    rows = await db.fetch(
        """
        SELECT fm.id, fm.faction_id, fm.megaproject_type_id, mt.code AS type_code,
               mt.name AS type_name, fm.world_id, w.name AS world_name,
               fm.is_active, fm.built_at, fm.disabled_at
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        LEFT JOIN worlds w ON w.id = fm.world_id
        WHERE fm.faction_id = $1
        ORDER BY fm.built_at ASC
        """,
        faction_id,
    )
    return FactionMegaproject.from_rows(rows)


async def get_project_detail(faction_id: int, project_id: int) -> Optional[FactionMegaproject]:
    row = await db.fetchrow(
        """
        SELECT fm.id, fm.faction_id, fm.megaproject_type_id, mt.code AS type_code,
               mt.name AS type_name, fm.world_id, w.name AS world_name,
               fm.is_active, fm.built_at, fm.disabled_at
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        LEFT JOIN worlds w ON w.id = fm.world_id
        WHERE fm.faction_id = $1 AND fm.id = $2
        """,
        faction_id, project_id,
    )
    return FactionMegaproject.from_row(row) if row else None


async def get_faction_active_projects_by_type_code(faction_id: int, type_code: str) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT fm.id, fm.faction_id, fm.world_id
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        WHERE mt.code = $1 AND fm.faction_id = $2 AND fm.is_active = true
        """,
        type_code, faction_id,
    )
    return [dict(r) for r in rows]


async def get_active_projects_by_type_code(type_code: str) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT fm.id, fm.faction_id, fm.world_id
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        WHERE mt.code = $1 AND fm.is_active = true
        """,
        type_code,
    )
    return [dict(r) for r in rows]


async def set_active(project_id: int, is_active: bool) -> str:
    if is_active:
        return await db.execute(
            "UPDATE faction_megaprojects SET is_active = true, disabled_at = NULL WHERE id = $1 AND is_active = false",
            project_id,
        )
    return await db.execute(
        "UPDATE faction_megaprojects SET is_active = false, disabled_at = now() WHERE id = $1 AND is_active = true",
        project_id,
    )


async def get_faction_active_project_by_code(faction_id: int, type_code: str) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT fm.id, fm.faction_id, fm.world_id, fm.is_active
        FROM faction_megaprojects fm
        JOIN megaproject_types mt ON mt.id = fm.megaproject_type_id
        WHERE fm.faction_id = $1 AND mt.code = $2
        """,
        faction_id, type_code,
    )
    return dict(row) if row else None


async def snapshot_last_cycle_spend(conn) -> None:
    await conn.execute(
        """
        DELETE FROM faction_last_cycle_spend
        """
    )
    await conn.execute(
        """
        INSERT INTO faction_last_cycle_spend (faction_id, resource_id, direction, amount)
        SELECT faction_id, resource_id, direction, amount FROM faction_weekly_spend
        """
    )


async def get_megaproject_progress_rows(faction_id: int, megaproject_type_id: int, world_id: Optional[int]) -> list[MegaprojectProgressRow]:
    if world_id is not None:
        rows = await db.fetch(
            """
            SELECT r.name AS resource_name, mpr.current_amount
            FROM megaproject_progress_resources mpr
            JOIN resources r ON r.id = mpr.resource_id
            WHERE mpr.faction_id = $1 AND mpr.megaproject_type_id = $2 AND mpr.world_id = $3
            """,
            faction_id, megaproject_type_id, world_id,
        )
    else:
        rows = await db.fetch(
            """
            SELECT r.name AS resource_name, mpr.current_amount
            FROM megaproject_progress_resources mpr
            JOIN resources r ON r.id = mpr.resource_id
            WHERE mpr.faction_id = $1 AND mpr.megaproject_type_id = $2 AND mpr.world_id IS NULL
            """,
            faction_id, megaproject_type_id,
        )
    return MegaprojectProgressRow.from_rows(rows)


async def upsert_megaproject_progress_resource(
    conn,
    faction_id: int,
    megaproject_type_id: int,
    world_id: Optional[int],
    resource_name: str,
    amount: int,
) -> int:
    executor = conn if conn is not None else db
    if world_id is not None:
        row = await executor.fetchrow(
            """
            INSERT INTO megaproject_progress_resources (faction_id, megaproject_type_id, world_id, resource_id, current_amount, updated_at)
            VALUES ($1, $2, $3, (SELECT id FROM resources WHERE name = $4), $5, CURRENT_TIMESTAMP)
            ON CONFLICT (faction_id, megaproject_type_id, world_id, resource_id) WHERE world_id IS NOT NULL
            DO UPDATE SET current_amount = megaproject_progress_resources.current_amount + $5,
                          updated_at = CURRENT_TIMESTAMP
            RETURNING current_amount
            """,
            faction_id, megaproject_type_id, world_id, resource_name, amount,
        )
    else:
        row = await executor.fetchrow(
            """
            INSERT INTO megaproject_progress_resources (faction_id, megaproject_type_id, world_id, resource_id, current_amount, updated_at)
            VALUES ($1, $2, NULL, (SELECT id FROM resources WHERE name = $3), $4, CURRENT_TIMESTAMP)
            ON CONFLICT (faction_id, megaproject_type_id, resource_id) WHERE world_id IS NULL
            DO UPDATE SET current_amount = megaproject_progress_resources.current_amount + $4,
                          updated_at = CURRENT_TIMESTAMP
            RETURNING current_amount
            """,
            faction_id, megaproject_type_id, resource_name, amount,
        )
    return row["current_amount"]


async def delete_megaproject_progress(conn, faction_id: int, megaproject_type_id: int, world_id: Optional[int]) -> None:
    executor = conn if conn is not None else db
    if world_id is not None:
        await executor.execute(
            "DELETE FROM megaproject_progress_resources WHERE faction_id = $1 AND megaproject_type_id = $2 AND world_id = $3",
            faction_id, megaproject_type_id, world_id,
        )
    else:
        await executor.execute(
            "DELETE FROM megaproject_progress_resources WHERE faction_id = $1 AND megaproject_type_id = $2 AND world_id IS NULL",
            faction_id, megaproject_type_id,
        )


async def get_last_cycle_refined_spend(faction_id: int) -> dict:
    rows = await db.fetch(
        """
        SELECT r.name AS resource_name, SUM(fls.amount * fls.direction) AS net_amount
        FROM faction_last_cycle_spend fls
        JOIN resources r ON r.id = fls.resource_id
        WHERE fls.faction_id = $1 AND r.name IN ('CM', 'EL', 'CS')
        GROUP BY r.name
        """,
        faction_id,
    )
    return {r["resource_name"]: int(r["net_amount"] or 0) for r in rows}
