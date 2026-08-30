# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Port:
    id: int
    faction_id: int
    faction_name: Optional[str]
    world_id: int
    world_name: Optional[str]
    is_active: bool

    @classmethod
    def from_row(cls, row) -> "Port":
        return cls(
            id=row["id"],
            faction_id=row["faction_id"],
            faction_name=row["faction_name"] if "faction_name" in row else None,
            world_id=row["world_id"],
            world_name=row["world_name"] if "world_name" in row else None,
            is_active=row["is_active"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["Port"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class PortLane:
    id: int
    faction_id: int
    port_a_id: int
    port_b_id: int
    world_a_id: Optional[int]
    world_b_id: Optional[int]
    world_a_name: Optional[str]
    world_b_name: Optional[str]

    @classmethod
    def from_row(cls, row) -> "PortLane":
        return cls(
            id=row["id"],
            faction_id=row["faction_id"],
            port_a_id=row["port_a_id"],
            port_b_id=row["port_b_id"],
            world_a_id=row["world_a_id"] if "world_a_id" in row else None,
            world_b_id=row["world_b_id"] if "world_b_id" in row else None,
            world_a_name=row["world_a_name"] if "world_a_name" in row else None,
            world_b_name=row["world_b_name"] if "world_b_name" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["PortLane"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class PortAccessRule:
    id: int
    port_id: int
    faction_id: Optional[int]
    faction_name: Optional[str]
    traffic_type: str
    policy: str

    @classmethod
    def from_row(cls, row) -> "PortAccessRule":
        return cls(
            id=row["id"],
            port_id=row["port_id"],
            faction_id=row["faction_id"],
            faction_name=row["faction_name"] if "faction_name" in row else None,
            traffic_type=row["traffic_type"],
            policy=row["policy"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["PortAccessRule"]:
        return [cls.from_row(row) for row in rows]
