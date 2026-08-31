# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import set_fleet_number
from services.validation_service import require_faction, require_unit


@app_commands.command(name="number", description="Change a unit's faction number")
@app_commands.describe(
    faction="Faction owning the unit",
    unit_id="Unit ID or name",
    new_number="New faction number for the unit"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def unit_number(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    new_number: int
):
    await defer_response(interaction)

    if new_number < 1:
        await interaction.followup.send(embed=error_embed("Error", "Unit number must be at least 1."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    r_unit_data = await require_unit(unit_id, faction_data.id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    try:
        result = await set_fleet_number(unit_data['id'], faction_data.id, new_number)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    old_number = result['old_number']
    unit_name = unit_data['name'] or f"Unit #{old_number}"

    if old_number == new_number:
        description = f"**{unit_name}** already uses number **#{new_number}**."
    elif result['swapped_fleet_id'] is None:
        description = f"**{unit_name}** is now **#{new_number}** (was #{old_number})."
    else:
        other_name = result['swapped_name'] or f"Unit #{new_number}"
        description = (
            f"**{unit_name}** is now **#{new_number}** and **{other_name}** is now **#{old_number}**."
        )

    embed = success_embed("Unit Number Updated", description)
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
