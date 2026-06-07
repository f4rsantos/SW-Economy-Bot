from typing import Optional
from database.db_manager import db


async def search_board_names(current: str, limit: int = 25) -> list[str]:
    rows = await db.fetch(
        "SELECT name FROM kanban_boards WHERE LOWER(name) LIKE $1 ORDER BY position LIMIT $2",
        f"%{current.lower()}%",
        limit,
    )
    return [r['name'] for r in rows]


async def search_org_names(current: str, limit: int = 25) -> list[str]:
    rows = await db.fetch(
        "SELECT name FROM kanban_organizations WHERE LOWER(name) LIKE $1 ORDER BY name LIMIT $2",
        f"%{current.lower()}%",
        limit,
    )
    return [r['name'] for r in rows]


async def get_task(task_id: int) -> Optional[dict]:
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
    return dict(row) if row else None


async def get_board_by_name(name: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT * FROM kanban_boards WHERE LOWER(name) = LOWER($1)", name)
    return dict(row) if row else None


async def get_org_by_name(name: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT * FROM kanban_organizations WHERE LOWER(name) = LOWER($1)", name)
    return dict(row) if row else None


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


async def add_task_assignee_if_missing(task_id: int, user_id: int) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM kanban_task_assignees WHERE task_id = $1 AND user_id = $2",
        task_id,
        user_id,
    )
    if row:
        return False
    await db.execute(
        "INSERT INTO kanban_task_assignees (task_id, user_id) VALUES ($1, $2)",
        task_id,
        user_id,
    )
    return True


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


async def list_board_tasks(board_id: int, org_id: Optional[int] = None, priority: Optional[str] = None) -> list[dict]:
    conditions = ["t.board_id = $1"]
    params = [board_id]
    idx = 2
    if org_id is not None:
        conditions.append(f"t.org_id = ${idx}")
        params.append(org_id)
        idx += 1
    if priority is not None:
        conditions.append(f"t.priority = ${idx}")
        params.append(priority)
    where = " AND ".join(conditions)
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
    return [dict(r) for r in rows]


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


async def list_boards() -> list[dict]:
    rows = await db.fetch("SELECT * FROM kanban_boards ORDER BY position")
    return [dict(r) for r in rows]


async def list_board_ids(scope: str) -> list[int]:
    if scope == 'done':
        rows = await db.fetch("SELECT id FROM kanban_boards WHERE LOWER(name) = 'done'")
    else:
        rows = await db.fetch("SELECT id FROM kanban_boards")
    return [r['id'] for r in rows]


async def count_tasks_for_scope(board_ids: list[int], org_id: Optional[int] = None) -> int:
    if org_id is not None:
        count = await db.fetchval(
            "SELECT COUNT(*) FROM kanban_tasks WHERE board_id = ANY($1) AND org_id = $2",
            board_ids,
            org_id,
        )
    else:
        count = await db.fetchval("SELECT COUNT(*) FROM kanban_tasks WHERE board_id = ANY($1)", board_ids)
    return int(count or 0)


async def delete_tasks_for_scope(board_ids: list[int], org_id: Optional[int] = None) -> int:
    conditions = ["t.board_id = ANY($1)"]
    params: list = [board_ids]
    idx = 2
    if org_id is not None:
        conditions.append(f"t.org_id = ${idx}")
        params.append(org_id)
    where = " AND ".join(conditions)
    result = await db.execute(f"DELETE FROM kanban_tasks t WHERE {where}", *params)
    return int(result.split()[-1]) if result else 0


async def create_org(name: str) -> int:
    row = await db.fetchrow("INSERT INTO kanban_organizations (name) VALUES ($1) RETURNING id", name)
    return row['id']


async def org_exists(name: str) -> bool:
    row = await db.fetchrow("SELECT id FROM kanban_organizations WHERE LOWER(name) = LOWER($1)", name)
    return row is not None


async def delete_org_and_unlink_tasks(org_id: int):
    await db.execute("UPDATE kanban_tasks SET org_id = NULL WHERE org_id = $1", org_id)
    await db.execute("DELETE FROM kanban_organizations WHERE id = $1", org_id)


async def list_orgs_with_task_count() -> list[dict]:
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
    return [dict(r) for r in rows]


async def list_boards_with_task_count() -> list[dict]:
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
    return [dict(r) for r in rows]


async def board_task_counts(org_id: Optional[int] = None) -> dict[int, int]:
    if org_id is not None:
        rows = await db.fetch(
            "SELECT board_id, COUNT(*) as cnt FROM kanban_tasks WHERE org_id = $1 GROUP BY board_id",
            org_id,
        )
    else:
        rows = await db.fetch("SELECT board_id, COUNT(*) as cnt FROM kanban_tasks GROUP BY board_id")
    return {r['board_id']: r['cnt'] for r in rows}


async def board_task_preview_rows(org_id: Optional[int] = None) -> list[dict]:
    if org_id is not None:
        rows = await db.fetch(
            "SELECT t.id, t.title, t.priority, t.board_id FROM kanban_tasks t WHERE t.org_id = $1 ORDER BY t.id DESC",
            org_id,
        )
    else:
        rows = await db.fetch("SELECT t.id, t.title, t.priority, t.board_id FROM kanban_tasks t ORDER BY t.id DESC")
    return [dict(r) for r in rows]


async def next_subtask_position(task_id: int) -> int:
    pos = await db.fetchval("SELECT COALESCE(MAX(position), -1) + 1 FROM kanban_subtasks WHERE task_id = $1", task_id)
    return int(pos or 0)


async def create_subtask(task_id: int, title: str, position: int) -> int:
    row = await db.fetchrow(
        "INSERT INTO kanban_subtasks (task_id, title, position) VALUES ($1, $2, $3) RETURNING id",
        task_id,
        title,
        position,
    )
    return row['id']


async def get_subtask(task_id: int, subtask_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT id, title, done FROM kanban_subtasks WHERE id = $1 AND task_id = $2",
        subtask_id,
        task_id,
    )
    return dict(row) if row else None


async def update_subtask_done(subtask_id: int, done: bool):
    await db.execute("UPDATE kanban_subtasks SET done = $1 WHERE id = $2", done, subtask_id)


async def list_task_assignees(task_id: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT user_id FROM kanban_task_assignees WHERE task_id = $1 ORDER BY assigned_at",
        task_id,
    )
    return [dict(r) for r in rows]


async def list_subtasks(task_id: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, title, done FROM kanban_subtasks WHERE task_id = $1 ORDER BY position, id",
        task_id,
    )
    return [dict(r) for r in rows]


async def delete_task(task_id: int):
    await db.execute("DELETE FROM kanban_tasks WHERE id = $1", task_id)


async def count_subtasks(task_id: int) -> int:
    count = await db.fetchval("SELECT COUNT(*) FROM kanban_subtasks WHERE task_id = $1", task_id)
    return int(count or 0)
