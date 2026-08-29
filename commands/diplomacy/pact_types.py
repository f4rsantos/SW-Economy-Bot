# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from services.pact_service import get_all_pact_types, INTELLIGENCE_SHARING_PACT_TYPE
from repositories.income_repo import (
    INTELLIGENCE_SHARING_INFLUENCE_SINGLE_MODE,
    INTELLIGENCE_SHARING_INFLUENCE_BOTH_MODES,
)


@app_commands.command(name="types", description="View available pact types and their influence costs")
@require_access_level(0)
async def pact_types(interaction: discord.Interaction):
    await interaction.response.defer()

    pact_types_data = await get_all_pact_types()
    if not pact_types_data:
        await interaction.followup.send(embed=error_embed("No Data", "No pact types found in database."))
        return

    embed = discord.Embed(title="Pact Types", description="Available diplomatic agreements and their influence costs per member", color=0x3498db)
    for pact in pact_types_data:
        description = pact.description or "No description available"
        if pact.name == INTELLIGENCE_SHARING_PACT_TYPE:
            cost_line = (
                f"**Cost:** {INTELLIGENCE_SHARING_INFLUENCE_SINGLE_MODE} Influence per world shared, per other member for one mode, "
                f"{INTELLIGENCE_SHARING_INFLUENCE_BOTH_MODES} for both modes"
            )
        else:
            cost = pact.influence_cost or 0
            cost_line = f"**Cost:** {cost} Influence per member"
        embed.add_field(name=f"{pact.name} (ID: {pact.id})", value=f"{cost_line}\n{description}", inline=False)
    embed.set_footer(text="All members pay the listed influence cost")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(pact_types)
