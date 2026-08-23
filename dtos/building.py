# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True, slots=True)
class Building:
    id: int
    name: str

    @classmethod
    def from_row(cls, row) -> "Building":
        return cls(id=row["id"], name=row["name"])

    @classmethod
    def from_rows(cls, rows) -> List["Building"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class CatalogBuilding:
    id: int
    name: str
    description: Optional[str]
    is_generator: Optional[bool]
    production: Optional[int]
    is_refinery: Optional[bool]
    percentage_affects: Optional[str]
    resource_name: Optional[str]
    storage: Optional[int]

    @classmethod
    def from_row(cls, row) -> "CatalogBuilding":
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            is_generator=row["is_generator"],
            production=row["production"],
            is_refinery=row["is_refinery"],
            percentage_affects=row["percentage_affects"],
            resource_name=row["resource_name"],
            storage=row["storage"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["CatalogBuilding"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class BuildingCostRow:
    building_id: int
    name: str
    amount: int

    @classmethod
    def from_row(cls, row) -> "BuildingCostRow":
        return cls(
            building_id=row["building_id"],
            name=row["name"],
            amount=row["amount"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["BuildingCostRow"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class FactionBuildingStats:
    total_unweighted: int
    total_weighted: int
    total_actual: int
    by_resource: Dict[str, int]
    by_resource_weighted: Dict[str, int]
    by_type: Dict[str, int]
    by_type_weighted: Dict[str, int]
