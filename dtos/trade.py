# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Trade:
    id: int
    amount: int
    resource_name: str
    sender_name: str
    sender_color: str
    receiver_name: str
    sender_faction_id: Optional[int] = None
    receiver_faction_id: Optional[int] = None
    sender_world: Optional[str] = None
    receiver_world: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Trade":
        keys = row.keys()
        return cls(
            id=row["id"],
            amount=row["amount"],
            resource_name=row["resource_name"],
            sender_name=row["sender_name"],
            sender_color=row["sender_color"],
            receiver_name=row["receiver_name"],
            sender_faction_id=row["sender_faction_id"] if "sender_faction_id" in keys else None,
            receiver_faction_id=row["receiver_faction_id"] if "receiver_faction_id" in keys else None,
            sender_world=row["sender_world"] if "sender_world" in keys else None,
            receiver_world=row["receiver_world"] if "receiver_world" in keys else None,
        )


@dataclass(frozen=True, slots=True)
class TradeSummary:
    id: int
    amount: int
    resource_name: str
    other_faction_name: str
    sender_world: Optional[str]
    receiver_world: Optional[str]

    @classmethod
    def from_row(cls, row, other_col: str) -> "TradeSummary":
        return cls(
            id=row["id"],
            amount=row["amount"],
            resource_name=row["resource_name"],
            other_faction_name=row[other_col],
            sender_world=row["sender_world"],
            receiver_world=row["receiver_world"],
        )

    @classmethod
    def from_rows(cls, rows, other_col: str) -> List["TradeSummary"]:
        return [cls.from_row(row, other_col) for row in rows]
