# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.faction_service import set_leader as set_leader_service
from services.validation_service import require_faction


@app_commands.command(name="set-leader", description="Set the leader of a faction (Admin)")
@app_commands.describe(faction="Name or ID of the faction", user="User to set as faction leader")
@require_access_level(5)
async def set_leader(interaction: discord.Interaction, faction: str, user: discord.User):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    old_leader_id = faction_data.leader_id
    old_leader_mention = f"<@{old_leader_id}>" if old_leader_id else "None"

    try:
        await set_leader_service(faction_data.id, user.id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="Faction Leader Updated", description=f"**{faction_data.display_name}** leadership has been updated")
    embed.add_field(name="Previous Leader", value=old_leader_mention, inline=True)
    embed.add_field(name="New Leader", value=user.mention, inline=True)
    embed.add_field(name="Updated By", value=interaction.user.mention, inline=False)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
