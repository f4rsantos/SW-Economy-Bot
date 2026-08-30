# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class MegaprojectType:
    id: int
    code: str
    name: str
    description: Optional[str]
    is_world_scoped: bool
    one_per_world: bool
    one_per_faction: bool
    has_maintenance: bool

    @classmethod
    def from_row(cls, row) -> "MegaprojectType":
        return cls(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            description=row["description"] if "description" in row else None,
            is_world_scoped=row["is_world_scoped"],
            one_per_world=row["one_per_world"],
            one_per_faction=row["one_per_faction"],
            has_maintenance=row["has_maintenance"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["MegaprojectType"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class FactionMegaproject:
    id: int
    faction_id: int
    megaproject_type_id: int
    type_code: str
    type_name: str
    world_id: Optional[int]
    world_name: Optional[str]
    is_active: bool
    built_at: object
    disabled_at: object

    @classmethod
    def from_row(cls, row) -> "FactionMegaproject":
        return cls(
            id=row["id"],
            faction_id=row["faction_id"],
            megaproject_type_id=row["megaproject_type_id"],
            type_code=row["type_code"],
            type_name=row["type_name"],
            world_id=row["world_id"],
            world_name=row["world_name"] if "world_name" in row else None,
            is_active=row["is_active"],
            built_at=row["built_at"],
            disabled_at=row["disabled_at"] if "disabled_at" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["FactionMegaproject"]:
        return [cls.from_row(row) for row in rows]
