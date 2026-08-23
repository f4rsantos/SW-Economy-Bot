# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class CasinoPool:
    resource_id: int
    amount: int
    floor_amount: int
    resource: Optional[str]

    @classmethod
    def from_row(cls, row) -> "CasinoPool":
        return cls(
            resource_id=row["resource_id"],
            amount=row["amount"],
            floor_amount=row["floor_amount"],
            resource=row["resource"] if "resource" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["CasinoPool"]:
        return [cls.from_row(row) for row in rows]
