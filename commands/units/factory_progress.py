# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import get_factory_progress
from services.validation_service import require_faction, require_world


@app_commands.command(name="factory-progress", description="View vehicle construction progress")
@app_commands.describe(
    faction="Your faction name",
    world="World name (optional, shows all if not specified)"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def factory_progress(interaction: discord.Interaction, faction: str, world: str = None):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        orders = await get_factory_progress(faction_data.id, r_world.data['id'])
    else:
        orders = await get_factory_progress(faction_data.id)

    if not orders:
        location = f" on {world}" if world else ""
        await interaction.followup.send(embed=error_embed("No Construction", f"No active vehicle construction{location}."))
        return

    embed = discord.Embed(
        title=f"Factory Construction Progress{' - ' + world if world else ''}",
        description=f"**{faction_data.display_name}**",
        color=faction_color
    )

    current_world = None
    for order in orders[:25]:
        unit_name = order['fleet_name'] if order['fleet_name'] else f"Unit #{order['fleet_id']}"
        if order['world_name'] != current_world:
            if current_world is not None:
                embed.add_field(name="​", value="", inline=False)
            current_world = order['world_name']
        embed.add_field(
            name=f"{order['world_name']}: {order['vehicle_name']}",
            value=f"**Qty:** {order['quantity']:,} | **Unit:** {unit_name}\n"
                  f"**Space:** {order['factory_space_used']:,}m | **Done:** <t:{int(order['completion_date'].timestamp())}:R>",
            inline=False
        )

    if len(orders) > 25:
        embed.set_footer(text=f"Showing 25 of {len(orders)} orders")

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(factory_progress)
