# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import logging
import discord
from discord import app_commands
from datetime import datetime, timezone
from utils.checks import require_access_level
from services.background_tasks import check_income_cycle
from services.event_queue import event_queue

logger = logging.getLogger(__name__)


@app_commands.command(name="sync", description="Reload event queue and run income check")
@require_access_level(9)
async def sync(interaction: discord.Interaction):
    await interaction.response.defer()

    errors = []

    try:
        await event_queue.load_window()
    except Exception as e:
        logger.exception("Error reloading event queue")
        errors.append(f"Event queue reload failed: {e}")

    try:
        await check_income_cycle()
    except Exception as e:
        logger.exception("Error checking income")
        errors.append(f"Income check failed: {e}")

    worker_alive = event_queue.is_running
    color = discord.Color.green() if worker_alive and not errors else discord.Color.red()
    embed = discord.Embed(title="Sync Complete" if worker_alive and not errors else "Sync Issues Detected", color=color)
    embed.add_field(
        name="Actions",
        value="• Event queue reloaded (2h window)\n• Income cycle checked",
        inline=False
    )
    embed.add_field(
        name="Event Worker",
        value=f"{'Running' if worker_alive else 'NOT RUNNING — events will not execute! Restart the bot.'}\nQueued events: {event_queue.queue_size()}",
        inline=False
    )
    if errors:
        embed.add_field(name="Errors", value="\n".join(f"• {e}"[:1000] for e in errors), inline=False)
    embed.set_footer(text=f"Synced at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(sync)
