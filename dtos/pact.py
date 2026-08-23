# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class PactType:
    id: int
    name: str
    influence_cost: Optional[int]
    description: Optional[str]

    @classmethod
    def from_row(cls, row) -> "PactType":
        return cls(
            id=row["id"],
            name=row["name"],
            influence_cost=row["influence_cost"],
            description=row["description"] if "description" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["PactType"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class Pact:
    id: int
    name: str
    pact_type: str
    leader_id: int
    date_created: Optional[datetime]
    leader_name: str
    color: str

    @classmethod
    def from_row(cls, row) -> "Pact":
        return cls(
            id=row["id"],
            name=row["name"],
            pact_type=row["pact_type"],
            leader_id=row["leader_id"],
            date_created=row["date_created"],
            leader_name=row["leader_name"],
            color=row["color"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["Pact"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class PactMember:
    faction_name: str
    date_joined: datetime

    @classmethod
    def from_row(cls, row) -> "PactMember":
        return cls(
            faction_name=row["faction_name"],
            date_joined=row["date_joined"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["PactMember"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class FactionPact:
    id: int
    name: str
    pact_type: str
    member_count: Optional[int]
    leader_name: Optional[str]

    @classmethod
    def from_row(cls, row) -> "FactionPact":
        return cls(
            id=row["id"],
            name=row["name"],
            pact_type=row["pact_type"],
            member_count=row["member_count"] if "member_count" in row else None,
            leader_name=row["leader_name"] if "leader_name" in row else None,
        )

    @classmethod
    def from_rows(cls, rows) -> List["FactionPact"]:
        return [cls.from_row(row) for row in rows]
