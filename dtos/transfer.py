# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class Transfer:
    id: int
    from_faction_id: int
    to_faction_id: int
    from_world_id: int
    to_world_id: int
    status_id: int
    start_time: datetime
    arrival_time: datetime
    actual_arrival: Optional[datetime]
    intercepting_faction_id: Optional[int]
    intercepted_by_fleet_id: Optional[int]
    interception_time: Optional[datetime]
    interception_world_id: Optional[int]
    escort_fleet_id: Optional[int]
    status: str
    from_faction_name: str
    to_faction_name: str
    from_world_name: str
    to_world_name: str

    @classmethod
    def from_row(cls, row) -> "Transfer":
        return cls(
            id=row["id"],
            from_faction_id=row["from_faction_id"],
            to_faction_id=row["to_faction_id"],
            from_world_id=row["from_world_id"],
            to_world_id=row["to_world_id"],
            status_id=row["status_id"],
            start_time=row["start_time"],
            arrival_time=row["arrival_time"],
            actual_arrival=row["actual_arrival"],
            intercepting_faction_id=row["intercepting_faction_id"],
            intercepted_by_fleet_id=row["intercepted_by_fleet_id"],
            interception_time=row["interception_time"],
            interception_world_id=row["interception_world_id"],
            escort_fleet_id=row["escort_fleet_id"],
            status=row["status"],
            from_faction_name=row["from_faction_name"],
            to_faction_name=row["to_faction_name"],
            from_world_name=row["from_world_name"],
            to_world_name=row["to_world_name"],
        )


@dataclass(frozen=True, slots=True)
class TransferResource:
    resource_id: int
    amount: int
    name: str

    @classmethod
    def from_row(cls, row) -> "TransferResource":
        return cls(
            resource_id=row["resource_id"],
            amount=row["amount"],
            name=row["name"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["TransferResource"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class TransferResourceBulk:
    transfer_id: int
    amount: int
    name: str

    @classmethod
    def from_row(cls, row) -> "TransferResourceBulk":
        return cls(
            transfer_id=row["transfer_id"],
            amount=row["amount"],
            name=row["name"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["TransferResourceBulk"]:
        return [cls.from_row(row) for row in rows]


@dataclass(frozen=True, slots=True)
class PendingTransfer:
    id: int
    status: str
    arrival_time: datetime
    from_faction_name: str
    to_faction_name: str
    from_world_name: str
    to_world_name: str
    interception_world_name: Optional[str]
    intercepting_faction_name: Optional[str]
    intercepting_unit_name: Optional[str]
    escort_name: Optional[str]

    @classmethod
    def from_row(cls, row) -> "PendingTransfer":
        return cls(
            id=row["id"],
            status=row["status"],
            arrival_time=row["arrival_time"],
            from_faction_name=row["from_faction_name"],
            to_faction_name=row["to_faction_name"],
            from_world_name=row["from_world_name"],
            to_world_name=row["to_world_name"],
            interception_world_name=row["interception_world_name"],
            intercepting_faction_name=row["intercepting_faction_name"],
            intercepting_unit_name=row["intercepting_unit_name"],
            escort_name=row["escort_name"],
        )

    @classmethod
    def from_rows(cls, rows) -> List["PendingTransfer"]:
        return [cls.from_row(row) for row in rows]
