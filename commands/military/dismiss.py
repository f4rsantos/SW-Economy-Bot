# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_currency
from services.fleet_service import dismiss_infantry_from_unit
from services.validation_service import require_faction, require_unit


@app_commands.command(name="dismiss", description="Dismiss infantry from a unit")
@app_commands.describe(
    faction="Faction name",
    unit="Unit ID or name to dismiss infantry from",
    amount="Amount of infantry to dismiss (supports k/m/b/t multipliers)",
    name="Role name for display (default: soldiers)"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def dismiss(
    interaction: discord.Interaction,
    faction: str,
    unit: str,
    amount: str,
    name: str = "soldiers"
):
    await defer_response(interaction)

    try:
        personnel_amount = int(handle_currency(amount))
        if personnel_amount < 1:
            raise ValueError
    except Exception:
        await interaction.followup.send(embed=error_embed("Error", "Invalid amount."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)
    display_name = faction_data.display_name

    r_unit_data = await require_unit(unit, faction_id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    unit_label = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"

    try:
        await dismiss_infantry_from_unit(unit_data['id'], faction_id, personnel_amount)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = discord.Embed(
        title=f"Military: {display_name}",
        description=f"{display_name} has dismissed **{personnel_amount:,} {name}** from **{unit_label}**.\n\nThey return to civilian life immediately.",
        color=faction_color
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
