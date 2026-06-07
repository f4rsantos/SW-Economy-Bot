import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from database.db_manager import db
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
    resources = await db.fetch("SELECT resource_id, amount FROM transfer_resources WHERE transfer_id = $1", transfer_id)
    for resource in resources:
        await db.execute(
            """
            INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (faction_id, world_id, resource_id)
            DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount
            """,
            to_faction_id, to_world_id, resource['resource_id'], resource['amount']
        )
    await db.execute("DELETE FROM transfer_resources WHERE transfer_id = $1", transfer_id)
    result = await db.execute("DELETE FROM resource_transfers WHERE id = $1", transfer_id)
    if result != "DELETE 0":
        logger.info(f"Transfer {transfer_id} completed")


async def handle_fleet_arrival(payload: dict):
    fleet_id = payload['fleet_id']
    await db.execute(
        """
        UPDATE fleets
        SET position = moving_to, moving_to = NULL, moving_since = NULL, status_id = 1
        WHERE id = $1 AND moving_to IS NOT NULL
        """,
        fleet_id
    )
    logger.info(f"Fleet #{fleet_id} arrived")


async def handle_construction_complete(payload: dict):
    order_id = payload['order_id']
    fleet_id = payload['fleet_id']
    vehicle_id = payload['vehicle_id']
    quantity = payload['quantity']
    async with db.get_connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO fleet_vehicles (fleet_id, vehicle_id, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (fleet_id, vehicle_id)
                DO UPDATE SET amount = fleet_vehicles.amount + EXCLUDED.amount
                """,
                fleet_id, vehicle_id, quantity
            )
            await conn.execute(
                """
                UPDATE fleets
                SET total_cs = (
                    SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
                    FROM fleet_vehicles fv
                    JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
                    JOIN resources r ON vc.resource_id = r.id
                    WHERE fv.fleet_id = fleets.id AND r.name = 'CS'
                )
                WHERE id = $1
                """,
                fleet_id
            )
            result = await conn.execute("DELETE FROM vehicle_construction WHERE id = $1", order_id)
            if result == "DELETE 0":
                raise Exception(f"Construction order {order_id} already processed")
    logger.info(f"Construction order {order_id} completed — {quantity} vehicles added to fleet {fleet_id}")


async def handle_recruitment_complete(payload: dict):
    recruitment_id = payload['recruitment_id']
    fleet_id = payload['fleet_id']
    amount = payload['amount']
    result = await db.execute("DELETE FROM military_recruitment WHERE id = $1 AND status = 'training'", recruitment_id)
    if result != "DELETE 0":
        await db.execute("UPDATE fleets SET infantry_count = infantry_count + $1 WHERE id = $2", amount, fleet_id)
        logger.info(f"Recruitment {recruitment_id} completed — {amount} soldiers added to fleet {fleet_id}")


async def check_income_cycle(skip_income: bool = False):
    if skip_income:
        return
    now = datetime.now(timezone.utc)
    try:
        settings = await db.fetchrow("SELECT last_income, income_day FROM settings LIMIT 1")
        if not settings:
            income_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            await db.execute("INSERT INTO settings (last_income, income_day) VALUES ($1, 6)", income_date)
            return

        last_income = settings['last_income']
        income_day = settings['income_day'] or 6
    except Exception as e:
        logger.warning(f"Could not read settings table: {e}")
        return

    if not last_income:
        income_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        await db.execute("UPDATE settings SET last_income = $1", income_date)
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
        factions = await db.fetch("SELECT id, name FROM factions")

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
                    await execute_income(faction['id'], shared_cache)
                except Exception as e:
                    logger.exception(f"  ✗ Error processing income for {faction['name']}: {e}")

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
        await db.execute("UPDATE settings SET last_income = $1", income_date)
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


async def check_continuity_protocol():
    if _bot is None:
        return
    try:
        settings = await db.fetchrow("SELECT continuity_triggered_at FROM settings LIMIT 1")
        if not settings or not settings["continuity_triggered_at"]:
            return

        triggered_at = settings["continuity_triggered_at"]
        if (datetime.now(timezone.utc) - triggered_at) < timedelta(days=7):
            return

        successor_id = int(os.getenv("DESIGNATED_SUCCESSOR_ID", "0"))
        continuity_email = os.getenv("CONTINUITY_EMAIL", "(not set)")
        continuity_password = os.getenv("CONTINUITY_PASSWORD", "(not set)")

        try:
            successor = await _bot.fetch_user(successor_id)
            await successor.send(
                f"🔑 **PROJECT CONTINUITY PROTOCOL — 7-Day Window Expired**\n\n"
                f"Fer0 did not deactivate the Protocol within 7 days of "
                f"<t:{int(triggered_at.timestamp())}:F>.\n\n"
                f"You are now authorized to carry on development of SWU.\n\n"
                f"**Credentials:**\n"
                f"Email: `{continuity_email}`\n"
                f"Password: `{continuity_password}`"
            )
        except Exception as e:
            logger.error(f"Continuity: failed to DM Designated Successor: {e}")

        await db.execute("UPDATE settings SET continuity_triggered_at = NULL")
        await db.execute("UPDATE operators SET continuity_confirmed = false")
    except Exception as e:
        logger.error(f"Continuity protocol check error: {e}")


async def handle_income_cycle(payload: dict):
    await check_income_cycle(skip_income=_skip_income)
    await event_queue.push_income_event()


async def handle_scripting_run(payload: dict):
    from services.scripting.executor import run_scheduled_scripts
    await run_scheduled_scripts(current_time=datetime.now(timezone.utc))
    next_run = datetime.now(timezone.utc) + timedelta(days=7)
    await event_queue.push(next_run, 'scripting_run', {})


async def handle_continuity_check(payload: dict):
    await check_continuity_protocol()
    next_check = datetime.now(timezone.utc) + timedelta(days=1)
    await event_queue.push(next_check, 'continuity_check', {})


def _register_handlers():
    event_queue.register_handler('transfer_arrival', handle_transfer_arrival)
    event_queue.register_handler('fleet_arrival', handle_fleet_arrival)
    event_queue.register_handler('construction_complete', handle_construction_complete)
    event_queue.register_handler('recruitment_complete', handle_recruitment_complete)
    event_queue.register_handler('income_cycle', handle_income_cycle)
    event_queue.register_handler('scripting_run', handle_scripting_run)
    event_queue.register_handler('continuity_check', handle_continuity_check)


async def run_background_tasks(bot=None, skip_income: bool = False):
    global _bot, _skip_income
    _bot = bot
    _skip_income = skip_income
    _register_handlers()
    logger.info("Background tasks started")

    await event_queue.push_income_event()
    now = datetime.now(timezone.utc)
    await event_queue.push(now + timedelta(minutes=5), 'scripting_run', {})
    await event_queue.push(now + timedelta(hours=1), 'continuity_check', {})

    await event_queue.worker()
