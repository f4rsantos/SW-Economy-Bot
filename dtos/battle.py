# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Battle:
    id: int
    war_id: Optional[int]
    world_id: int
    world_name: str
    date_start: datetime

    @classmethod
    def from_row(cls, row) -> "Battle":
        return cls(
            id=row["id"],
            war_id=row["war_id"],
            world_id=row["world_id"],
            world_name=row["world_name"],
            date_start=row["date_start"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["Battle"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class BattleSideStat:
    side: str
    fleet_count: int
    total_cs: float
    avg_health: Optional[float]

    @classmethod
    def from_row(cls, row) -> "BattleSideStat":
        return cls(
            side=row["side"],
            fleet_count=row["fleet_count"],
            total_cs=row["total_cs"],
            avg_health=row["avg_health"] if "avg_health" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["BattleSideStat"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class BattleSummary:
    id: int
    war_id: Optional[int]
    world_name: str
    date_start: datetime
    fleet_count: int
    sides: list

    @classmethod
    def from_row(cls, row) -> "BattleSummary":
        return cls(
            id=row["id"],
            war_id=row["war_id"],
            world_name=row["world_name"],
            date_start=row["date_start"],
            fleet_count=row["fleet_count"],
            sides=row["sides"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["BattleSummary"]:
        return [cls.from_row(row) for row in rows]
