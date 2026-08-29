# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Faction:
    id: int
    name: str
    display_name: str
    formal_name: Optional[str]
    color: str
    leader: Optional[str]
    flag: Optional[str]
    faction_type: int
    capital_world_id: Optional[int]
    leader_id: Optional[int]
    is_company: bool
    is_pirate: bool
    population_limit: Optional[int]

    @classmethod
    def from_row(cls, row) -> "Faction":
        formal_name = row["formal_name"]
        name = row["name"]
        faction_type = row["faction_type"]
        return cls(
            id=row["id"],
            name=name,
            display_name=formal_name or name,
            formal_name=formal_name,
            color=row["color"],
            leader=row["leader"],
            flag=row["flag"],
            faction_type=faction_type,
            capital_world_id=row["capital_world_id"],
            leader_id=row["leader_id"],
            is_company=faction_type == 1,
            is_pirate=faction_type == 2,
            population_limit=row["population_limit"] if "population_limit" in row.keys() else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Faction"]:
        return [cls.from_row(row) for row in rows]
