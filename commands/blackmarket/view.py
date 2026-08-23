# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.validation_service import require_faction
from services.blackmarket_service import get_alloys_held, buy_price_for_tier, ALLOY_HOLD_CAP, SELL_PAYOUT_BASE


@app_commands.command(name="view", description="Check the black market's current Alloy prices for your faction")
@app_commands.describe(faction="Your faction name")
@require_access_level(0)
async def view_cmd(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    held = await get_alloys_held(faction_id)
    can_buy = max(ALLOY_HOLD_CAP - held, 0)

    if can_buy > 0:
        next_price = buy_price_for_tier(held)
        buy_line = f"{handle_return(next_price)} each of CM, EL, CS"
    else:
        buy_line = "Refused, holdings at cap"

    sell_low = handle_return(round(SELL_PAYOUT_BASE * 0.9))
    sell_high = handle_return(SELL_PAYOUT_BASE)

    embed = discord.Embed(
        title=f"Black Market Alloys: {faction_data.display_name}",
        color=faction_color,
    )
    embed.add_field(name="Alloys Held", value=f"{held} / {ALLOY_HOLD_CAP}", inline=True)
    embed.add_field(name="Can Still Buy", value=str(can_buy), inline=True)
    embed.add_field(name="Next Buy Price", value=buy_line, inline=False)
    embed.add_field(name="Sell Payout", value=f"{sell_low} to {sell_high} each of CM, EL, CS", inline=False)
    await interaction.followup.send(embed=embed)
