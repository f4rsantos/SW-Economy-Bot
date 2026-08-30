# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.battle_service import get_battle, get_fleet_for_battle, join_battle
from services.war_service import get_participant
from services.validation_service import require_faction


@app_commands.command(name="join", description="Join an existing battle with your fleet")
@app_commands.describe(battle_id="ID of the battle to join", fleet="Name or ID of your fleet", side="Which side to join (any label)", faction="Your faction name")
@require_access_level(0)
async def join_battle_cmd(interaction: discord.Interaction, battle_id: int, fleet: str, side: str, faction: str):
    await interaction.response.defer()

    side = side.strip().upper()
    if not side:
        await interaction.followup.send(embed=error_embed("Error", "Side cannot be empty."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    battle_data = await get_battle(battle_id)
    if not battle_data:
        await interaction.followup.send(embed=error_embed("Error", "Battle not found."))
        return

    fleet_data = await get_fleet_for_battle(fleet, faction_data.id)
    if not fleet_data:
        await interaction.followup.send(embed=error_embed("Error", "Fleet not found or you don't own this fleet."))
        return

    if fleet_data['position'] != battle_data.world_id:
        await interaction.followup.send(embed=error_embed("Error", f"Fleet must be at **{battle_data.world_name}** to join this battle. Currently at **{fleet_data['position_name']}**."))
        return

    if fleet_data['status_name'].lower() not in ['idle', 'in combat']:
        await interaction.followup.send(embed=error_embed("Error", f"Fleet must be idle or in combat to join battles. Current status: **{fleet_data['status_name']}**."))
        return

    if battle_data.war_id:
        participant = await get_participant(battle_data.war_id, faction_data.id)
        if participant and participant['side'] != side:
            await interaction.followup.send(embed=error_embed("Warning", f"Your faction is on side **{participant['side']}** in this war, but you're joining on side **{side}**. Proceeding anyway..."))

    try:
        result = await join_battle(battle_id, fleet_data['id'], side)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    stats_text = "\n".join(f"**Side {s.side}:** {s.fleet_count} fleet(s), {s.total_cs} CS" for s in result['stats'])
    fleet_name = fleet_data['name'] or f"Fleet #{fleet_data['id']}"
    embed = success_embed(
        "Joined Battle",
        f"**{fleet_name}** has joined Battle #{battle_id} at **{battle_data.world_name}**!\n**Side:** {side}\n\n**Current Battle Status:**\n{stats_text}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(join_battle_cmd)
