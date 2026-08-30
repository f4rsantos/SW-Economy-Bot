# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from database.static_cache import static_cache
from utils.embeds import success_embed, error_embed


@app_commands.command(name="reload_static", description="Reload static cache (worlds, buildings, resources, etc.)")
@require_access_level(3)
async def reload_static_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        await static_cache.load()
        await interaction.followup.send(embed=success_embed("Static Cache Reloaded", "All static data reloaded from database."))
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Failed to reload static cache: {e}"))


async def setup(bot):
    bot.tree.add_command(reload_static_cmd)
