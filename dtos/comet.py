# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Comet:
    id: Optional[int]
    name: str
    message: str
    discoverer: int
    created_at: Optional[datetime]

    @classmethod
    def from_row(cls, row) -> "Comet":
        return cls(
            id=row["id"] if "id" in row else None,
            name=row["name"],
            message=row["message"],
            discoverer=row["discoverer"],
            created_at=row["created_at"] if "created_at" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["Comet"]:
        return [cls.from_row(row) for row in rows]
