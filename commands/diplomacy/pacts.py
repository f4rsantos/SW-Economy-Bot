# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import get_faction_pacts
from services.validation_service import require_faction


@app_commands.command(name="list", description="View faction's pacts")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def pacts(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    pacts_data = await get_faction_pacts(faction_id)
    led_pacts = pacts_data['led']
    member_pacts = pacts_data['member']

    if not led_pacts and not member_pacts:
        await interaction.followup.send(embed=error_embed("No Pacts", f"{faction_data.display_name} is not part of any pacts."))
        return

    embed = discord.Embed(title=f"Pacts: {faction_data.display_name}", color=faction_color)

    if led_pacts:
        lines = []
        for p in led_pacts:
            lines.append(f"**{p.name}** (ID: {p.id})")
            lines.append(f"  Type: {p.pact_type} | Members: {p.member_count}")
        embed.add_field(name="Leader Of", value="\n".join(lines), inline=False)

    if member_pacts:
        lines = []
        for p in member_pacts:
            lines.append(f"**{p.name}** (ID: {p.id})")
            lines.append(f"  Type: {p.pact_type} | Leader: {p.leader_name}")
        embed.add_field(name="Member Of", value="\n".join(lines), inline=False)

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(pacts)
