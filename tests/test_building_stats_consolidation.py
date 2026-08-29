# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from repositories.building_repo import get_faction_building_stats


def _grouped_row(resource_name, building_type, unweighted, actual, weighted):
    return {
        "resource_name": resource_name,
        "building_type": building_type,
        "unweighted": unweighted,
        "actual": actual,
        "weighted": weighted,
    }


@pytest.mark.asyncio
async def test_stats_totals_sum_every_group(fake_db):
    fake_db.fetch_queue.append([
        _grouped_row("CM", "extractor", 10, 5, 10),
        _grouped_row("EL", "refinery", 4, 2, 6),
        _grouped_row(None, "city", 3, 3, 3),
    ])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.total_unweighted == 17
    assert stats.total_actual == 10
    assert stats.total_weighted == 19


@pytest.mark.asyncio
async def test_rows_without_resource_are_excluded_from_resource_rollups(fake_db):
    fake_db.fetch_queue.append([
        _grouped_row(None, "city", 3, 3, 3),
        _grouped_row("CM", "extractor", 10, 5, 10),
    ])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.by_resource == {"CM": 10}
    assert stats.by_resource_weighted == {"CM": 10}
    assert stats.by_type == {"city": 3, "extractor": 10}
    assert stats.by_type_weighted == {"city": 3, "extractor": 10}


@pytest.mark.asyncio
async def test_upgraded_resource_variants_merge_into_base_resource(fake_db):
    fake_db.fetch_queue.append([
        _grouped_row("CM", "extractor", 10, 5, 10),
        _grouped_row("U-CM", "refinery", 4, 2, 6),
    ])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.by_resource == {"CM": 14}
    assert stats.by_resource_weighted == {"CM": 16}


@pytest.mark.asyncio
async def test_same_type_across_resources_accumulates(fake_db):
    fake_db.fetch_queue.append([
        _grouped_row("CM", "extractor", 10, 5, 10),
        _grouped_row("EL", "extractor", 6, 3, 6),
    ])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.by_type == {"extractor": 16}
    assert stats.by_type_weighted == {"extractor": 16}


@pytest.mark.asyncio
async def test_null_aggregates_are_treated_as_zero(fake_db):
    fake_db.fetch_queue.append([
        _grouped_row("CM", "extractor", None, None, None),
    ])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.total_unweighted == 0
    assert stats.total_actual == 0
    assert stats.total_weighted == 0
    assert stats.by_resource == {"CM": 0}


@pytest.mark.asyncio
async def test_faction_with_no_buildings(fake_db):
    fake_db.fetch_queue.append([])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.total_unweighted == 0
    assert stats.by_resource == {}
    assert stats.by_type == {}


@pytest.mark.asyncio
async def test_stats_issue_a_single_query(fake_db):
    fake_db.fetch_queue.append([_grouped_row("CM", "extractor", 10, 5, 10)])

    await get_faction_building_stats(faction_id=1)

    assert len(fake_db.executed) == 1


@pytest.mark.asyncio
async def test_fractional_city_weight_rounds_instead_of_truncating(fake_db):
    fake_db.fetch_queue.append([
        _grouped_row(None, "city", 9, 9, 0.9),
    ])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.total_weighted == 1
    assert stats.by_type_weighted == {"city": 1}


@pytest.mark.asyncio
async def test_fractional_city_weight_below_half_rounds_down(fake_db):
    fake_db.fetch_queue.append([
        _grouped_row(None, "city", 3, 3, 0.3),
    ])

    stats = await get_faction_building_stats(faction_id=1)

    assert stats.total_weighted == 0
    assert stats.by_type_weighted == {"city": 0}
