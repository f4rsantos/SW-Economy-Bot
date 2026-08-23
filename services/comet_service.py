# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
from typing import Optional
from dtos.comet import Comet
from repositories import comet_repo


async def create_comet(name: str, message: str, discoverer: int) -> Comet:
    try:
        return await comet_repo.create_comet(name, message, discoverer)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_comets(limit: int = 50, offset: int = 0) -> list[Comet]:
    return await comet_repo.get_comets(limit, offset)


async def get_comet(comet_id: int) -> Optional[Comet]:
    return await comet_repo.get_comet(comet_id)
