# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import logging
import os
import discord
from datetime import datetime, timedelta, timezone
from repositories import background_tasks_repo, notification_repo
from services.income_service import execute_income
from services.event_queue import event_queue
from services import notification_service

logger = logging.getLogger(__name__)

INCOME_INTERVAL = timedelta(days=7)


class IncomeCycleFailed(Exception):
    pass


_bot = None
_skip_income = False


def _row_value(row, key, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = getattr(row, key, None)
    return default if value is None else value


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
    context = await notification_repo.get_fleet_context(fleet_id)
    await background_tasks_repo.complete_fleet_arrival(fleet_id)
    logger.info(f"Fleet #{fleet_id} arrived")
    if context:
        try:
            await notification_service.notify_fleet_arrival(
                context['faction_id'], context['fleet_name'] or f"Fleet #{fleet_id}", context['world_name']
            )
        except Exception as e:
            logger.warning(f"Fleet arrival notification failed for fleet {fleet_id}: {e}")


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
    context = await notification_repo.get_recruitment_context(recruitment_id)
    result = await background_tasks_repo.delete_completed_recruitment(recruitment_id)
    if result != "DELETE 0":
        await background_tasks_repo.add_fleet_infantry(fleet_id, amount)
        logger.info(f"Recruitment {recruitment_id} completed — {amount} soldiers added to fleet {fleet_id}")
        try:
            if context:
                await notification_service.notify_recruitment_complete(
                    context['faction_id'], f"Fleet #{fleet_id}", amount
                )
        except Exception as e:
            logger.warning(f"Recruitment notification failed for recruitment {recruitment_id}: {e}")


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

        pending_resources_earned = {}
        pending_population_change = 0

        for i in range(cycles_to_run):
            logger.info(f"Processing Catch-Up Batch {i+1}/{cycles_to_run}")

            if i > 0:
                try:
                    await post_weekly_spend_report(pending_resources_earned, pending_population_change)
                except Exception as e:
                    logger.error(f"  Weekly spend report error: {e}")

            spinner_chars = ["\\", "|", "/", "-"]
            spinner_running = True

            async def spin():
                idx = 0
                while spinner_running:
                    print(f"\r  Processing {spinner_chars[idx]} ", end="", flush=True)
                    idx = (idx + 1) % 4
                    await asyncio.sleep(0.25)

            spinner_task = asyncio.create_task(spin())

            global_resources_earned = {}
            global_population_change = 0

            failed_factions = []

            async def _run_one(faction):
                faction_id = _row_value(faction, 'id')
                faction_label = _row_value(faction, 'name', default=f"id={faction_id}")
                try:
                    return await execute_income(faction_id, shared_cache)
                except Exception as e:
                    failed_factions.append(faction_label)
                    logger.exception(f"  Error processing income for {faction_label}: {e}")
                    return None

            try:
                batch_results = await asyncio.gather(*[_run_one(f) for f in factions])
            finally:
                spinner_running = False
                await spinner_task
                print("\r  Processing... done!    ")

            for result in batch_results:
                if not result:
                    continue
                for resource_name, amount in result['resources_earned'].items():
                    global_resources_earned[resource_name] = global_resources_earned.get(resource_name, 0) + amount
                global_population_change += result['population_change']

            if failed_factions:
                logger.error(
                    f"  Income failed for {len(failed_factions)}/{len(factions)} faction(s): "
                    f"{', '.join(failed_factions)}"
                )

            if factions and len(failed_factions) == len(factions):
                raise IncomeCycleFailed("INCOME ABORTED, all factions failed")

            try:
                from services.scripting.executor import run_income_day_scripts
                await run_income_day_scripts(
                    factions=factions,
                    income_weekday_name=income_weekday_name,
                    current_time=now,
                )
            except Exception as e:
                logger.error(f"  Script runner (income day) error: {e}")

            pending_resources_earned = global_resources_earned
            pending_population_change = global_population_change

            try:
                await notification_service.notify_income_cycle_complete()
            except Exception as e:
                logger.warning(f"Income cycle notification failed: {e}")

        try:
            await post_weekly_spend_report(pending_resources_earned, pending_population_change)
        except Exception as e:
            logger.error(f"  Weekly spend report error: {e}")

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


async def post_weekly_spend_report(resources_earned: dict, population_change: int):
    from services import spend_service
    from utils.currency import handle_return
    from utils.embeds import create_embed

    channel = await _find_channel_by_name(NATIONAL_UPDATES_CHANNEL_NAME)
    if not channel:
        logger.warning(f"Weekly spend report: channel '{NATIONAL_UPDATES_CHANNEL_NAME}' not found, skipping post")
        return

    async def post(spend_totals) -> bool:
        earned_total = sum(resources_earned.values())
        spent_total = sum(t.amount for t in spend_totals)
        net_change = earned_total - spent_total
        try:
            population_sign = "+" if population_change > 0 else ""
            net_sign = "+" if net_change > 0 else ""
            lines = [
                f"Total resources earned: {handle_return(earned_total)}",
                f"Population change: {population_sign}{handle_return(population_change)}",
                f"Total resources spent: {handle_return(spent_total)}",
                f"Change: {net_sign}{handle_return(net_change)}",
            ]
            embed = create_embed(
                title="Weekly National Report",
                description="\n".join(lines),
            )
            await channel.send(embed=embed)
            return True
        except Exception as e:
            logger.error(f"  Weekly spend report: failed to post to channel: {e}")
            return False

    try:
        await spend_service.reset_snapshot_and_report(post)
    except Exception as e:
        logger.error(f"  Weekly spend report: report/reset failed, spend data preserved: {e}")


async def handle_income_cycle(payload: dict):
    reschedule = True
    try:
        await check_income_cycle(skip_income=_skip_income)
    except IncomeCycleFailed as e:
        reschedule = False
        logger.error(str(e))
    finally:
        if reschedule:
            try:
                await event_queue.push_income_event()
            except Exception as e:
                logger.exception(f"Failed to reschedule income cycle event: {e}")


async def handle_scripting_run(payload: dict):
    from services.scripting.executor import run_scheduled_scripts
    try:
        await run_scheduled_scripts(current_time=datetime.now(timezone.utc))
    finally:
        next_run = datetime.now(timezone.utc) + timedelta(days=1)
        try:
            await event_queue.push(next_run, 'scripting_run', {})
        except Exception as e:
            logger.exception(f"Failed to reschedule scripting run: {e}")


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
    notification_service.set_bot(bot)
    _register_handlers()
    logger.info("Background tasks started")

    await event_queue.push_income_event()
    now = datetime.now(timezone.utc)
    await event_queue.push(now + timedelta(minutes=5), 'scripting_run', {})

    await event_queue.worker()
