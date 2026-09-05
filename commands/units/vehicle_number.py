# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.vehicle_service import set_vehicle_number
from services.validation_service import require_faction, require_vehicle


@app_commands.command(name="number", description="Change a vehicle's faction number")
@app_commands.describe(
    faction="Faction owning the vehicle",
    vehicle_id="Vehicle ID or name",
    new_number="New faction number for the vehicle"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def vehicle_number(
    interaction: discord.Interaction,
    faction: str,
    vehicle_id: str,
    new_number: int
):
    await defer_response(interaction)

    if new_number < 1:
        await interaction.followup.send(embed=error_embed("Error", "Vehicle number must be at least 1."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    r_vehicle_data = await require_vehicle(vehicle_id, faction_data.id)
    if not r_vehicle_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_vehicle_data.error))
    vehicle_data = r_vehicle_data.data

    try:
        result = await set_vehicle_number(vehicle_data['id'], faction_data.id, new_number)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    old_number = result['old_number']
    vehicle_name = vehicle_data['name'] or f"Vehicle #{old_number}"

    if old_number == new_number:
        description = f"**{vehicle_name}** already uses number **#{new_number}**."
    elif result['swapped_vehicle_id'] is None:
        description = f"**{vehicle_name}** is now **#{new_number}** (was #{old_number})."
    else:
        other_name = result['swapped_name'] or f"Vehicle #{new_number}"
        description = (
            f"**{vehicle_name}** is now **#{new_number}** and **{other_name}** is now **#{old_number}**."
        )

    embed = success_embed("Vehicle Number Updated", description)
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
