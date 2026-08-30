# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional
from database.db_manager import db
from dtos.kanban import Board, Org, Subtask, Task


async def search_board_names(current: str, limit: int) -> list[str]:
    rows = await db.fetch(
        "SELECT name FROM kanban_boards WHERE LOWER(name) LIKE $1 ORDER BY position LIMIT $2",
        current,
        limit,
    )
    return [r['name'] for r in rows]


async def search_org_names(current: str, limit: int) -> list[str]:
    rows = await db.fetch(
        "SELECT name FROM kanban_organizations WHERE LOWER(name) LIKE $1 ORDER BY name LIMIT $2",
        current,
        limit,
    )
    return [r['name'] for r in rows]


async def get_task(task_id: int) -> Optional[Task]:
    row = await db.fetchrow(
        """
        SELECT t.*, b.name as board_name, b.color as board_color,
               o.name as org_name
        FROM kanban_tasks t
        JOIN kanban_boards b ON t.board_id = b.id
        LEFT JOIN kanban_organizations o ON t.org_id = o.id
        WHERE t.id = $1
        """,
        task_id,
    )
    return Task.from_row(row) if row else None


async def get_board_by_name(name: str) -> Optional[Board]:
    row = await db.fetchrow("SELECT * FROM kanban_boards WHERE LOWER(name) = LOWER($1)", name)
    return Board.from_row(row) if row else None


async def get_org_by_name(name: str) -> Optional[Org]:
    row = await db.fetchrow("SELECT * FROM kanban_organizations WHERE LOWER(name) = LOWER($1)", name)
    return Org.from_row(row) if row else None


async def create_task(title: str, description: Optional[str], board_id: int, org_id: Optional[int], priority: str, created_by: int) -> int:
    row = await db.fetchrow(
        """
        INSERT INTO kanban_tasks (title, description, board_id, org_id, priority, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        title,
        description,
        board_id,
        org_id,
        priority,
        created_by,
    )
    return row['id']


async def find_task_assignee(task_id: int, user_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT 1 FROM kanban_task_assignees WHERE task_id = $1 AND user_id = $2",
        task_id,
        user_id,
    )
    return dict(row) if row else None


async def insert_task_assignee(task_id: int, user_id: int):
    await db.execute(
        "INSERT INTO kanban_task_assignees (task_id, user_id) VALUES ($1, $2)",
        task_id,
        user_id,
    )


async def upsert_task_assignee(task_id: int, user_id: int):
    await db.execute(
        "INSERT INTO kanban_task_assignees (task_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        task_id,
        user_id,
    )


async def remove_task_assignee(task_id: int, user_id: int) -> bool:
    result = await db.execute(
        "DELETE FROM kanban_task_assignees WHERE task_id = $1 AND user_id = $2",
        task_id,
        user_id,
    )
    return result != "DELETE 0"


async def touch_task(task_id: int):
    await db.execute("UPDATE kanban_tasks SET updated_at = NOW() WHERE id = $1", task_id)


async def list_board_tasks(where: str, params: list) -> List[Task]:
    rows = await db.fetch(
        f"""
        SELECT t.id, t.title, t.priority, o.name as org_name,
               COUNT(a.user_id) as assignee_count
        FROM kanban_tasks t
        LEFT JOIN kanban_organizations o ON t.org_id = o.id
        LEFT JOIN kanban_task_assignees a ON t.id = a.task_id
        WHERE {where}
        GROUP BY t.id, t.title, t.priority, o.name
        ORDER BY t.id DESC
        """,
        *params,
    )
    return Task.from_rows(rows)


async def move_task_to_board(task_id: int, board_id: int):
    await db.execute(
        "UPDATE kanban_tasks SET board_id = $1, updated_at = NOW() WHERE id = $2",
        board_id,
        task_id,
    )


async def update_task(task_id: int, title: str, description: Optional[str], priority: str, org_id: Optional[int]):
    await db.execute(
        """
        UPDATE kanban_tasks
        SET title = $1, description = $2, priority = $3, org_id = $4,
            updated_at = NOW()
        WHERE id = $5
        """,
        title,
        description,
        priority,
        org_id,
        task_id,
    )


async def list_boards() -> List[Board]:
    rows = await db.fetch("SELECT * FROM kanban_boards ORDER BY position")
    return Board.from_rows(rows)


async def list_all_board_ids() -> list[int]:
    rows = await db.fetch("SELECT id FROM kanban_boards")
    return [r['id'] for r in rows]


async def list_done_board_ids() -> list[int]:
    rows = await db.fetch("SELECT id FROM kanban_boards WHERE LOWER(name) = 'done'")
    return [r['id'] for r in rows]


async def count_tasks_for_scope_with_org(board_ids: list[int], org_id: int) -> int:
    return await db.fetchval(
        "SELECT COUNT(*) FROM kanban_tasks WHERE board_id = ANY($1) AND org_id = $2",
        board_ids,
        org_id,
    )


async def count_tasks_for_scope(board_ids: list[int]) -> int:
    return await db.fetchval("SELECT COUNT(*) FROM kanban_tasks WHERE board_id = ANY($1)", board_ids)


async def delete_tasks_for_scope(where: str, params: list) -> str:
    return await db.execute(f"DELETE FROM kanban_tasks t WHERE {where}", *params)


async def create_org(name: str) -> int:
    row = await db.fetchrow("INSERT INTO kanban_organizations (name) VALUES ($1) RETURNING id", name)
    return row['id']


async def org_exists(name: str) -> bool:
    row = await db.fetchrow("SELECT id FROM kanban_organizations WHERE LOWER(name) = LOWER($1)", name)
    return row is not None


async def unlink_org_tasks(org_id: int):
    await db.execute("UPDATE kanban_tasks SET org_id = NULL WHERE org_id = $1", org_id)


async def delete_org(org_id: int):
    await db.execute("DELETE FROM kanban_organizations WHERE id = $1", org_id)


async def list_orgs_with_task_count() -> List[Org]:
    rows = await db.fetch(
        """
        SELECT o.id, o.name,
               COUNT(t.id) as task_count
        FROM kanban_organizations o
        LEFT JOIN kanban_tasks t ON t.org_id = o.id
        GROUP BY o.id, o.name
        ORDER BY o.name
        """
    )
    return Org.from_rows(rows)


async def list_boards_with_task_count() -> List[Board]:
    rows = await db.fetch(
        """
        SELECT b.id, b.name, b.position,
               COUNT(t.id) as task_count
        FROM kanban_boards b
        LEFT JOIN kanban_tasks t ON t.board_id = b.id
        GROUP BY b.id, b.name, b.position
        ORDER BY b.position
        """
    )
    return Board.from_rows(rows)


async def board_task_counts_for_org(org_id: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT board_id, COUNT(*) as cnt FROM kanban_tasks WHERE org_id = $1 GROUP BY board_id",
        org_id,
    )
    return [dict(r) for r in rows]


async def board_task_counts() -> list[dict]:
    rows = await db.fetch("SELECT board_id, COUNT(*) as cnt FROM kanban_tasks GROUP BY board_id")
    return [dict(r) for r in rows]


async def board_task_preview_rows_for_org(org_id: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT t.id, t.title, t.priority, t.board_id FROM kanban_tasks t WHERE t.org_id = $1 ORDER BY t.id DESC",
        org_id,
    )
    return [dict(r) for r in rows]


async def board_task_preview_rows() -> list[dict]:
    rows = await db.fetch("SELECT t.id, t.title, t.priority, t.board_id FROM kanban_tasks t ORDER BY t.id DESC")
    return [dict(r) for r in rows]


async def next_subtask_position(task_id: int) -> int:
    return await db.fetchval("SELECT COALESCE(MAX(position), -1) + 1 FROM kanban_subtasks WHERE task_id = $1", task_id)


async def create_subtask(task_id: int, title: str, position: int) -> int:
    row = await db.fetchrow(
        "INSERT INTO kanban_subtasks (task_id, title, position) VALUES ($1, $2, $3) RETURNING id",
        task_id,
        title,
        position,
    )
    return row['id']


async def get_subtask(task_id: int, subtask_id: int) -> Optional[Subtask]:
    row = await db.fetchrow(
        "SELECT id, title, done FROM kanban_subtasks WHERE id = $1 AND task_id = $2",
        subtask_id,
        task_id,
    )
    return Subtask.from_row(row) if row else None


async def update_subtask_done(subtask_id: int, done: bool):
    await db.execute("UPDATE kanban_subtasks SET done = $1 WHERE id = $2", done, subtask_id)


async def list_task_assignees(task_id: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT user_id FROM kanban_task_assignees WHERE task_id = $1 ORDER BY assigned_at",
        task_id,
    )
    return [dict(r) for r in rows]


async def list_subtasks(task_id: int) -> List[Subtask]:
    rows = await db.fetch(
        "SELECT id, title, done FROM kanban_subtasks WHERE task_id = $1 ORDER BY position, id",
        task_id,
    )
    return Subtask.from_rows(rows)


async def delete_task(task_id: int):
    await db.execute("DELETE FROM kanban_tasks WHERE id = $1", task_id)


async def count_subtasks(task_id: int) -> int:
    return await db.fetchval("SELECT COUNT(*) FROM kanban_subtasks WHERE task_id = $1", task_id)
