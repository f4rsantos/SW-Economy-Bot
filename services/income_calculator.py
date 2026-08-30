# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import math
from typing import Dict, Tuple

POPULATION_PER_CS = 5000
POPULATION_SUPPORTED_PER_CS = 5000
INFLUENCE_CAP = 10000


def get_influence_cap() -> int:
    from database.static_cache import static_cache
    resource = static_cache.get_resource('Influence')
    if resource and resource.get('is_limited') and resource.get('hard_limit'):
        return int(resource['hard_limit'])
    return INFLUENCE_CAP
STORABLE_RESOURCES = {'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS'}


def calculate_influence_cost_from_pacts(pact_rows) -> int:
    return sum(r['influence_cost'] or 0 for r in pact_rows)


def calculate_fleet_cs_cost(row) -> int:
    idle_cost          = math.ceil((row['idle_cs'] or 0) / 8)
    defence_patrol_cost = math.ceil((row['defence_patrol_cs'] or 0) / 6)
    battle_cost        = math.ceil((row['battle_cs'] or 0) / 4)
    mothballed_cost    = math.ceil((row['mothballed_cs'] or 0) / 60)
    return idle_cost + defence_patrol_cost + battle_cost + mothballed_cost


def calculate_fleet_cs_cost_for_fleet(fleet) -> int:
    status = fleet['status_name'].lower()
    cs = fleet['total_cs']
    if status == 'idle':
        return math.ceil(cs / 8)
    if status in ('defence', 'patrol', 'travelling', 'ftl supply'):
        return math.ceil(cs / 6)
    if status in ('battle', 'in combat', 'blockading'):
        return math.ceil(cs / 4)
    if status == 'mothballed':
        return math.ceil(cs / 60)
    return 0


def plan_fleet_cs_damage(fleets, cs_deficit: int) -> Tuple[list, list]:
    updates_damage = []
    updates_debris = []
    for fleet in fleets:
        if cs_deficit <= 0:
            break
        fleet_cost = calculate_fleet_cs_cost_for_fleet(fleet)
        new_health = max(0, fleet['health'] - 30)
        if new_health == 0:
            updates_debris.append((0, fleet['id']))
        else:
            updates_damage.append((new_health, fleet['id']))
        cs_deficit -= fleet_cost
    return updates_damage, updates_debris


def population_cs_map(pop_rows) -> Dict[int, int]:
    return {r['world_id']: math.ceil((r['population'] or 0) / POPULATION_PER_CS) for r in pop_rows}


def build_unrefined_production_map(rows) -> Dict[int, Dict]:
    result = {}
    for row in rows:
        wid = row['world_id']
        if wid not in result:
            result[wid] = {}
        result[wid][row['resource_name']] = {
            'base_production': row['total_production'],
            'percentage': row['percentage'],
        }
    return result


def build_refined_capacity_map(rows) -> Dict[int, Dict]:
    result = {}
    for row in rows:
        wid = row['world_id']
        if wid not in result:
            result[wid] = {}
        result[wid][row['resource_name']] = row['total_capacity']
    return result


def build_stock_map(rows) -> Dict[int, Dict]:
    result = {}
    for row in rows:
        wid = row['world_id']
        if wid not in result:
            result[wid] = {}
        result[wid][row['name']] = row['amount']
    return result


def build_storage_capacity_map(rows, efficiency_cache: Dict) -> Dict[int, Dict]:
    result = {}
    for row in rows:
        wid = row['world_id']
        res = row['resource_name']
        if wid not in result:
            result[wid] = {}
        eff = efficiency_cache.get(('storage', res), 1.0)
        result[wid][res] = math.floor(row['total_storage'] * eff)
    return result


def calculate_er_income(treasury: int, working_population: int, is_company: bool) -> int:
    if treasury <= 1_000_000_000_000:
        percentage = 100
    elif treasury <= 15_000_000_000_000:
        percentage = -0.005714 * (treasury / 1_000_000_000 - 1000) + 100
    else:
        percentage = 22 - math.log10(treasury / 1_000_000_000 - 5699) / 2

    if working_population <= 250_000_000:
        base_income = 245 * working_population / 210 * 1000 - 41_666_666_666
    else:
        base_income = 1_000_000_000 * ((1.7 * math.log10(working_population + 1)) ** 2 + 46.18193)

    income = (percentage / 100) * base_income
    if is_company:
        return max(round(income), 0)
    return max(round(income), 5_000_000_000)


def calculate_level_10_building_influence_bonus(level_10_building_count: int) -> int:
    count = max(0, level_10_building_count)
    total = 0.0
    for n in range(1, count + 1):
        marginal = max(0.0, 10 - 0.5 * (n - 1))
        if marginal <= 0:
            break
        total += marginal
    return round(total)


def calculate_influence_income(
    total_hexes: int,
    influence_cost: int,
    current_influence: int,
    total_cs_upkeep: int = 0,
    level_10_building_count: int = 0,
    influence_cap: int = None,
) -> int:
    generation_rate = max(2500 - 0.25 * total_hexes, 50)
    net_generation = generation_rate - influence_cost
    upkeep_bonus = min(1.0, total_cs_upkeep / 1_000_000)
    gain = net_generation * (1 + upkeep_bonus) if net_generation > 0 else net_generation
    gain += calculate_level_10_building_influence_bonus(level_10_building_count)
    cap = influence_cap if influence_cap is not None else get_influence_cap()
    max_gain = max(0, cap - current_influence)
    return round(min(gain, max_gain))


def calculate_city_growth_bonus(city_levels, growth_percent: float) -> float:
    if growth_percent <= 0:
        return 0.0
    scale_factor = max(0.0, min(1.0, growth_percent / 5))
    effective_city_levels = sum(max(0, level) for level in city_levels) / 10
    if effective_city_levels <= 0:
        return 0.0
    total_city_bonus = 10 * (1 - 0.5 ** effective_city_levels)
    return total_city_bonus * scale_factor


def calculate_population_growth(
    population: int,
    global_cs: int,
    global_population: int,
    local_cs_production: int,
    is_blockaded: bool,
    city_levels=None,
) -> int:
    if population <= 0:
        return 0

    if is_blockaded:
        cs_available = local_cs_production * POPULATION_SUPPORTED_PER_CS
        pop_for_ratio = population
    else:
        cs_available = global_cs * POPULATION_SUPPORTED_PER_CS
        pop_for_ratio = global_population if global_population > 0 else population

    consumable_ratio = cs_available / pop_for_ratio if pop_for_ratio > 0 else 0

    if consumable_ratio <= 0.5:
        growth_percent = -5
    elif consumable_ratio <= 1:
        growth_percent = (consumable_ratio - 1) * 10
    elif consumable_ratio <= 2:
        growth_percent = (consumable_ratio - 1) * 5
    else:
        growth_percent = 5

    if city_levels:
        growth_percent += calculate_city_growth_bonus(city_levels, growth_percent)

    return math.floor(population * growth_percent * 2 / 100)


def apply_faction_population_limit(pop_growth_by_world: Dict[int, int], current_total_population: int, effective_limit: int) -> Dict[int, int]:
    if effective_limit < 0:
        return dict(pop_growth_by_world)

    headroom = max(0, effective_limit - current_total_population)

    growing_worlds = {wid: g for wid, g in pop_growth_by_world.items() if g > 0}
    total_requested_growth = sum(growing_worlds.values())

    if total_requested_growth <= headroom:
        return dict(pop_growth_by_world)

    result = dict(pop_growth_by_world)

    if headroom <= 0:
        for wid in growing_worlds:
            result[wid] = 0
        return result

    scale = headroom / total_requested_growth
    floored = {}
    remainders = []
    for wid in sorted(growing_worlds.keys()):
        exact = growing_worlds[wid] * scale
        base = math.floor(exact)
        floored[wid] = base
        remainders.append((exact - base, wid))

    allocated = sum(floored.values())
    leftover = headroom - allocated

    remainders.sort(key=lambda r: (-r[0], r[1]))
    for i in range(leftover):
        _, wid = remainders[i % len(remainders)]
        floored[wid] += 1

    for wid, capped in floored.items():
        result[wid] = capped

    return result


def build_efficiency_cache(base_efficiency: float, is_specialized: bool, spec_type: str, bonus: float, spirit_bonus: float = 0.0) -> Dict:
    cache = {}
    for building_type in ('extractor', 'refinery', 'storage'):
        for resource_name in ('CM', 'EL', 'CS'):
            eff = base_efficiency
            if is_specialized:
                matches = (spec_type in ('CM', 'EL', 'CS') and resource_name == spec_type) or spec_type == building_type
                eff = base_efficiency + (0.15 if matches else 0.075)
            eff = max(eff + spirit_bonus, 0.001)
            cache[(building_type, resource_name)] = eff
            if building_type == 'storage':
                cache[('storage', f'U-{resource_name}')] = eff
    return cache


def compute_world_production(
    world_id: int,
    unrefined_data_map: Dict,
    refined_capacity_map: Dict,
    stock_map: Dict,
    refined_stock_map: Dict,
    storage_capacity_map: Dict,
    outgoing_trade_map: Dict,
    efficiency_cache: Dict,
    self_refining: bool = False,
    self_refine_production_scale: float = 1.0,
) -> Tuple[Dict, Dict, Dict, Dict]:
    unrefined_production = {}
    self_refined_production = {}
    total_available = {}
    world_unrefined_data = unrefined_data_map.get(world_id, {})

    for res_name in ('U-CM', 'U-EL', 'U-CS'):
        data = world_unrefined_data.get(res_name)
        if data:
            base_production = data['base_production']
            if self_refining:
                base_production = math.floor(base_production * self_refine_production_scale)
            pct_adjusted = math.floor(base_production * (data['percentage'] / 100))
            base_resource = res_name[2:]
            eff = efficiency_cache.get(('extractor', base_resource), 1.0)
            prod = math.floor(pct_adjusted * eff)
        else:
            prod = 0

        if self_refining and prod > 0:
            self_refined = prod
            prod = 0
        else:
            self_refined = 0

        unrefined_production[res_name] = prod
        self_refined_production[res_name[2:]] = self_refined
        stock = stock_map.get(world_id, {}).get(res_name, 0)
        total_available[res_name] = prod + stock

    refined = {}
    unrefined_consumed = {}
    world_capacity_data = refined_capacity_map.get(world_id, {})
    world_storage_caps = storage_capacity_map.get(world_id, {})
    world_refined_stock = refined_stock_map.get(world_id, {})
    world_outgoing_trade = outgoing_trade_map.get(world_id, {})

    for res_name in ('CM', 'EL', 'CS'):
        capacity = world_capacity_data.get(res_name, 0)
        u_name = f'U-{res_name}'
        eff = efficiency_cache.get(('refinery', res_name), 1.0)
        potential = math.floor(capacity * eff)
        available_u = total_available.get(u_name, 0)
        self_refined = self_refined_production.get(res_name, 0)

        if res_name == 'CS':
            actual = min(potential, available_u)
        else:
            storage_cap = world_storage_caps.get(res_name, 0)
            current_stored = world_refined_stock.get(res_name, 0)
            outgoing = world_outgoing_trade.get(res_name, 0)
            available_storage = max(0, storage_cap - current_stored + outgoing)
            actual = min(potential, available_u, available_storage)
            if self_refined > 0:
                remaining_storage = max(0, available_storage - actual)
                self_refined = min(self_refined, remaining_storage)

        refined[res_name] = actual + self_refined
        unrefined_consumed[u_name] = actual

    unrefined_delta = {
        r: unrefined_production[r] - unrefined_consumed.get(r, 0)
        for r in ('U-CM', 'U-EL', 'U-CS')
    }

    world_resources = {**unrefined_delta, **refined}
    return world_resources, unrefined_production, refined, unrefined_consumed


def plan_cs_withdrawals(worlds_with_cs, total_needed: int) -> Dict[int, int]:
    withdrawals = {}
    remaining = total_needed
    for world in worlds_with_cs:
        if remaining <= 0:
            break
        available = world['cs_amount']
        withdraw = min(available, remaining)
        withdrawals[world['world_id']] = withdraw
        remaining -= withdraw
    return withdrawals
