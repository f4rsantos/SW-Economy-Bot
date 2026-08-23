# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.blockade_service import (
    get_blockade, get_blockade_targets, get_fleet_in_blockade,
    get_my_fleet_in_blockade, end_blockade, count_blockade_fleets
)
from services.user_service import get_user_access_level
from services.validation_service import require_faction


@app_commands.command(name="end", description="End a blockade (remove your fleet or end entire blockade)")
@app_commands.describe(
    blockade_id="ID of the blockade to end",
    faction="Your faction name",
    remove_fleet="Fleet to remove from blockade (leave empty to end entire blockade)"
)
@require_access_level(0)
async def end_blockade_cmd(interaction: discord.Interaction, blockade_id: int, faction: str, remove_fleet: str = None):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    blockade_data = await get_blockade(blockade_id)
    if not blockade_data:
        await interaction.followup.send(embed=error_embed("Error", "Blockade not found."))
        return

    target_names = await get_blockade_targets(blockade_id)

    if remove_fleet:
        fleet_data = await get_fleet_in_blockade(blockade_id, faction_data.id, remove_fleet)
        if not fleet_data:
            await interaction.followup.send(embed=error_embed("Error", "Fleet not found in this blockade or you don't own this fleet."))
            return

        try:
            await end_blockade(blockade_id, fleet_data['id'])
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

        fleet_name = fleet_data['name'] or f"Fleet #{fleet_data['id']}"
        remaining = await count_blockade_fleets(blockade_id)

        if not remaining:
            embed = success_embed(
                "Blockade Ended & Deleted",
                f"**{fleet_name}** was the last fleet in blockade #{blockade_id}.\n"
                f"The blockade of **{blockade_data.world_name}** has been removed.\n"
                f"**Previously blockading:** {', '.join(target_names)}"
            )
        else:
            embed = success_embed(
                "Fleet Removed from Blockade",
                f"**{fleet_name}** has been removed from blockade #{blockade_id}.\n"
                f"**{remaining}** fleet(s) still participating."
            )
        embed.color = faction_color
    else:
        my_fleet = await get_my_fleet_in_blockade(blockade_id, faction_data.id)
        if not my_fleet:
            admin_level = await get_user_access_level(interaction.user.id)
            if not admin_level or admin_level < 4:
                await interaction.followup.send(embed=error_embed("Error", "You must have a fleet in this blockade to end it."))
                return

        fleet_count = await count_blockade_fleets(blockade_id)

        try:
            await end_blockade(blockade_id, None)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

        embed = success_embed(
            "Blockade Ended",
            f"Blockade #{blockade_id} of **{blockade_data.world_name}** has been ended.\n"
            f"**{fleet_count}** fleet(s) released.\n"
            f"**Previously blockading:** {', '.join(target_names)}"
        )
        embed.color = faction_color

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(end_blockade_cmd)
