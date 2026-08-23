# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True, slots=True)
class Blockade:
    id: int
    world_id: int
    world_name: str

    @classmethod
    def from_row(cls, row) -> "Blockade":
        return cls(
            id=row["id"],
            world_id=row["world_id"],
            world_name=row["world_name"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["Blockade"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class BlockadeSummary:
    id: int
    world_name: str
    date_start: datetime
    targets: list
    fleet_count: int
    blockading_factions: list

    @classmethod
    def from_row(cls, row) -> "BlockadeSummary":
        return cls(
            id=row["id"],
            world_name=row["world_name"],
            date_start=row["date_start"],
            targets=row["targets"],
            fleet_count=row["fleet_count"],
            blockading_factions=row["blockading_factions"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["BlockadeSummary"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class InterceptionDetails:
    unit_name: str
    faction_name: str

    @classmethod
    def from_row(cls, row) -> "InterceptionDetails":
        return cls(
            unit_name=row["unit_name"],
            faction_name=row["faction_name"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["InterceptionDetails"]:
        return [cls.from_row(row) for row in rows]
