# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.validation_service import require_faction
from services.blackmarket_service import buy_alloys, ALLOY_HOLD_CAP


@app_commands.command(name="buy", description="Buy Alloys from the pirates. CM, EL and CS, no questions asked")
@app_commands.describe(
    faction="Your faction name",
    quantity="Number of Alloys to buy (default 1)"
)
@require_access_level(0)
async def buy_cmd(interaction: discord.Interaction, faction: str, quantity: int = 1):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    if quantity < 1:
        await interaction.followup.send(embed=error_embed("Error", "Quantity must be at least 1."))
        return

    try:
        result = await buy_alloys(faction_id, quantity)
    except ValueError as e:
        msg = str(e)
        if 'CAP_REACHED' in msg or 'RESOURCE_INSUFFICIENT' in msg or 'RESOURCE_NOT_FOUND' in msg:
            await interaction.followup.send(embed=error_embed("Error", msg.split(':', 1)[1].strip()))
        else:
            await interaction.followup.send(embed=error_embed("Error", msg))
        return

    cost_str = ", ".join(f"{handle_return(amount)} {res}" for res, amount in result['costs'].items())
    embed = success_embed(
        title="Alloys Purchased",
        description=(
            f"**{faction_data.display_name}** bought {quantity} Alloys from the black market for {cost_str}.\n"
            f"Holdings: {result['held_before']} -> {result['held_after']} (cap {ALLOY_HOLD_CAP})"
        ),
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)
