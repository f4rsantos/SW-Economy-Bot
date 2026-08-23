# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import get_fleet_by_identifier, set_unit_type
from services.validation_service import require_faction


@app_commands.command(name="set-type", description="Set the type of a unit (Space, Ground, Air, Naval)")
@app_commands.describe(
    faction="Faction name",
    unit="Unit name or number",
    unit_type="Unit type",
)
@app_commands.choices(unit_type=[
    app_commands.Choice(name="Space",  value="Space"),
    app_commands.Choice(name="Ground", value="Ground"),
    app_commands.Choice(name="Air",    value="Air"),
    app_commands.Choice(name="Naval",  value="Naval"),
])
@require_access_level(0)
async def unit_set_type(
    interaction: discord.Interaction,
    faction: str,
    unit: str,
    unit_type: str,
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    unit_data = await get_fleet_by_identifier(unit, faction_data.id)
    if not unit_data:
        await interaction.followup.send(embed=error_embed("Error", f"Unit '{unit}' not found for {faction_data.display_name}."))
        return

    try:
        await set_unit_type(unit_data.id, unit_type)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_label = unit_data.name or f"Unit #{unit_data.faction_fleet_number}"
    embed = success_embed(
        "Unit Type Set",
        f"**{unit_label}** is now classified as **{unit_type}**.",
    )
    embed.color = hex_to_int(faction_data.color)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(unit_set_type)
