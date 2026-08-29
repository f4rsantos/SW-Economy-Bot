# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True, slots=True)
class WeeklySpendTotal:
    resource_name: str
    amount: int

    @classmethod
    def from_row(cls, row) -> "WeeklySpendTotal":
        return cls(
            resource_name=row["resource_name"],
            amount=row["amount"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["WeeklySpendTotal"]:
        return [cls.from_row(row) for row in rows]
