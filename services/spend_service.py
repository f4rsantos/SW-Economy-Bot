# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import logging
from typing import Awaitable, Callable, Dict, List

from repositories import spend_repo
from dtos.spend import WeeklySpendTotal

logger = logging.getLogger(__name__)

SPEND = 1
REFUND = -1


async def record_spend(faction_id: int, resources: Dict[str, int], direction: int = SPEND) -> None:
    if not resources:
        return
    try:
        await spend_repo.record_spend(faction_id, resources, direction)
    except Exception:
        logger.exception(f"Failed to record weekly spend for faction {faction_id}")


async def reset_and_report(on_reset: Callable[[List[WeeklySpendTotal]], Awaitable[bool]]) -> List[WeeklySpendTotal]:
    return await spend_repo.reset_and_report(on_reset)


async def reset_snapshot_and_report(on_reset: Callable[[List[WeeklySpendTotal]], Awaitable[bool]]) -> List[WeeklySpendTotal]:
    return await spend_repo.reset_snapshot_and_report(on_reset)
