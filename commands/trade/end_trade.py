# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.trade_service import end_trade as end_trade_service


@app_commands.command(name="end", description="End recurring trade")
@app_commands.describe(trade_id="Trade ID to end")
@require_access_level(0)
async def end_trade(interaction: discord.Interaction, trade_id: int):
    await interaction.response.defer()

    try:
        trade_data = await end_trade_service(trade_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        "Trade Deal Ended",
        f"**{trade_data.sender_name}** → **{trade_data.receiver_name}**\n\n"
        f"**Resource:** {trade_data.resource_name}\n"
        f"**Amount:** {trade_data.amount:,} per cycle\n\n"
        f"This trade will no longer execute during income."
    )
    embed.color = hex_to_int(trade_data.sender_color)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(end_trade)
