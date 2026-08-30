# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dtos.national_spirit import NationalSpirit
from repositories import national_spirit_repo


async def get_active_efficiency_bonus(faction_id: int) -> float:
    return await national_spirit_repo.get_active_efficiency_bonus(faction_id)


async def get_active_factory_efficiency_bonus(faction_id: int) -> float:
    return await national_spirit_repo.get_active_factory_efficiency_bonus(faction_id)


async def get_national_spirits(faction_id: int) -> list[NationalSpirit]:
    return await national_spirit_repo.get_national_spirits(faction_id)
