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

    try:
        await event_queue.load_window()
    except Exception as e:
        logger.error(f"Error reloading event queue: {e}")

    try:
        await check_income_cycle()
    except Exception as e:
        logger.error(f"Error checking income: {e}")

    embed = discord.Embed(title="Sync Complete", color=discord.Color.green())
    embed.add_field(
        name="Actions",
        value="• Event queue reloaded (2h window)\n• Income cycle checked",
        inline=False
    )
    embed.set_footer(text=f"Synced at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(sync)
