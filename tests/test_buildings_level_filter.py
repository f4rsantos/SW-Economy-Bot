# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from services.building_service import get_faction_building_ids_at_level, get_building_ids_supporting_level


@pytest.mark.asyncio
async def test_faction_building_ids_at_level(fake_db):
    fake_db.fetch_queue.append([{"building_id": 3}, {"building_id": 7}])
    ids = await get_faction_building_ids_at_level(faction_id=1, level=2)
    assert ids == {3, 7}


@pytest.mark.asyncio
async def test_faction_building_ids_at_level_empty(fake_db):
    fake_db.fetch_queue.append([])
    ids = await get_faction_building_ids_at_level(faction_id=1, level=9)
    assert ids == set()


@pytest.mark.asyncio
async def test_building_ids_supporting_level(fake_db):
    fake_db.fetch_queue.append([{"building_id": 1}, {"building_id": 2}])
    ids = await get_building_ids_supporting_level(level=3)
    assert ids == {1, 2}
