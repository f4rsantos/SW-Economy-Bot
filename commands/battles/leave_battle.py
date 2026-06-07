import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.battle_service import leave_battle, get_battle
from services.validation_service import require_faction


@app_commands.command(name="leave-battle", description="Withdraw your fleets from a battle")
@app_commands.describe(battle_id="ID of the battle to leave", faction="Your faction name")
@require_access_level(0)
async def leave_battle_cmd(interaction: discord.Interaction, battle_id: int, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    if not await get_battle(battle_id):
        await interaction.followup.send(embed=error_embed("Error", "Battle not found."))
        return

    try:
        result = await leave_battle(battle_id, faction_data['id'])
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    fleet_names = result['fleet_names']
    if result['battle_ended']:
        embed = success_embed(
            title="Withdrew & Battle Ended",
            description=f"**{faction_data['display_name']}** withdrew {result['fleet_count']} fleet(s) from Battle #{battle_id}.\n**Fleets:** {', '.join(fleet_names)}\n\nAs the last participant, the battle has been automatically ended and deleted."
        )
    else:
        embed = success_embed(
            title="Withdrew from Battle",
            description=f"**{faction_data['display_name']}** withdrew {result['fleet_count']} fleet(s) from Battle #{battle_id}.\n**Fleets:** {', '.join(fleet_names)}\n\n**Remaining Fleets:** {result['remaining']}"
        )

    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(leave_battle_cmd)
