# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True, slots=True)
class BadgeCostRow:
    id: int
    name: str
    needs_world: bool
    resource_name: str
    amount: int

    @classmethod
    def from_row(cls, row) -> "BadgeCostRow":
        return cls(
            id=row["id"],
            name=row["name"],
            needs_world=row["needs_world"],
            resource_name=row["resource_name"],
            amount=row["amount"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["BadgeCostRow"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class BadgeProgressRow:
    resource_name: str
    current_amount: int

    @classmethod
    def from_row(cls, row) -> "BadgeProgressRow":
        return cls(
            resource_name=row["resource_name"],
            current_amount=row["current_amount"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["BadgeProgressRow"]:
        return [cls.from_row(row) for row in rows]
