# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from repositories import building_repo
from services.national_spirit_service import get_active_factory_efficiency_bonus
from typing import Dict, Optional, Tuple
import math

SPECIALIZATION_MATCHING_BONUS = 0.15
SPECIALIZATION_OTHER_BONUS = 0.075
EFFICIENCY_DECIMALS = 3


def round_efficiency(value: float) -> float:
    return max(round(value, EFFICIENCY_DECIMALS), 0.001)


def format_efficiency_pct(value: float, decimals: int = 1) -> str:
    pct = round(value * 100, decimals)
    return f"{pct:g}"


def ceil_efficiency_pct(value: float, decimals: int = 1) -> str:
    multiplier = 10 ** decimals
    pct = math.ceil(round(value * 100, 6) * multiplier) / multiplier
    return f"{pct:g}"


async def get_faction_building_count_unweighted(faction_id: int) -> int:
    return await building_repo.get_faction_building_count_unweighted(faction_id)


async def get_faction_building_count_actual(faction_id: int) -> int:
    return await building_repo.get_faction_building_count_actual(faction_id)


async def get_faction_building_count_split(faction_id: int) -> Tuple[int, int]:
    return await building_repo.get_faction_building_count_split(faction_id)


async def get_faction_building_count_weighted(faction_id: int) -> int:
    return await building_repo.get_faction_building_count_weighted(faction_id)


async def get_faction_total_population(faction_id: int) -> int:
    return await building_repo.get_faction_total_population(faction_id)


async def get_faction_total_hexes(faction_id: int) -> int:
    return await building_repo.get_faction_total_hexes(faction_id)


async def calculate_building_cap(faction_id: int) -> int:
    total_hexes = await get_faction_total_hexes(faction_id)
    if total_hexes == 0:
        return 0
    cap = 172 * math.pow(total_hexes, 0.2)
    return int(cap)


async def get_faction_infantry_penalty(faction_id: int) -> float:
    infantry = await building_repo.get_faction_infantry_count(faction_id)
    population = await get_faction_total_population(faction_id)

    denominator = population + infantry
    if denominator == 0:
        return 0.0
    return infantry / denominator


async def get_infantry_allocation_by_world(faction_id: int) -> Dict[int, int]:
    total_infantry = await building_repo.get_faction_infantry_count(faction_id)
    pop_rows = await building_repo.get_faction_population_by_world(faction_id)

    allocation: Dict[int, int] = {r['world_id']: 0 for r in pop_rows}
    if total_infantry == 0 or not pop_rows:
        return allocation

    total_population = sum(r['population'] for r in pop_rows)
    if total_population == 0:
        return allocation

    remainders = []
    assigned = 0
    for r in pop_rows:
        wid = r['world_id']
        share_float = (r['population'] / total_population) * total_infantry
        share = int(share_float)
        allocation[wid] = share
        assigned += share
        remainders.append((share_float - share, wid))

    leftover = total_infantry - assigned
    if leftover > 0:
        remainders.sort(key=lambda x: (x[0], x[1]), reverse=True)
        largest_wid = max(pop_rows, key=lambda r: r['population'])['world_id']
        for i in range(leftover):
            if i < len(remainders):
                allocation[remainders[i][1]] += 1
            else:
                allocation[largest_wid] += 1

    return allocation


async def calculate_building_efficiency(faction_id: int) -> float:
    factory_count, other_count = await get_faction_building_count_split(faction_id)
    building_count = factory_count + other_count

    if building_count <= 500:
        base = 1.0
    else:
        other_free = min(other_count, 500)
        other_over = other_count - other_free
        factory_over = max(factory_count - (500 - other_free), 0)

        decline = other_over * 0.001 + factory_over * 0.0005
        linear_value = 1.0 - decline
        if linear_value >= 0.10:
            base = linear_value
        else:
            total_over = other_over + factory_over
            avg_rate = decline / total_over if total_over else 0.001
            over = (decline - 0.90) / avg_rate if avg_rate else 0
            base = max(0.05 + 0.05 * math.exp(-avg_rate * over), 0.001)

    return round_efficiency(base)


async def calculate_efficiency(faction_id: int) -> float:
    base = await calculate_building_efficiency(faction_id)
    infantry_penalty = await get_faction_infantry_penalty(faction_id)
    return round_efficiency(base - infantry_penalty)


def _breakdown_from_stats(stats) -> Dict:
    return {
        'total': stats.total_unweighted,
        'by_resource': stats.by_resource,
        'by_type': stats.by_type,
        'by_resource_weighted': stats.by_resource_weighted,
        'by_type_weighted': stats.by_type_weighted
    }


async def get_building_breakdown(faction_id: int, stats=None) -> Dict:
    if stats is None:
        stats = await building_repo.get_faction_building_stats(faction_id)
    return _breakdown_from_stats(stats)


def _specialization_from_stats(stats) -> Tuple[bool, str, float]:
    if stats.total_weighted == 0:
        return False, '', 0.0

    threshold = stats.total_weighted * 0.5

    for resource, count in stats.by_resource_weighted.items():
        if count >= threshold:
            return True, resource, SPECIALIZATION_OTHER_BONUS

    for building_type, count in stats.by_type_weighted.items():
        if building_type != 'other' and count >= threshold:
            return True, building_type, SPECIALIZATION_OTHER_BONUS

    return False, '', 0.0


async def detect_specialization(faction_id: int, stats=None) -> Tuple[bool, str, float]:
    if stats is None:
        stats = await building_repo.get_faction_building_stats(faction_id)
    return _specialization_from_stats(stats)


async def calculate_effective_efficiency(faction_id: int, building_type: str = None, resource_name: str = None, stats=None) -> float:
    base_efficiency = await calculate_efficiency(faction_id)
    is_specialized, spec_type, bonus = await detect_specialization(faction_id, stats=stats)
    factory_bonus = await get_active_factory_efficiency_bonus(faction_id) if building_type == 'factory' else 0.0

    if not is_specialized:
        return round_efficiency(base_efficiency + factory_bonus)

    matches_specialization = False
    if resource_name and spec_type in ['CM', 'EL', 'CS']:
        if resource_name.replace('U-', '') == spec_type:
            matches_specialization = True
    if building_type and spec_type == building_type:
        matches_specialization = True

    if matches_specialization:
        return round_efficiency(base_efficiency + SPECIALIZATION_MATCHING_BONUS + factory_bonus)
    else:
        return round_efficiency(base_efficiency + SPECIALIZATION_OTHER_BONUS + factory_bonus)


async def get_faction_efficiency_map(faction_id: int, stats=None) -> Dict[tuple, float]:
    base = await calculate_efficiency(faction_id)
    is_specialized, spec_type, _ = await detect_specialization(faction_id, stats=stats)
    factory_bonus = await get_active_factory_efficiency_bonus(faction_id)

    if not is_specialized:
        def _eff(building_type, resource_name):
            bonus = factory_bonus if building_type == 'factory' else 0.0
            return round_efficiency(base + bonus)
        return _eff

    general = round_efficiency(base + SPECIALIZATION_OTHER_BONUS)
    matching = round_efficiency(base + SPECIALIZATION_MATCHING_BONUS)
    general_factory = round_efficiency(base + SPECIALIZATION_OTHER_BONUS + factory_bonus)
    matching_factory = round_efficiency(base + SPECIALIZATION_MATCHING_BONUS + factory_bonus)

    def _eff(building_type, resource_name):
        is_factory = building_type == 'factory'
        if resource_name and spec_type in ('CM', 'EL', 'CS'):
            if resource_name.replace('U-', '') == spec_type:
                return matching_factory if is_factory else matching
        if building_type and spec_type == building_type:
            return matching_factory if is_factory else matching
        return general_factory if is_factory else general

    return _eff


async def get_efficiency_info(faction_id: int) -> Dict:
    stats = await building_repo.get_faction_building_stats(faction_id)
    building_count_unweighted = stats.total_unweighted
    building_count_weighted = stats.total_weighted
    building_cap = await calculate_building_cap(faction_id)
    building_efficiency = await calculate_building_efficiency(faction_id)
    infantry_penalty = await get_faction_infantry_penalty(faction_id)
    base_efficiency = round_efficiency(building_efficiency - infantry_penalty)
    is_specialized, spec_type, bonus = _specialization_from_stats(stats)
    breakdown = _breakdown_from_stats(stats)
    total_hexes = await get_faction_total_hexes(faction_id)

    return {
        'building_count': building_count_unweighted,
        'building_count_weighted': building_count_weighted,
        'building_cap': building_cap,
        'total_hexes': total_hexes,
        'building_efficiency': building_efficiency,
        'infantry_penalty': infantry_penalty,
        'base_efficiency': base_efficiency,
        'is_specialized': is_specialized,
        'specialization_type': spec_type,
        'specialization_bonus': bonus,
        'specialization_matching_bonus': SPECIALIZATION_MATCHING_BONUS if is_specialized else 0.0,
        'breakdown': breakdown,
        'over_cap': building_count_unweighted > building_cap
    }
