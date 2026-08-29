# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int, is_faction_leader
from services.faction_service import set_population_limit
from services.validation_service import require_faction


@app_commands.command(name="population-limit", description="Set or clear your faction's self declared population maximum")
@app_commands.describe(
    faction="Faction name",
    limit="Maximum population to set, leave empty to clear the limit"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def population_limit(
    interaction: discord.Interaction,
    faction: str,
    limit: Optional[int] = None
):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    if not await is_faction_leader(interaction.user.id, faction_data):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to set this faction's population limit."))
        return

    faction_color = hex_to_int(faction_data.color)

    try:
        result = await set_population_limit(faction_data.id, limit)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    if result is None:
        embed = success_embed(
            title="Population Limit Cleared",
            description=f"**{faction_data.display_name}** no longer has a self declared population maximum. Only the physical capacity applies."
        )
    else:
        embed = success_embed(
            title="Population Limit Set",
            description=f"**{faction_data.display_name}**'s population will stop growing at {handle_return(result)}."
        )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(population_limit)
