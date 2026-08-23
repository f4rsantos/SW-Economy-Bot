# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from database.static_cache import static_cache
from services.map_service import has_faction_presence
from services.treasury_service import set_resource as set_resource_service
from services.validation_service import require_faction, require_world


@app_commands.command(name="set", description="Set faction resource amount (admin)")
@app_commands.describe(
    faction="Faction name",
    resource_name="Resource name (ER, CM, EL, CS, etc.)",
    amount="Amount to set",
    world="World name for local treasury"
)
@require_access_level(4)
async def set_resource(
    interaction: discord.Interaction,
    faction: str,
    resource_name: str,
    amount: int,
    world: Optional[str] = None
):
    await interaction.response.defer()

    if amount < 0:
        await interaction.followup.send(embed=error_embed("Error", "Amount cannot be negative."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    resource = static_cache.get_resource(resource_name)
    if not resource:
        await interaction.followup.send(embed=error_embed("Error", f"Resource '{resource_name}' not found."))
        return

    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_data = r_world.data
        if not await has_faction_presence(world_data['id'], faction_data.id):
            await interaction.followup.send(embed=error_embed("Error", "Faction has no presence on this world."))
            return
        await set_resource_service(faction_data.id, resource['id'], amount, world_data['id'])
        location = f" on **{world_data['name']}**"
    else:
        await set_resource_service(faction_data.id, resource['id'], amount)
        location = " (global)"

    embed = success_embed(
        title="Resource Set",
        description=f"**{faction_data.display_name}**{location} now has {handle_return(amount)} {resource['name']}"
    )
    embed.color = hex_to_int(faction_data.color)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(set_resource)
