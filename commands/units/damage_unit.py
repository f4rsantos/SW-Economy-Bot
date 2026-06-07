import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.battle_service import damage_fleet, get_battle, get_fleet_side_in_battle
from services.fleet_service import get_fleet_for_damage


@app_commands.command(name="damage", description="Deal damage to a unit (reduces health)")
@app_commands.describe(
    unit="Name or ID of unit to damage",
    damage="Damage amount (percentage points, 1-100)",
    faction="Optional: Faction name to help identify the unit",
    battle_id="Optional: Battle ID if this damage is part of a battle"
)
@require_access_level(0)
async def damage_unit_cmd(interaction: discord.Interaction, unit: str, damage: int, faction: str = None, battle_id: int = None):
    await interaction.response.defer()

    if damage < 1 or damage > 100:
        await interaction.followup.send(embed=error_embed("Error", "Damage must be between 1 and 100."))
        return

    unit_data = await get_fleet_for_damage(unit, faction)
    if not unit_data:
        msg = f"Unit '{unit}' not found" + (f" in faction '{faction}'" if faction else "")
        await interaction.followup.send(embed=error_embed("Error", msg + "."))
        return

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
    unit_name = unit_data['name'] or f"Unit #{unit_data['id']}"
    status_msg = ""
    if new_health == 0:
        status_msg = "\n**Unit destroyed! Status changed to Debris.**"
    elif new_health <= 10:
        status_msg = "\n**Unit is critically damaged!**"

    battle_info = f"\n**Battle:** #{battle_id}" if battle_id else ""
    embed = discord.Embed(
        title="Unit Damaged",
        description=f"**{unit_name}** ({unit_data['faction_name']})\n"
                    f"**Damage:** {damage}% HP{battle_info}\n"
                    f"**Health:** {unit_data['health']}% → {new_health}%{status_msg}",
        color=hex_to_int(unit_data['faction_color'])
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(damage_unit_cmd)
