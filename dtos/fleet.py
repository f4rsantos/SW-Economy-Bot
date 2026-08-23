# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Fleet:
    id: int
    name: Optional[str]
    faction_id: Optional[int]
    faction_fleet_number: Optional[int]
    health: Optional[int]
    total_cs: Optional[int]
    status_id: Optional[int]
    status_name: Optional[str]
    position: Optional[int]
    position_name: Optional[str]
    moving_to_name: Optional[str]
    moving_since: Optional[object]
    infantry_count: Optional[int]
    type_name: Optional[str]

    @classmethod
    def from_row(cls, row) -> "Fleet":
        return cls(
            id=row["id"],
            name=row["name"] if "name" in row else None,
            faction_id=row["faction_id"] if "faction_id" in row else None,
            faction_fleet_number=row["faction_fleet_number"] if "faction_fleet_number" in row else None,
            health=row["health"] if "health" in row else None,
            total_cs=row["total_cs"] if "total_cs" in row else None,
            status_id=row["status_id"] if "status_id" in row else None,
            status_name=row["status_name"] if "status_name" in row else None,
            position=row["position"] if "position" in row else None,
            position_name=row["position_name"] if "position_name" in row else None,
            moving_to_name=row["moving_to_name"] if "moving_to_name" in row else None,
            moving_since=row["moving_since"] if "moving_since" in row else None,
            infantry_count=row["infantry_count"] if "infantry_count" in row else None,
            type_name=row["type_name"] if "type_name" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Fleet"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class FleetListing:
    id: int
    name: Optional[str]
    faction_fleet_number: int
    status: str
    position: str
    position_id: int
    moving_to_name: Optional[str]
    moving_since: Optional[object]
    health: int
    total_cs: int
    faction_id: int
    type_name: Optional[str]
    faction_name: str
    faction_color: str

    @classmethod
    def from_row(cls, row) -> "FleetListing":
        return cls(
            id=row["id"],
            name=row["name"],
            faction_fleet_number=row["faction_fleet_number"],
            status=row["status"],
            position=row["position"],
            position_id=row["position_id"],
            moving_to_name=row["moving_to_name"],
            moving_since=row["moving_since"],
            health=row["health"],
            total_cs=row["total_cs"],
            faction_id=row["faction_id"],
            type_name=row["type_name"],
            faction_name=row["faction_name"],
            faction_color=row["faction_color"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["FleetListing"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class FleetDamageInfo:
    id: int
    name: Optional[str]
    faction_id: int
    faction_name: str
    faction_color: str
    health: int
    total_cs: int
    status_name: str

    @classmethod
    def from_row(cls, row) -> "FleetDamageInfo":
        return cls(
            id=row["id"],
            name=row["name"],
            faction_id=row["faction_id"],
            faction_name=row["faction_name"],
            faction_color=row["faction_color"],
            health=row["health"],
            total_cs=row["total_cs"],
            status_name=row["status_name"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["FleetDamageInfo"]:
        return [cls.from_row(row) for row in rows]
