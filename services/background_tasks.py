# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import logging
import os
import discord
from datetime import datetime, timedelta, timezone
from repositories import background_tasks_repo
from services.income_service import execute_income
from services.event_queue import event_queue

logger = logging.getLogger(__name__)

INCOME_INTERVAL = timedelta(days=7)

_bot = None
_skip_income = False


async def handle_transfer_arrival(payload: dict):
    transfer_id = payload['transfer_id']
    to_faction_id = payload['to_faction_id']
    to_world_id = payload['to_world_id']
    status_row = await background_tasks_repo.get_transfer_status(transfer_id)
    if not status_row or status_row['name'] != 'in_transit':
        return
    resources = await background_tasks_repo.get_transfer_resources(transfer_id)
    for resource in resources:
        await background_tasks_repo.deposit_local_treasury(
            to_faction_id, to_world_id, resource['resource_id'], resource['amount']
        )
    await background_tasks_repo.delete_transfer_resources(transfer_id)
    result = await background_tasks_repo.delete_resource_transfer(transfer_id)
    if result != "DELETE 0":
        logger.info(f"Transfer {transfer_id} completed")


async def handle_fleet_arrival(payload: dict):
    fleet_id = payload['fleet_id']
    await background_tasks_repo.complete_fleet_arrival(fleet_id)
    logger.info(f"Fleet #{fleet_id} arrived")


async def handle_construction_complete(payload: dict):
    order_id = payload['order_id']
    fleet_id = payload['fleet_id']
    vehicle_id = payload['vehicle_id']
    quantity = payload['quantity']
    async with background_tasks_repo.get_connection() as conn:
        async with conn.transaction():
            await background_tasks_repo.add_fleet_vehicles(conn, fleet_id, vehicle_id, quantity)
            await background_tasks_repo.recalc_fleet_cs(conn, fleet_id)
            result = await background_tasks_repo.delete_construction_order(conn, order_id)
            if result == "DELETE 0":
                raise Exception(f"Construction order {order_id} already processed")
    logger.info(f"Construction order {order_id} completed — {quantity} vehicles added to fleet {fleet_id}")


async def handle_recruitment_complete(payload: dict):
    recruitment_id = payload['recruitment_id']
    fleet_id = payload['fleet_id']
    amount = payload['amount']
    result = await background_tasks_repo.delete_completed_recruitment(recruitment_id)
    if result != "DELETE 0":
        await background_tasks_repo.add_fleet_infantry(fleet_id, amount)
        logger.info(f"Recruitment {recruitment_id} completed — {amount} soldiers added to fleet {fleet_id}")


async def check_income_cycle(skip_income: bool = False):
    if skip_income:
        return
    now = datetime.now(timezone.utc)
    try:
        settings = await background_tasks_repo.get_settings()
        if not settings:
            income_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            await background_tasks_repo.insert_initial_settings(income_date)
            return

        last_income = settings['last_income']
        income_day = settings['income_day'] or 6
    except Exception as e:
        logger.warning(f"Could not read settings table: {e}")
        return

    if not last_income:
        income_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        await background_tasks_repo.set_last_income(income_date)
        return

    target_weekday = income_day - 1
    current_check = last_income
    cycles_to_run = 0

    while True:
        next_day = current_check + timedelta(days=1)
        if next_day > now:
            break
        current_check = next_day
        if current_check.weekday() == target_weekday:
            cycles_to_run += 1
            last_income = current_check

    if cycles_to_run > 0:
        logger.info("=" * 60)
        logger.info("PROCESSING INCOME - DO NOT CLOSE THE BOT UNTIL ALL CLEAR")
        logger.info(f"   Catching up {cycles_to_run} cycle(s) (since: {settings['last_income']})")
        logger.info("=" * 60)

        from database.static_cache import static_cache
        factions = await background_tasks_repo.get_factions()

        shared_cache = {
            'status_ids': dict(static_cache.fleet_status),
            'resource_map': {v['name']: v['id'] for v in static_cache.resources_by_id.values()},
        }

        weekday_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
        income_weekday_name = weekday_names[target_weekday]

        for i in range(cycles_to_run):
            logger.info(f"Processing Catch-Up Batch {i+1}/{cycles_to_run}")

            spinner_chars = ["\\", "|", "/", "-"]
            spinner_running = True

            async def spin():
                idx = 0
                while spinner_running:
                    print(f"\r  Processing {spinner_chars[idx]} ", end="", flush=True)
                    idx = (idx + 1) % 4
                    await asyncio.sleep(0.25)

            spinner_task = asyncio.create_task(spin())

            async def _run_one(faction):
                try:
                    await execute_income(faction.id, shared_cache)
                except Exception as e:
                    logger.exception(f"  ✗ Error processing income for {faction.name}: {e}")

            await asyncio.gather(*[_run_one(f) for f in factions])

            spinner_running = False
            await spinner_task
            print("\r  Processing... done!    ")

            try:
                from services.scripting.executor import run_income_day_scripts
                await run_income_day_scripts(
                    factions=factions,
                    income_weekday_name=income_weekday_name,
                    current_time=now,
                )
            except Exception as e:
                logger.error(f"  Script runner (income day) error: {e}")

        income_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        await background_tasks_repo.set_last_income(income_date)
        logger.info("=" * 60)
        logger.info("INCOME PROCESSED")
        logger.info(f"   {cycles_to_run} cycle(s) completed. Next check from: {income_date}")
        logger.info("=" * 60)
        try:
            from services.dashboard import record_income_run
            for _ in range(cycles_to_run):
                record_income_run()
        except Exception:
            pass

        for _ in range(cycles_to_run):
            try:
                await run_casino_weekly_trim()
            except Exception as e:
                logger.error(f"  Casino weekly trim error: {e}")


NATIONAL_UPDATES_CHANNEL_NAME = "national-updates"


async def _find_channel_by_name(channel_name: str):
    if _bot is None:
        return None
    for channel in _bot.get_all_channels():
        if isinstance(channel, discord.TextChannel) and channel.name == channel_name:
            return channel
    return None


async def run_casino_weekly_trim():
    from services.casino_service import apply_weekly_trim
    from utils.currency import handle_return

    results = await apply_weekly_trim()
    trimmed_total = sum(r['trimmed'] for r in results)
    pool_total = sum(r['pool_after'] for r in results)

    if trimmed_total <= 0:
        return

    channel = await _find_channel_by_name(NATIONAL_UPDATES_CHANNEL_NAME)
    if not channel:
        logger.warning(f"Casino weekly trim: channel '{NATIONAL_UPDATES_CHANNEL_NAME}' not found, skipping post")
        return

    lines = [
        f"Weekly Pool: {handle_return(pool_total)}",
        f"Resources Trimmed this Week: {handle_return(trimmed_total)}",
    ]
    await channel.send("\n".join(lines))


async def handle_income_cycle(payload: dict):
    await check_income_cycle(skip_income=_skip_income)
    await event_queue.push_income_event()


async def handle_scripting_run(payload: dict):
    from services.scripting.executor import run_scheduled_scripts
    await run_scheduled_scripts(current_time=datetime.now(timezone.utc))
    next_run = datetime.now(timezone.utc) + timedelta(days=1)
    await event_queue.push(next_run, 'scripting_run', {})


def _register_handlers():
    event_queue.register_handler('transfer_arrival', handle_transfer_arrival)
    event_queue.register_handler('fleet_arrival', handle_fleet_arrival)
    event_queue.register_handler('construction_complete', handle_construction_complete)
    event_queue.register_handler('recruitment_complete', handle_recruitment_complete)
    event_queue.register_handler('income_cycle', handle_income_cycle)
    event_queue.register_handler('scripting_run', handle_scripting_run)


async def run_background_tasks(bot=None, skip_income: bool = False):
    global _bot, _skip_income
    _bot = bot
    _skip_income = skip_income
    _register_handlers()
    logger.info("Background tasks started")

    await event_queue.push_income_event()
    now = datetime.now(timezone.utc)
    await event_queue.push(now + timedelta(minutes=5), 'scripting_run', {})

    await event_queue.worker()
