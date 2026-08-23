# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import get_faction_by_id, hex_to_int
from services.user_service import get_user_access_level
from services.faction_service import rename_faction as rename_faction_service
from services.validation_service import require_faction_by_id


async def _can_manage_faction(user_id: int, faction_id: int) -> bool:
    if await get_user_access_level(user_id) >= 4:
        return True
    faction = await get_faction_by_id(faction_id)
    return faction is not None and faction.leader_id == user_id


@app_commands.command(name="rename", description="Rename a faction")
@app_commands.describe(
    faction_id="The ID of the faction to rename",
    new_name="The new name for the faction (lowercase, English letters only)"
)
@require_access_level(0)
async def rename_faction(interaction: discord.Interaction, faction_id: int, new_name: str):
    await interaction.response.defer()

    if not await _can_manage_faction(interaction.user.id, faction_id):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to rename this faction."))
        return

    new_name = new_name.strip().lower()
    if not new_name.replace(" ", "").isalpha() or not new_name.isascii():
        await interaction.followup.send(embed=error_embed("Invalid Name", "Faction name must contain only English letters (a-z). No numbers or special characters."))
        return

    r_old_faction = await require_faction_by_id(faction_id)
    if not r_old_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_old_faction.error))
    old_faction = r_old_faction.data

    try:
        await rename_faction_service(faction_id, new_name)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Name Taken", str(e)))
        return

    embed = success_embed(title="Faction Renamed", description=f"**{old_faction.display_name}** has been renamed to **{new_name}**")
    embed.color = hex_to_int(old_faction.color)
    embed.add_field(name="Old Name", value=old_faction.name, inline=True)
    embed.add_field(name="New Name", value=new_name, inline=True)
    embed.add_field(name="Renamed By", value=interaction.user.mention, inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
