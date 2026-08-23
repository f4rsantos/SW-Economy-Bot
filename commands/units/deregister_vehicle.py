# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.vehicle_service import deregister_vehicle as deregister_vehicle_service
from services.validation_service import require_faction, require_vehicle


@app_commands.command(name="deregister", description="Deregister a vehicle design")
@app_commands.describe(
    faction="Faction name or ID that owns the vehicle",
    vehicle_id="Vehicle display ID or name"
)
@require_access_level(0)
async def deregister_vehicle(
    interaction: discord.Interaction,
    faction: str,
    vehicle_id: str
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    r_vehicle_data = await require_vehicle(vehicle_id, faction_data.id)
    if not r_vehicle_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_vehicle_data.error))
    vehicle_data = r_vehicle_data.data

    try:
        await deregister_vehicle_service(vehicle_data['id'])
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        "Vehicle Deregistered",
        f"**{vehicle_data['name']}** (#{vehicle_data['faction_vehicle_number']}) has been deregistered."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(deregister_vehicle)
