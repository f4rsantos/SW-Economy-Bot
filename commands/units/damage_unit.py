# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.battle_service import damage_fleet, get_battle, get_fleet_side_in_battle
from services.validation_service import require_faction, require_unit
from utils.autocomplete import faction_autocomplete


@app_commands.command(name="damage", description="Deal damage to a unit (reduces health)")
@app_commands.describe(
    faction="Faction owning the unit",
    unit="Unit number (faction-specific) or name",
    damage="Damage amount (percentage points, 1-100)",
    battle_id="Optional: Battle ID if this damage is part of a battle"
)
@app_commands.autocomplete(faction=faction_autocomplete)
@require_access_level(0)
async def damage_unit_cmd(interaction: discord.Interaction, faction: str, unit: str, damage: int, battle_id: int = None):
    await interaction.response.defer()

    if damage < 1 or damage > 100:
        await interaction.followup.send(embed=error_embed("Error", "Damage must be between 1 and 100."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    r_unit_data = await require_unit(unit, faction_data.id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    if battle_id:
        battle_data = await get_battle(battle_id)
        if not battle_data:
            await interaction.followup.send(embed=error_embed("Error", "Battle not found."))
            return
        unit_side = await get_fleet_side_in_battle(battle_id, unit_data['id'])
        if not unit_side:
            await interaction.followup.send(embed=error_embed("Error", "Unit is not participating in this battle."))
            return

    try:
        await damage_fleet(unit_data['id'], damage)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    new_health = max(0, unit_data['health'] - damage)
    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    status_msg = ""
    if new_health == 0:
        status_msg = "\n**Unit destroyed! Status changed to Debris.**"
    elif new_health <= 10:
        status_msg = "\n**Unit is critically damaged!**"

    battle_info = f"\n**Battle:** #{battle_id}" if battle_id else ""
    embed = discord.Embed(
        title="Unit Damaged",
        description=f"**{unit_name}** ({faction_data.display_name})\n"
                    f"**Damage:** {damage}% HP{battle_info}\n"
                    f"**Health:** {unit_data['health']}% → {new_health}%{status_msg}",
        color=hex_to_int(faction_data.color)
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(damage_unit_cmd)
