# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True, slots=True)
class User:
    id: int
    access_level: int
    badge_ids: Tuple[int, ...]
    ephemeral_commands: bool

    @classmethod
    def from_row(cls, row) -> "User":
        badge_ids = row["badge_ids"] if "badge_ids" in row else None
        ephemeral = row["ephemeral_commands"] if "ephemeral_commands" in row else False
        return cls(
            id=row["id"],
            access_level=row["access_level"],
            badge_ids=tuple(badge_ids) if badge_ids else (),
            ephemeral_commands=bool(ephemeral),
        )

    @classmethod
    def from_rows(cls, rows) -> List["User"]:
        return [cls.from_row(row) for row in rows]
