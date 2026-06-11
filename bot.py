import asyncio
import logging
import math
import os

import discord
from discord.ext import commands
from packaging.version import Version

from database.db_manager import db
from error_handler import setup_error_handler
from loader import load_commands

logger = logging.getLogger(__name__)

_intentional_shutdown = False


def is_shutdown_intentional() -> bool:
    return _intentional_shutdown


def start_bot(supabase_client, supabase_user_uuid: str, continuity_mode: bool, no_income: bool):
    global _intentional_shutdown

    logger.info("Initializing Discord bot...")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.supabase_client = supabase_client

    setup_error_handler(bot)

    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            from services.dashboard import record_command
            cmd_name = interaction.command.name if interaction.command else 'unknown'
            record_command(cmd_name, str(interaction.user))

    @bot.event
    async def on_ready():
        from database.cache_manager import cache
        from services.background_tasks import run_background_tasks

        if hasattr(bot, '_ready_complete'):
            logger.info(f"Bot reconnected as {bot.user}")
            return

        original_send_message = discord.InteractionResponse.send_message

        async def send_message_with_custom_message(self, *args, **kwargs):
            embed = kwargs.get('embed')
            if embed and hasattr(self, '_parent') and self._parent:
                user_id = self._parent.user.id
                custom_message = cache.get_custom_message(user_id)
                if custom_message:
                    current_footer = embed.footer.text if embed.footer else ""
                    embed.set_footer(text=f"{current_footer} | {custom_message}" if current_footer else custom_message)
            return await original_send_message(self, *args, **kwargs)

        discord.InteractionResponse.send_message = send_message_with_custom_message

        logger.info("=" * 70)
        logger.info(f"Bot connected as: {bot.user.name}")
        logger.info(f"Connected to {len(bot.guilds)} guild(s)")
        logger.info("=" * 70)

        logger.info("Connecting to database...")
        await db.connect()

        try:
            _min_ver_row = await db.fetchrow("SELECT min_version FROM settings LIMIT 1")
            _min_ver = _min_ver_row['min_version'] if _min_ver_row else None
            _bot_ver = os.getenv("BOT_VERSION", "")
            if _min_ver and _bot_ver:
                if Version(_bot_ver) < Version(_min_ver):
                    global _intentional_shutdown
                    logger.warning("=" * 60)
                    logger.warning("  Bot can't start: outdated version.")
                    logger.warning(f"  Running: v{_bot_ver}  |  Required: v{_min_ver}")
                    logger.warning("  Please update the bot, then press Ctrl+C to exit.")
                    logger.warning("=" * 60)
                    _intentional_shutdown = True
                    while True:
                        await asyncio.sleep(3600)
        except Exception as e:
            logger.warning(f"Note: Could not check min_version: {e}")

        if continuity_mode:
            await _check_continuity(bot, supabase_user_uuid)

        db_size_gb = await _check_db_size()

        logger.info("Loading static cache...")
        from database.static_cache import static_cache
        await static_cache.load()
        logger.info("Loading dynamic cache...")
        await cache.load_full_cache()
        def _log_task_crash(name):
            def callback(task):
                if task.cancelled():
                    return
                exc = task.exception()
                if exc:
                    logger.error(f"Background task '{name}' crashed: {type(exc).__name__}: {exc}", exc_info=exc)
            return callback

        bot._bg_tasks = []
        logger.info("Starting cache refresh loop...")
        cache_task = bot.loop.create_task(cache.start_refresh_loop())
        cache_task.add_done_callback(_log_task_crash("cache refresh loop"))
        bot._bg_tasks.append(cache_task)
        logger.info("Starting background tasks...")
        events_task = bot.loop.create_task(run_background_tasks(bot, skip_income=no_income))
        events_task.add_done_callback(_log_task_crash("event queue worker"))
        bot._bg_tasks.append(events_task)
        if no_income:
            logger.warning("  Income processing DISABLED (--no-income flag)")
        logger.info("Loading commands...")
        await load_commands(bot, continuity_mode=continuity_mode)

        bot._ready_complete = True

        from services.dashboard import start_dashboard, update_bot_info, update_db_info, update_cache_info, set_flags
        set_flags(no_income=no_income, continuity_mode=continuity_mode)
        update_bot_info(
            bot_name=str(bot.user.name),
            bot_id=bot.user.id,
            guild_count=len(bot.guilds),
            ping_ms=bot.latency * 1000,
            bot_version=os.getenv('BOT_VERSION', ''),
        )
        update_db_info(connected=True, size_gb=db_size_gb)
        update_cache_info(
            factions=len(cache.get_all_factions()),
            players=len(cache.users),
        )
        start_dashboard()
        bot.loop.create_task(_dashboard_ping_loop(bot))

        logger.info("Bot is ready and operational.")
        logger.info("Press Ctrl+C to stop the bot.")

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param.name}")
        else:
            await ctx.send("An error occurred while processing the command.")

    try:
        bot.run(os.getenv("DISCORD_TOKEN"))
    except KeyboardInterrupt:
        _intentional_shutdown = True
        logger.info("Bot shutdown requested.")
    except SystemExit as e:
        _intentional_shutdown = True
        logger.info(f"Bot shut down (exit code {e.code}).")
    except Exception as e:
        logger.error("=" * 60)
        logger.error("  BOT CRASHED")
        logger.error("=" * 60)
        logger.exception(f"  {type(e).__name__}: {e}")


async def _check_db_size() -> float | None:
    try:
        result = await db.fetchrow("SELECT get_db_size() as size_gb")
        if result:
            size_gb = float(result['size_gb'])
            logger.info(f"Database size: {size_gb:.4f} GB")
            if size_gb > 0.48:
                logger.warning("=" * 60)
                logger.warning("  WARNING: DATABASE SIZE CRITICAL!")
                logger.warning(f"   Current size: {size_gb:.4f} GB")
                logger.warning("   Maximum recommended: 0.48 GB")
                logger.warning("   DATABASE CLEANUP REQUIRED!")
                logger.warning("=" * 60)
            return size_gb
    except Exception as e:
        logger.warning(f"Note: Could not check database size: {e}")
    return None


async def _check_continuity(bot, supabase_user_uuid: str):
    try:
        settings = await db.fetchrow("SELECT continuity_triggered_at FROM settings LIMIT 1")
        if not (settings and settings['continuity_triggered_at']):
            return
        if not supabase_user_uuid:
            return
        op = await db.fetchrow(
            "SELECT id, continuity_confirmed FROM operators "
            "WHERE user_id = $1::uuid AND locked = false",
            supabase_user_uuid,
        )
        if not (op and not op['continuity_confirmed']):
            return
        triggered = settings['continuity_triggered_at']
        logger.info("=" * 60)
        logger.info("  PROJECT CONTINUITY PROTOCOL — ACTIVATED")
        logger.info("=" * 60)
        logger.info(f"  Activated: {triggered.strftime('%Y-%m-%d %H:%M UTC')}")
        ans = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: input("  Confirm activation? [Y/N]: ").strip()
        )
        if ans.upper() != 'Y':
            logger.info("  Confirmation declined.")
            return
        await db.execute(
            "UPDATE operators SET continuity_confirmed = true WHERE user_id = $1::uuid",
            supabase_user_uuid,
        )
        logger.info("  Confirmation recorded.")
        total = await db.fetchval("SELECT COUNT(*) FROM operators WHERE locked = false")
        confirmed = await db.fetchval(
            "SELECT COUNT(*) FROM operators WHERE locked = false AND continuity_confirmed = true"
        )
        required = total if total < 3 else max(3, math.ceil(total / 2))
        if confirmed >= required:
            logger.info("=" * 60)
            logger.info("  QUORUM REACHED — Protocol fully active")
            logger.info(f"  ({confirmed}/{total} operators confirmed)")
            logger.info("=" * 60)
            fer0_id = int(os.getenv("FER0_ID", "0"))
            if fer0_id:
                try:
                    fer0 = await bot.fetch_user(fer0_id)
                    await fer0.send(
                        f"**PROJECT CONTINUITY PROTOCOL — QUORUM REACHED**\n\n"
                        f"**{confirmed}/{total}** operators have confirmed.\n"
                        f"The protocol is now fully active."
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Note: Could not perform continuity check: {e}")


async def _dashboard_ping_loop(bot):
    from services.dashboard import update_bot_info, update_cache_info
    from database.cache_manager import cache
    while True:
        await asyncio.sleep(30)
        try:
            update_bot_info(
                bot_name=str(bot.user.name),
                bot_id=bot.user.id,
                guild_count=len(bot.guilds),
                ping_ms=bot.latency * 1000,
            )
            update_cache_info(
                factions=len(cache.get_all_factions()),
                players=len(cache.users),
            )
        except Exception:
            pass
