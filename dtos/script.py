# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Script:
    id: int
    name: Optional[str]
    script_text: str
    trigger_day: Optional[str]
    trigger_type: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_run_at: Optional[datetime]
    run_count: Optional[int]
    is_active: Optional[bool]
    created_by: Optional[int]
    faction_id: Optional[int]
    is_company: Optional[bool]

    @classmethod
    def from_row(cls, row) -> "Script":
        return cls(
            id=row["id"],
            name=row["name"] if "name" in row else None,
            script_text=row["script_text"],
            trigger_day=row["trigger_day"] if "trigger_day" in row else None,
            trigger_type=row["trigger_type"] if "trigger_type" in row else None,
            created_at=row["created_at"] if "created_at" in row else None,
            updated_at=row["updated_at"] if "updated_at" in row else None,
            last_run_at=row["last_run_at"] if "last_run_at" in row else None,
            run_count=row["run_count"] if "run_count" in row else None,
            is_active=row["is_active"] if "is_active" in row else None,
            created_by=row["created_by"] if "created_by" in row else None,
            faction_id=row["faction_id"] if "faction_id" in row else None,
            is_company=row["is_company"] if "is_company" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Script"]:
        return [cls.from_row(row) for row in rows]
