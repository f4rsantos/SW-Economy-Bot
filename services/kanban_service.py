# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional
from repositories import kanban_repo
from dtos.kanban import Board, Org, Subtask, Task


async def search_board_names(current: str, limit: int = 25) -> list[str]:
    return await kanban_repo.search_board_names(f"%{current.lower()}%", limit)


async def search_org_names(current: str, limit: int = 25) -> list[str]:
    return await kanban_repo.search_org_names(f"%{current.lower()}%", limit)


async def get_task(task_id: int) -> Optional[Task]:
    return await kanban_repo.get_task(task_id)


async def get_board_by_name(name: str) -> Optional[Board]:
    return await kanban_repo.get_board_by_name(name)


async def get_org_by_name(name: str) -> Optional[Org]:
    return await kanban_repo.get_org_by_name(name)


async def create_task(title: str, description: Optional[str], board_id: int, org_id: Optional[int], priority: str, created_by: int) -> int:
    return await kanban_repo.create_task(title, description, board_id, org_id, priority, created_by)


async def add_task_assignee_if_missing(task_id: int, user_id: int) -> bool:
    existing = await kanban_repo.find_task_assignee(task_id, user_id)
    if existing:
        return False
    await kanban_repo.insert_task_assignee(task_id, user_id)
    return True


async def upsert_task_assignee(task_id: int, user_id: int):
    await kanban_repo.upsert_task_assignee(task_id, user_id)


async def remove_task_assignee(task_id: int, user_id: int) -> bool:
    return await kanban_repo.remove_task_assignee(task_id, user_id)


async def touch_task(task_id: int):
    await kanban_repo.touch_task(task_id)


async def list_board_tasks(board_id: int, org_id: Optional[int] = None, priority: Optional[str] = None) -> List[Task]:
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
    return await kanban_repo.list_board_tasks(where, params)


async def move_task_to_board(task_id: int, board_id: int):
    await kanban_repo.move_task_to_board(task_id, board_id)


async def update_task(task_id: int, title: str, description: Optional[str], priority: str, org_id: Optional[int]):
    await kanban_repo.update_task(task_id, title, description, priority, org_id)


async def list_boards() -> List[Board]:
    return await kanban_repo.list_boards()


async def list_board_ids(scope: str) -> list[int]:
    if scope == 'done':
        return await kanban_repo.list_done_board_ids()
    return await kanban_repo.list_all_board_ids()


async def count_tasks_for_scope(board_ids: list[int], org_id: Optional[int] = None) -> int:
    if org_id is not None:
        count = await kanban_repo.count_tasks_for_scope_with_org(board_ids, org_id)
    else:
        count = await kanban_repo.count_tasks_for_scope(board_ids)
    return int(count or 0)


async def delete_tasks_for_scope(board_ids: list[int], org_id: Optional[int] = None) -> int:
    conditions = ["t.board_id = ANY($1)"]
    params: list = [board_ids]
    idx = 2
    if org_id is not None:
        conditions.append(f"t.org_id = ${idx}")
        params.append(org_id)
    where = " AND ".join(conditions)
    result = await kanban_repo.delete_tasks_for_scope(where, params)
    return int(result.split()[-1]) if result else 0


async def create_org(name: str) -> int:
    return await kanban_repo.create_org(name)


async def org_exists(name: str) -> bool:
    return await kanban_repo.org_exists(name)


async def delete_org_and_unlink_tasks(org_id: int):
    await kanban_repo.unlink_org_tasks(org_id)
    await kanban_repo.delete_org(org_id)


async def list_orgs_with_task_count() -> List[Org]:
    return await kanban_repo.list_orgs_with_task_count()


async def list_boards_with_task_count() -> List[Board]:
    return await kanban_repo.list_boards_with_task_count()


async def board_task_counts(org_id: Optional[int] = None) -> dict[int, int]:
    if org_id is not None:
        rows = await kanban_repo.board_task_counts_for_org(org_id)
    else:
        rows = await kanban_repo.board_task_counts()
    return {r['board_id']: r['cnt'] for r in rows}


async def board_task_preview_rows(org_id: Optional[int] = None) -> list[dict]:
    if org_id is not None:
        return await kanban_repo.board_task_preview_rows_for_org(org_id)
    return await kanban_repo.board_task_preview_rows()


async def next_subtask_position(task_id: int) -> int:
    pos = await kanban_repo.next_subtask_position(task_id)
    return int(pos or 0)


async def create_subtask(task_id: int, title: str, position: int) -> int:
    return await kanban_repo.create_subtask(task_id, title, position)


async def get_subtask(task_id: int, subtask_id: int) -> Optional[Subtask]:
    return await kanban_repo.get_subtask(task_id, subtask_id)


async def update_subtask_done(subtask_id: int, done: bool):
    await kanban_repo.update_subtask_done(subtask_id, done)


async def list_task_assignees(task_id: int) -> list[dict]:
    return await kanban_repo.list_task_assignees(task_id)


async def list_subtasks(task_id: int) -> List[Subtask]:
    return await kanban_repo.list_subtasks(task_id)


async def delete_task(task_id: int):
    await kanban_repo.delete_task(task_id)


async def count_subtasks(task_id: int) -> int:
    count = await kanban_repo.count_subtasks(task_id)
    return int(count or 0)
