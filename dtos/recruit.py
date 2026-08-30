# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Recruitment:
    id: int
    faction_id: int
    amount: int
    role_name: str
    fleet_id: Optional[int]
    start_time: Optional[datetime]
    completion_time: Optional[datetime]
    status: Optional[str]
    unit_name: Optional[str]
    unit_number: Optional[int]
    faction_name: Optional[str]

    @classmethod
    def from_row(cls, row) -> "Recruitment":
        return cls(
            id=row["id"],
            faction_id=row["faction_id"],
            amount=row["amount"],
            role_name=row["role_name"],
            fleet_id=row["fleet_id"] if "fleet_id" in row else None,
            start_time=row["start_time"] if "start_time" in row else None,
            completion_time=row["completion_time"] if "completion_time" in row else None,
            status=row["status"] if "status" in row else None,
            unit_name=row["unit_name"] if "unit_name" in row else None,
            unit_number=row["unit_number"] if "unit_number" in row else None,
            faction_name=row["faction_name"] if "faction_name" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Recruitment"]:
        return [cls.from_row(row) for row in rows]
