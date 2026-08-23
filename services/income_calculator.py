# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import math
from typing import Dict, Tuple

POPULATION_PER_CS = 50000
INFLUENCE_CAP = 10000
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


def calculate_influence_income(total_hexes: int, influence_cost: int, current_influence: int, total_cs_upkeep: int = 0) -> int:
    generation_rate = max(2500 - 0.25 * total_hexes, 50)
    net_generation = generation_rate - influence_cost
    upkeep_bonus = min(1.0, total_cs_upkeep / 1_000_000)
    gain = net_generation * (1 + upkeep_bonus) if net_generation > 0 else net_generation
    max_gain = max(0, INFLUENCE_CAP - current_influence)
    return round(min(gain, max_gain))


def calculate_population_growth(
    population: int,
    global_cs: int,
    global_population: int,
    local_cs_production: int,
    is_blockaded: bool,
) -> int:
    if population <= 0:
        return 0

    if is_blockaded:
        cs_available = local_cs_production * 5000
        pop_for_ratio = population
    else:
        cs_available = global_cs * 5000
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

    return math.floor(population * growth_percent * 2 / 100)


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
) -> Tuple[Dict, Dict, Dict, Dict]:
    unrefined_production = {}
    total_available = {}
    world_unrefined_data = unrefined_data_map.get(world_id, {})

    for res_name in ('U-CM', 'U-EL', 'U-CS'):
        data = world_unrefined_data.get(res_name)
        if data:
            pct_adjusted = math.floor(data['base_production'] * (data['percentage'] / 100))
            base_resource = res_name[2:]
            eff = efficiency_cache.get(('extractor', base_resource), 1.0)
            prod = math.floor(pct_adjusted * eff)
        else:
            prod = 0
        unrefined_production[res_name] = prod
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

        if res_name == 'CS':
            actual = min(potential, available_u)
        else:
            storage_cap = world_storage_caps.get(res_name, 0)
            current_stored = world_refined_stock.get(res_name, 0)
            outgoing = world_outgoing_trade.get(res_name, 0)
            available_storage = max(0, storage_cap - current_stored + outgoing)
            actual = min(potential, available_u, available_storage)

        refined[res_name] = actual
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
