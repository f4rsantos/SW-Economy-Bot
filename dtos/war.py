# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class War:
    id: int
    name: str
    date_start: datetime

    @classmethod
    def from_row(cls, row) -> "War":
        return cls(
            id=row["id"],
            name=row["name"],
            date_start=row["date_start"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["War"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class WarSideStat:
    side: str
    faction_names: list
    faction_count: Optional[int]

    @classmethod
    def from_row(cls, row) -> "WarSideStat":
        return cls(
            side=row["side"],
            faction_names=row["faction_names"],
            faction_count=row["faction_count"] if "faction_count" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["WarSideStat"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class WarSummary:
    id: int
    name: str
    date_start: datetime
    faction_count: int
    active_battles: int
    sides: list

    @classmethod
    def from_row(cls, row) -> "WarSummary":
        return cls(
            id=row["id"],
            name=row["name"],
            date_start=row["date_start"],
            faction_count=row["faction_count"],
            active_battles=row["active_battles"],
            sides=row["sides"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["WarSummary"]:
        return [cls.from_row(row) for row in rows]
