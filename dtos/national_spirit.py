# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class NationalSpirit:
    display_name: str
    effect_type: str
    modifier_value: float
    granted_at: Optional[datetime]
    expires_at: Optional[datetime]

    @classmethod
    def from_row(cls, row) -> "NationalSpirit":
        return cls(
            display_name=row["display_name"],
            effect_type=row["effect_type"],
            modifier_value=row["modifier_value"],
            granted_at=row["granted_at"],
            expires_at=row["expires_at"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["NationalSpirit"]:
        return [cls.from_row(row) for row in rows]
