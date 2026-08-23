# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.map_service import get_faction_land
from services.validation_service import require_faction


@app_commands.command(name="land", description="View faction's hexes on all worlds")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def land(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    worlds = await get_faction_land(faction_id)

    if not worlds:
        await interaction.followup.send(embed=error_embed("No Territory", f"{faction_data.display_name} has no claimed hexes."))
        return

    total_hexes = sum(w.territory for w in worlds)
    embed = discord.Embed(title=f"Territory: {faction_data.display_name}", description=f"**Total Hexes:** {total_hexes:,}", color=faction_color)

    world_lines = [f"**{w.name}:** {w.territory:,} hex(es)" for w in worlds]
    for i in range(0, len(world_lines), 20):
        embed.add_field(name="Worlds" if i == 0 else "...", value="\n".join(world_lines[i:i+20]), inline=False)

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(land)
