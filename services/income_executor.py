import json
import math
import asyncio
from datetime import datetime, timezone
from typing import Dict, List

import logging

from database.db_manager import db
from services.building_efficiency_service import calculate_efficiency, detect_specialization

logger = logging.getLogger(__name__)
from services.travel_time_service import calculate_travel_time
from services.income_queries import (
    fetch_pact_types_for_faction,
    fetch_fleet_cs_by_status,
    fetch_status_ids,
    fetch_non_debris_fleets,
    fetch_blockaded_world_ids,
    fetch_all_trade_deals,
    fetch_all_world_names,
    fetch_best_destination_world,
    fetch_unrefined_production_data,
    fetch_refined_capacity_data,
    fetch_local_stock,
    fetch_refined_stock,
    fetch_storage_capacities,
    fetch_er_treasury,
    fetch_total_population,
    fetch_total_army,
    fetch_faction_flags,
    fetch_hex_count,
    fetch_current_influence,
    fetch_worlds_with_cs,
    fetch_stored_cs,
    fetch_world_data_for_income,
    fetch_resource_map,
    fetch_all_population_by_world,
)
from services.income_calculator import (
    POPULATION_PER_CS,
    STORABLE_RESOURCES,
    calculate_influence_cost_from_pacts,
    calculate_fleet_cs_cost,
    plan_fleet_cs_damage,
    population_cs_map,
    build_unrefined_production_map,
    build_refined_capacity_map,
    build_stock_map,
    build_storage_capacity_map,
    calculate_er_income,
    calculate_influence_income,
    calculate_population_growth,
    build_efficiency_cache,
    compute_world_production,
    plan_cs_withdrawals,
)


async def _get_status_ids(shared_cache: dict) -> dict:
    if 'status_ids' in shared_cache:
        return shared_cache['status_ids']
    return await fetch_status_ids()


async def calculate_influence_usage(faction_id: int) -> int:
    pacts = await fetch_pact_types_for_faction(faction_id)
    return calculate_influence_cost_from_pacts(pacts)


async def calculate_fleet_cs_usage(faction_id: int, cached_status_ids: dict = None) -> int:
    status_ids = cached_status_ids or await fetch_status_ids()
    row = await fetch_fleet_cs_by_status(faction_id, status_ids)
    return calculate_fleet_cs_cost(row)


async def process_fleet_cs_damage(faction_id: int, cs_deficit: int):
    if cs_deficit <= 0:
        return
    debris_row = await db.fetchrow("SELECT id FROM fleet_status WHERE LOWER(name) = 'debris'")
    if not debris_row:
        logger.warning("debris status not found in database")
        return
    debris_id = debris_row['id']
    fleets = await fetch_non_debris_fleets(faction_id, debris_id)
    if not fleets:
        return
    updates_damage, updates_debris = plan_fleet_cs_damage(fleets, cs_deficit)
    if updates_damage:
        await db.executemany("UPDATE fleets SET health = $1 WHERE id = $2", updates_damage)
    if updates_debris:
        await db.executemany("UPDATE fleets SET health = 0, status_id = $1 WHERE id = $2",
                             [(debris_id, fleet_id) for _, fleet_id in updates_debris])


async def _process_trade_deals(
    faction_id: int,
    world_resources: Dict,
    stock_map: Dict,
    blockaded_world_ids: set,
) -> tuple:
    trades = await fetch_all_trade_deals(faction_id)
    world_names = await fetch_all_world_names()
    current_time = datetime.now(timezone.utc)
    destination_cache = {}
    pending_transfers = []

    for trade in trades:
        resource_name = trade['resource_name']
        resource_id = trade['resource_id']
        amount = trade['amount']
        receiver_id = trade['receiver_faction_id']
        sender_world_fixed = trade['sender_world_id']
        receiver_world_fixed = trade['receiver_world_id']

        if receiver_world_fixed:
            dest_world_id = receiver_world_fixed
        else:
            if receiver_id not in destination_cache:
                destination_cache[receiver_id] = await fetch_best_destination_world(receiver_id)
            dest_world_id = destination_cache[receiver_id]

        if not dest_world_id:
            logger.warning(f"  [Trade #{trade['id']}] No destination world for receiver {receiver_id} — skipped")
            continue

        worlds_with_resource = []
        if sender_world_fixed:
            if sender_world_fixed in blockaded_world_ids:
                logger.warning(f"  [Trade #{trade['id']}] Source world {sender_world_fixed} blockaded — skipped")
                continue
            if sender_world_fixed in world_resources:
                flow = world_resources[sender_world_fixed].get(resource_name, 0)
                stock = stock_map.get(sender_world_fixed, {}).get(resource_name, 0)
                available = max(0, flow + stock)
                if available > 0:
                    worlds_with_resource.append((sender_world_fixed, available))
        else:
            for wid, res_dict in world_resources.items():
                if wid in blockaded_world_ids:
                    continue
                flow = res_dict.get(resource_name, 0)
                stock = stock_map.get(wid, {}).get(resource_name, 0)
                available = max(0, flow + stock)
                if available > 0:
                    worlds_with_resource.append((wid, available))
            worlds_with_resource.sort(key=lambda x: x[1], reverse=True)

        remaining = amount
        for wid, available in worlds_with_resource:
            if remaining <= 0:
                break
            withdraw = min(available, remaining)
            world_resources[wid].setdefault(resource_name, 0)
            world_resources[wid][resource_name] -= withdraw
            remaining -= withdraw
            from_name = world_names.get(wid)
            to_name = world_names.get(dest_world_id)
            if from_name and to_name:
                pending_transfers.append({
                    'from_faction_id': faction_id,
                    'to_faction_id': receiver_id,
                    'from_world_id': wid,
                    'to_world_id': dest_world_id,
                    'resource_id': resource_id,
                    'resource_name': resource_name,
                    'amount': withdraw,
                    'start_time': current_time,
                    'from_world_name': from_name,
                    'to_world_name': to_name,
                })

        if remaining > 0:
            fulfilled = amount - remaining
            if fulfilled == 0:
                logger.warning(f"  [Trade #{trade['id']}] Could not fulfill {amount:,} {resource_name}")
            else:
                logger.warning(f"  [Trade #{trade['id']}] Partial: {fulfilled:,}/{amount:,} {resource_name}")

    transfers_to_create = []
    if pending_transfers:
        travel_tasks = [
            calculate_travel_time(t['from_world_name'], t['to_world_name'], current_time)
            for t in pending_transfers
        ]
        travel_times = await asyncio.gather(*travel_tasks)
        for i, transfer in enumerate(pending_transfers):
            transfer['arrival_time'] = current_time + travel_times[i]
            del transfer['from_world_name']
            del transfer['to_world_name']
            transfers_to_create.append(transfer)

    return world_resources, transfers_to_create


async def preview_income(faction_id: int, shared_cache: dict = None) -> Dict:
    if shared_cache is None:
        shared_cache = {}

    preview = {
        'worlds': {},
        'global': {'er': 0, 'influence': 0},
        'usages': {
            'fleet_cs': 0,
            'influence_pacts': 0,
            'population_cs': {},
            'trade_deals': [],
            'external_incoming_trades': [],
        },
        'transfers': [],
    }

    status_ids = await _get_status_ids(shared_cache)
    fleet_row = await fetch_fleet_cs_by_status(faction_id, status_ids)
    preview['usages']['fleet_cs'] = calculate_fleet_cs_cost(fleet_row)

    pact_rows = await fetch_pact_types_for_faction(faction_id)
    preview['usages']['influence_pacts'] = calculate_influence_cost_from_pacts(pact_rows)

    pop_rows = await db.fetch("""
        SELECT lt.world_id, COALESCE(lt.amount, 0) as population
        FROM local_treasury lt JOIN resources r ON lt.resource_id = r.id
        WHERE lt.faction_id = $1 AND r.name = 'Population'
    """, faction_id)
    preview['usages']['population_cs'] = population_cs_map(pop_rows)

    from services.income_queries import fetch_outgoing_trades, fetch_external_incoming_trades
    preview['usages']['trade_deals'] = await fetch_outgoing_trades(faction_id)
    preview['usages']['external_incoming_trades'] = await fetch_external_incoming_trades(faction_id)

    faction_data = await fetch_faction_flags(faction_id)
    is_company = faction_data['is_company'] if faction_data else False

    world_data = await fetch_world_data_for_income(faction_id, is_company)
    worlds = [{'world_id': wid, 'population': d['population'], 'army': d['army'], 'pop_cap': d['pop_cap']}
              for wid, d in world_data.items()]

    base_eff = await calculate_efficiency(faction_id)
    is_spec, spec_type, bonus = await detect_specialization(faction_id)
    efficiency_cache = build_efficiency_cache(base_eff, is_spec, spec_type, bonus)

    unrefined_rows = await fetch_unrefined_production_data(faction_id)
    refined_rows = await fetch_refined_capacity_data(faction_id)
    stock_rows = await fetch_local_stock(faction_id)
    refined_stock_rows = await fetch_refined_stock(faction_id)
    storage_rows = await fetch_storage_capacities(faction_id)
    trade_rows = await fetch_all_trade_deals(faction_id)

    unrefined_data_map = build_unrefined_production_map(unrefined_rows)
    refined_capacity_map = build_refined_capacity_map(refined_rows)
    stock_map = build_stock_map(stock_rows)
    refined_stock_map = build_stock_map(refined_stock_rows)
    storage_capacity_map = build_storage_capacity_map(storage_rows, efficiency_cache)
    preview['_storage_capacity_map'] = storage_capacity_map

    outgoing_trade_map: Dict[int, Dict[str, int]] = {}
    for trade in trade_rows:
        sender_wid = trade.get('sender_world_id')
        if sender_wid is None:
            continue
        res = trade['resource_name']
        if res not in ('CM', 'EL', 'CS'):
            continue
        outgoing_trade_map.setdefault(sender_wid, {})
        outgoing_trade_map[sender_wid][res] = (
            outgoing_trade_map[sender_wid].get(res, 0) + trade['amount']
        )

    world_resources = {}

    for world in worlds:
        wid = world['world_id']
        wr, unrefined_prod, refined, _ = compute_world_production(
            wid, unrefined_data_map, refined_capacity_map,
            stock_map, refined_stock_map, storage_capacity_map,
            outgoing_trade_map, efficiency_cache,
        )
        world_resources[wid] = wr
        preview['worlds'][wid] = {
            'production': wr.copy(),
            'unrefined_production': unrefined_prod.copy(),
            'gross_cs': refined.get('CS', 0),
            'population_growth': 0,
            'pop_cap': world['pop_cap'],
        }

    blockaded_world_ids = await fetch_blockaded_world_ids(faction_id)
    preview['_blockaded_world_ids'] = blockaded_world_ids
    world_resources, transfers = await _process_trade_deals(
        faction_id, world_resources, stock_map, blockaded_world_ids
    )
    preview['transfers'] = transfers

    for wid, resources in world_resources.items():
        preview['worlds'][wid]['net_cs_pre_upkeep'] = resources.get('CS', 0)

    fleet_cs_needed = preview['usages']['fleet_cs']
    remaining_fleet_cs = fleet_cs_needed

    for wid in list(world_resources.keys()):
        if remaining_fleet_cs <= 0:
            break
        available = max(0, world_resources[wid].get('CS', 0))
        drawn = min(available, remaining_fleet_cs)
        if drawn > 0:
            world_resources[wid]['CS'] = world_resources[wid].get('CS', 0) - drawn
            remaining_fleet_cs -= drawn

    if remaining_fleet_cs > 0:
        worlds_cs_rows = await fetch_worlds_with_cs(faction_id)
        cs_withdrawals = plan_cs_withdrawals(worlds_cs_rows, remaining_fleet_cs)
        for wid, withdrawn in cs_withdrawals.items():
            world_resources.setdefault(wid, {})
            world_resources[wid]['CS'] = world_resources[wid].get('CS', 0) - withdrawn
        preview['usages']['fleet_cs_paid'] = (fleet_cs_needed - remaining_fleet_cs) + sum(cs_withdrawals.values())
    else:
        preview['usages']['fleet_cs_paid'] = fleet_cs_needed

    for wid, resources in world_resources.items():
        if wid not in preview['worlds']:
            preview['worlds'][wid] = {
                'production': {},
                'gross_cs': 0,
                'population_growth': 0,
                'net_cs_pre_upkeep': 0,
            }
        preview['worlds'][wid]['final'] = resources.copy()

    er_treasury = await fetch_er_treasury(faction_id)
    population = await fetch_total_population(faction_id)
    army = await fetch_total_army(faction_id)
    working_population = max(0, population - army)
    preview['global']['er'] = calculate_er_income(er_treasury, working_population, is_company)

    hex_count = await fetch_hex_count(faction_id)
    current_influence = await fetch_current_influence(faction_id)
    influence_cost = preview['usages']['influence_pacts']
    preview['global']['influence'] = calculate_influence_income(hex_count, influence_cost, current_influence)

    return preview


SCOPE_LEVELS = {
    'extractors': 1,
    'extractors_refineries': 2,
    'extractors_refineries_trade': 3,
    'extractors_refineries_trade_upkeep': 4,
    'full': 5,
}


async def execute_income(faction_id: int, shared_cache: dict = None, scope: str = 'full'):
    if shared_cache is None:
        shared_cache = {}

    scope_level = SCOPE_LEVELS.get(scope, 5)

    preview = await preview_income(faction_id, shared_cache)

    if 'resource_map' in shared_cache:
        resource_map = shared_cache['resource_map']
    else:
        resource_map = await fetch_resource_map()

    blockaded_world_ids = preview.get('_blockaded_world_ids', set())
    world_populations = await fetch_all_population_by_world(faction_id)

    if scope_level >= SCOPE_LEVELS['extractors_refineries_trade_upkeep']:
        total_cs_available = 0
        total_cs_needed_for_pop = 0
        total_cs_needed_for_fleets = preview['usages']['fleet_cs']

        world_cs_info = {}
        for wid, data in preview['worlds'].items():
            gross_cs = data.get('gross_cs', 0)
            net_cs_pre_upkeep = data.get('net_cs_pre_upkeep', 0)
            world_pop = world_populations.get(wid, 0)
            world_cs_needed = math.ceil(world_pop / POPULATION_PER_CS)
            is_blockaded = wid in blockaded_world_ids

            world_cs_info[wid] = {
                'gross_cs': gross_cs,
                'net_cs_pre_upkeep': net_cs_pre_upkeep,
                'cs_needed': world_cs_needed,
                'is_blockaded': is_blockaded,
                'population': world_pop,
                'pop_cap': data.get('pop_cap', 0),
            }

            if not is_blockaded:
                total_cs_available += gross_cs
                total_cs_needed_for_pop += world_cs_needed

        global_cs = sum(
            info['gross_cs'] for info in world_cs_info.values() if not info['is_blockaded']
        )
        global_population = sum(
            info['population'] for info in world_cs_info.values() if not info['is_blockaded']
        )

        cs_resource_id = resource_map.get('CS')
        stored_cs_per_world = {}
        stored_cs_total = 0
        if cs_resource_id:
            rows = await fetch_stored_cs(faction_id, cs_resource_id)
            for row in rows:
                stored_cs_per_world[row['world_id']] = row['amount']
                if row['world_id'] not in blockaded_world_ids:
                    stored_cs_total += row['amount']
        global_cs += stored_cs_total

        cs_available_for_fleets = total_cs_available - total_cs_needed_for_pop
        cs_deficit_for_fleets = max(0, total_cs_needed_for_fleets - cs_available_for_fleets)
        if cs_deficit_for_fleets > 0:
            if stored_cs_total < cs_deficit_for_fleets:
                await process_fleet_cs_damage(faction_id, cs_deficit_for_fleets - stored_cs_total)

        global_cs_after_fleets = max(0, global_cs - total_cs_needed_for_fleets)
    else:
        world_cs_info = {
            wid: {
                'gross_cs': data.get('gross_cs', 0),
                'net_cs_pre_upkeep': data.get('net_cs_pre_upkeep', 0),
                'cs_needed': math.ceil(world_populations.get(wid, 0) / POPULATION_PER_CS),
                'is_blockaded': wid in blockaded_world_ids,
                'population': world_populations.get(wid, 0),
                'pop_cap': data.get('pop_cap', 0),
            }
            for wid, data in preview['worlds'].items()
        }
        stored_cs_per_world = {}
        global_cs_after_fleets = 0
        global_population = sum(
            info['population'] for info in world_cs_info.values() if not info['is_blockaded']
        )


    storage_capacity_map = preview.get('_storage_capacity_map', {})
    local_deltas = []
    for wid, data in preview['worlds'].items():
        if scope_level == SCOPE_LEVELS['extractors']:
            resources_to_apply = data.get('unrefined_production', {})
        elif scope_level == SCOPE_LEVELS['extractors_refineries']:
            resources_to_apply = data.get('production', {})
        else:
            resources_to_apply = data.get('final', {})

        world_caps = storage_capacity_map.get(wid, {})
        for resource_name, amount in resources_to_apply.items():
            resource_id = resource_map.get(resource_name)
            if not resource_id:
                continue
            storable = resource_name in STORABLE_RESOURCES
            cap = world_caps.get(resource_name, 0) if storable else 0
            local_deltas.append({
                'world_id': wid,
                'resource_id': resource_id,
                'amount': int(amount),
                'capacity': int(cap),
                'storable': storable,
            })

    population_deltas = []
    if scope_level >= SCOPE_LEVELS['full']:
        for wid, info in world_cs_info.items():
            local_cs_gross = info['gross_cs'] + stored_cs_per_world.get(wid, 0)
            pop_growth = calculate_population_growth(
                population=info['population'],
                global_cs=global_cs_after_fleets,
                global_population=global_population,
                local_cs_production=local_cs_gross,
                is_blockaded=info['is_blockaded'],
            )
            if pop_growth != 0:
                population_deltas.append({
                    'world_id': wid,
                    'amount': int(pop_growth),
                    'pop_cap': int(info['pop_cap']),
                })

    er_delta = int(preview['global']['er']) if scope_level >= SCOPE_LEVELS['full'] else 0
    influence_delta = int(preview['global']['influence']) if scope_level >= SCOPE_LEVELS['full'] else 0

    transfers_payload = []
    if scope_level >= SCOPE_LEVELS['extractors_refineries_trade']:
        for transfer in preview.get('transfers', []):
            transfers_payload.append({
                'from_faction_id': transfer['from_faction_id'],
                'to_faction_id':   transfer['to_faction_id'],
                'from_world_id':   transfer['from_world_id'],
                'to_world_id':     transfer['to_world_id'],
                'resource_id':     transfer['resource_id'],
                'amount':          transfer['amount'],
                'start_time':      transfer['start_time'].isoformat(),
                'arrival_time':    transfer['arrival_time'].isoformat(),
            })

    await db.execute(
        "SELECT sp_apply_income_cycle($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb)",
        faction_id,
        er_delta,
        influence_delta,
        json.dumps(local_deltas),
        json.dumps(population_deltas),
        json.dumps(transfers_payload),
    )
