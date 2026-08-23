# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import get_pact, get_pact_members


@app_commands.command(name="view", description="View pact details and members")
@app_commands.describe(pact_id="Pact ID to view")
@require_access_level(0)
async def view_pact(interaction: discord.Interaction, pact_id: int):
    await interaction.response.defer()

    pact_data = await get_pact(pact_id)

    if not pact_data:
        await interaction.followup.send(embed=error_embed("Error", "Pact not found."))
        return

    members = await get_pact_members(pact_id)

    embed = discord.Embed(title=pact_data.name, description=f"**Type:** {pact_data.pact_type}\n**Pact ID:** {pact_id}", color=hex_to_int(pact_data.color))
    embed.add_field(name="Leader", value=pact_data.leader_name, inline=False)

    if members:
        embed.add_field(name=f"Members ({len(members)})", value="\n".join(f"• {m.faction_name}" for m in members), inline=False)
    else:
        embed.add_field(name="Members", value="No members yet", inline=False)

    if pact_data.date_created:
        embed.set_footer(text=f"Created: {pact_data.date_created.strftime('%Y-%m-%d')}")

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(view_pact)
