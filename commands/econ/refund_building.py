# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.building_service import refund_building as refund_building_service
from services.validation_service import require_faction, require_world


@app_commands.command(name="refund-building", description="Refund buildings")
@app_commands.describe(
    faction="Faction name",
    building_id="Building type ID",
    world="World name",
    amount="Number of buildings to refund",
    level="Building level (1-10)",
    week="True if built within last week for 100% refund"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def refund_building(
    interaction: discord.Interaction,
    faction: str,
    building_id: int,
    world: str,
    amount: int = 1,
    level: int = 1,
    week: bool = False
):
    await defer_response(interaction)

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    if level < 1 or level > 10:
        await interaction.followup.send(embed=error_embed("Error", "Level must be between 1 and 10."))
        return

    r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    faction_data = r_faction_data.data
    world_data = r_world.data

    faction_color = hex_to_int(faction_data.color)

    try:
        result = await refund_building_service(
            faction_data.id, world_data['id'], building_id, amount, level, week
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    refund_str = ", ".join(f"{handle_return(amt)} {res}" for res, amt in result['refunds'].items())
    rate_label = "100%" if week else "30%"
    embed = success_embed(
        "Building Refund",
        f"**{faction_data.display_name}** has refunded {amount} level {level} {result['building_name']} on **{world_data['name']}** for {refund_str} ({rate_label} rate)"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(refund_building)
