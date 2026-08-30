# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class AllegianceRequest:
    id: int
    user_id: int
    faction_id: int
    status: str
    requested_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[int]

    @classmethod
    def from_row(cls, row) -> "AllegianceRequest":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            faction_id=row["faction_id"],
            status=row["status"],
            requested_at=row["requested_at"],
            resolved_at=row["resolved_at"] if "resolved_at" in row else None,
            resolved_by=row["resolved_by"] if "resolved_by" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["AllegianceRequest"]:
        return [cls.from_row(row) for row in rows]
