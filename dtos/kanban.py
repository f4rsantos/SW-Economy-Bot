# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Board:
    id: int
    name: str
    position: Optional[int]
    color: Optional[int]
    task_count: Optional[int]

    @classmethod
    def from_row(cls, row) -> "Board":
        return cls(
            id=row["id"],
            name=row["name"],
            position=row["position"] if "position" in row else None,
            color=row["color"] if "color" in row else None,
            task_count=row["task_count"] if "task_count" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Board"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class Org:
    id: int
    name: str
    created_at: Optional[datetime]
    task_count: Optional[int]

    @classmethod
    def from_row(cls, row) -> "Org":
        return cls(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"] if "created_at" in row else None,
            task_count=row["task_count"] if "task_count" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Org"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class Subtask:
    id: int
    title: str
    done: bool

    @classmethod
    def from_row(cls, row) -> "Subtask":
        return cls(
            id=row["id"],
            title=row["title"],
            done=row["done"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["Subtask"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class Task:
    id: int
    title: str
    description: Optional[str]
    board_id: Optional[int]
    org_id: Optional[int]
    priority: str
    created_by: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    board_name: Optional[str]
    board_color: Optional[int]
    org_name: Optional[str]
    assignee_count: Optional[int]

    @classmethod
    def from_row(cls, row) -> "Task":
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"] if "description" in row else None,
            board_id=row["board_id"] if "board_id" in row else None,
            org_id=row["org_id"] if "org_id" in row else None,
            priority=row["priority"],
            created_by=row["created_by"] if "created_by" in row else None,
            created_at=row["created_at"] if "created_at" in row else None,
            updated_at=row["updated_at"] if "updated_at" in row else None,
            board_name=row["board_name"] if "board_name" in row else None,
            board_color=row["board_color"] if "board_color" in row else None,
            org_name=row["org_name"] if "org_name" in row else None,
            assignee_count=row["assignee_count"] if "assignee_count" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Task"]:
        return [cls.from_row(row) for row in rows]
