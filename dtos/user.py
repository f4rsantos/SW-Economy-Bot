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
    notify_mode: str
    notify_channel_id: Optional[int]
    notify_transfers: bool
    notify_movements: bool
    notify_origin: bool
    notify_destination: bool
    notify_own: bool
    notify_recruitment: bool
    notify_fleet_arrival: bool
    notify_battle: bool
    notify_income: bool
    allegiance: Optional[str]
    treatment: Optional[str]

    @classmethod
    def from_row(cls, row) -> "User":
        badge_ids = row["badge_ids"] if "badge_ids" in row else None
        ephemeral = row["ephemeral_commands"] if "ephemeral_commands" in row else False
        notify_mode = row["notify_mode"] if "notify_mode" in row else None
        notify_channel_id = row["notify_channel_id"] if "notify_channel_id" in row else None
        notify_transfers = row["notify_transfers"] if "notify_transfers" in row else True
        notify_movements = row["notify_movements"] if "notify_movements" in row else True
        notify_origin = row["notify_origin"] if "notify_origin" in row else True
        notify_destination = row["notify_destination"] if "notify_destination" in row else True
        notify_own = row["notify_own"] if "notify_own" in row else False
        notify_recruitment = row["notify_recruitment"] if "notify_recruitment" in row else True
        notify_fleet_arrival = row["notify_fleet_arrival"] if "notify_fleet_arrival" in row else True
        notify_battle = row["notify_battle"] if "notify_battle" in row else True
        notify_income = row["notify_income"] if "notify_income" in row else True
        allegiance = row["allegiance"] if "allegiance" in row else None
        treatment = row["treatment"] if "treatment" in row else None
        return cls(
            id=row["id"],
            access_level=row["access_level"],
            badge_ids=tuple(badge_ids) if badge_ids else (),
            ephemeral_commands=bool(ephemeral),
            notify_mode=notify_mode or "off",
            notify_channel_id=int(notify_channel_id) if notify_channel_id else None,
            notify_transfers=bool(notify_transfers),
            notify_movements=bool(notify_movements),
            notify_origin=bool(notify_origin),
            notify_destination=bool(notify_destination),
            notify_own=bool(notify_own),
            notify_recruitment=bool(notify_recruitment),
            notify_fleet_arrival=bool(notify_fleet_arrival),
            notify_battle=bool(notify_battle),
            notify_income=bool(notify_income),
            allegiance=allegiance,
            treatment=treatment,
        )

    @classmethod
    def from_rows(cls, rows) -> List["User"]:
        return [cls.from_row(row) for row in rows]
