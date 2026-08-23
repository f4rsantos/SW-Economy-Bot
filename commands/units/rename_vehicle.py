# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.vehicle_service import rename_vehicle as rename_vehicle_service
from services.validation_service import require_faction, require_vehicle


@app_commands.command(name="rename", description="Rename a vehicle design or update designation")
@app_commands.describe(
    faction="Faction name or ID that owns the vehicle",
    vehicle_id="Vehicle display ID or name",
    new_name="New name for the vehicle (optional)",
    designation="New designation for the vehicle (optional, max 25 chars)"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def rename_vehicle(
    interaction: discord.Interaction,
    faction: str,
    vehicle_id: str,
    new_name: str = None,
    designation: str = None
):
    await defer_response(interaction)

    if not new_name and not designation:
        await interaction.followup.send(embed=error_embed("Error", "You must provide a new name or a new designation."))
        return

    if new_name and len(new_name) > 100:
        await interaction.followup.send(embed=error_embed("Error", "Vehicle name must be 100 characters or less."))
        return

    if designation and len(designation) > 25:
        await interaction.followup.send(embed=error_embed("Error", "Designation must be 25 characters or less."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    r_vehicle_data = await require_vehicle(vehicle_id, faction_data.id)
    if not r_vehicle_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_vehicle_data.error))
    vehicle_data = r_vehicle_data.data

    old_name = vehicle_data['name']
    old_designation = vehicle_data['designation']
    global_id = vehicle_data['id']
    changes = []

    if new_name and new_name != old_name:
        changes.append(f"Name: **{old_name}** → **{new_name}**")

    if designation is not None and designation != old_designation:
        changes.append(f"Designation: **{old_designation or '(None)'}** → **{designation or '(None)'}**")

    if not changes:
        await interaction.followup.send(embed=error_embed("Unchanged", "No changes were made to the vehicle."))
        return

    try:
        await rename_vehicle_service(
            global_id,
            faction_data.id,
            new_name if new_name and new_name != old_name else None,
            designation if designation is not None and designation != old_designation else None,
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed("Vehicle Updated", "\n".join(changes) + f"\n\nVehicle #{vehicle_data['faction_vehicle_number']}")
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(rename_vehicle)
