# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True, slots=True)
class FactionLandEntry:
    name: str
    territory: int

    @classmethod
    def from_row(cls, row) -> "FactionLandEntry":
        return cls(
            name=row["name"],
            territory=row["territory"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["FactionLandEntry"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class WorldFactionPresence:
    display_name: str
    territory: int
    color: str

    @classmethod
    def from_row(cls, row) -> "WorldFactionPresence":
        return cls(
            display_name=row["display_name"],
            territory=row["territory"],
            color=row["color"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["WorldFactionPresence"]:
        return [cls.from_row(row) for row in rows]
