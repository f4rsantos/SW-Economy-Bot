# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Vehicle:
    id: int
    faction_id: Optional[int]
    type: Optional[int]
    type_name: Optional[str]
    name: str
    designation: Optional[str]
    faction_vehicle_number: Optional[int]
    vehicle_data: Optional[list]

    @classmethod
    def from_row(cls, row) -> "Vehicle":
        return cls(
            id=row["id"],
            faction_id=row["faction_id"] if "faction_id" in row else None,
            type=row["type"] if "type" in row else None,
            type_name=row["type_name"] if "type_name" in row else None,
            name=row["name"],
            designation=row["designation"] if "designation" in row else None,
            faction_vehicle_number=row["faction_vehicle_number"] if "faction_vehicle_number" in row else None,
            vehicle_data=row["vehicle_data"] if "vehicle_data" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Vehicle"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class VehicleCostRow:
    name: str
    amount: int

    @classmethod
    def from_row(cls, row) -> "VehicleCostRow":
        return cls(name=row["name"], amount=row["amount"])

    @classmethod
    def from_rows(cls, rows) -> List["VehicleCostRow"]:
        return [cls.from_row(row) for row in rows]
