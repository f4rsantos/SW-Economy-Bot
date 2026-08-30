# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.building_service import transfer_building as transfer_building_service
from services.validation_service import require_faction, require_world


@app_commands.command(name="transfer-building", description="Transfer buildings between factions (admin)")
@app_commands.describe(
    from_faction="Source faction name",
    to_faction="Destination faction name",
    building_id="Building type ID",
    world="World name",
    amount="Number of buildings to transfer",
    level="Building level (1-10)"
)
@require_access_level(4)
@ephemeral_capable('from_faction')
async def transfer_building(
    interaction: discord.Interaction,
    from_faction: str,
    to_faction: str,
    building_id: int,
    world: str,
    amount: int = 1,
    level: int = 1
):
    await defer_response(interaction)

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    if level < 1 or level > 10:
        await interaction.followup.send(embed=error_embed("Error", "Level must be between 1 and 10."))
        return

    r_from, r_to, r_world = await asyncio.gather(
        require_faction(from_faction), require_faction(to_faction), require_world(world)
    )
    if not r_from.ok: return await interaction.followup.send(embed=error_embed("Error", r_from.error))
    if not r_to.ok: return await interaction.followup.send(embed=error_embed("Error", r_to.error))
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    from_data = r_from.data
    to_data = r_to.data
    world_data = r_world.data

    try:
        result = await transfer_building_service(from_data['id'], to_data['id'], world_data['id'], building_id, amount, level)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        "Buildings Transferred",
        f"**{from_data['display_name']}** transferred {amount} level {level} {result['building_name']} to **{to_data['display_name']}** on **{world_data['name']}**"
    )
    embed.color = hex_to_int(from_data['color'])
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(transfer_building)
