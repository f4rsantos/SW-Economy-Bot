# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.battle_service import get_battle, get_my_fleet_in_battle, end_battle
from services.validation_service import require_faction


@app_commands.command(name="end", description="End a battle and release all fleets")
@app_commands.describe(battle_id="ID of the battle to end", faction="Your faction name")
@require_access_level(0)
async def end_battle_cmd(interaction: discord.Interaction, battle_id: int, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    battle_data = await get_battle(battle_id)
    if not battle_data:
        await interaction.followup.send(embed=error_embed("Error", "Battle not found."))
        return

    if not await get_my_fleet_in_battle(battle_id, faction_data.id):
        await interaction.followup.send(embed=error_embed("Error", "You must have a fleet in this battle to end it."))
        return

    try:
        result = await end_battle(battle_id, faction_data.id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    stats_text = "\n".join(
        f"**Side {s.side}:** {s.fleet_count} fleet(s), {int(s.total_cs)} CS, {int(s.avg_health)}% avg health"
        for s in result['stats']
    )
    duration = f"\n**Duration:** <t:{int(battle_data.date_start.timestamp())}:R>" if battle_data.date_start else ""
    war_info = f"\n**War ID:** {battle_data.war_id}" if battle_data.war_id else ""

    embed = success_embed(
        "Battle Ended & Deleted",
        f"Battle #{battle_id} at **{battle_data.world_name}** has been ended and removed from records.{war_info}{duration}\n"
        f"**{result['fleet_count']}** fleet(s) released.\n\n**Final Status:**\n{stats_text}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(end_battle_cmd)
