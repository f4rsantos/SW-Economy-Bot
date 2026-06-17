import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.battle_service import get_fleet_for_battle, create_standalone_war, start_battle
from services.war_service import get_war, get_participant
from services.validation_service import require_faction, require_world


@app_commands.command(name="start", description="Start a battle with your fleet")
@app_commands.describe(
    fleet="Name or ID of your fleet",
    side="Which side of the battle (any label)",
    faction="Your faction name",
    world="World where battle takes place (defaults to fleet's current position)",
    war_id="Optional: War ID if this battle is part of a war"
)
@require_access_level(0)
async def start_battle_cmd(
    interaction: discord.Interaction,
    fleet: str,
    side: str,
    faction: str,
    world: Optional[str] = None,
    war_id: Optional[int] = None
):
    await interaction.response.defer()

    side = side.strip().upper()
    if not side:
        await interaction.followup.send(embed=error_embed("Error", "Side cannot be empty."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    fleet_data = await get_fleet_for_battle(fleet, faction_data['id'])
    if not fleet_data:
        await interaction.followup.send(embed=error_embed("Error", "Fleet not found or you don't own this fleet."))
        return

    if fleet_data['status_name'].lower() != 'idle':
        await interaction.followup.send(embed=error_embed("Error", f"Fleet must be idle to start a battle. Current status: **{fleet_data['status_name']}**."))
        return

    if world:
        r_world_data = await require_world(world)
        if not r_world_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_world_data.error))
        world_data = r_world_data.data
        if fleet_data['position'] != world_data['id']:
            await interaction.followup.send(embed=error_embed("Error", f"Fleet must be at **{world_data['name']}** to battle there. Currently at **{fleet_data['position_name']}**."))
            return
        battle_world_id = world_data['id']
        battle_world_name = world_data['name']
    else:
        battle_world_id = fleet_data['position']
        battle_world_name = fleet_data['position_name']

    if war_id:
        war_data = await get_war(war_id)
        if not war_data:
            await interaction.followup.send(embed=error_embed("Error", "War not found."))
            return
        participant = await get_participant(war_id, faction_data['id'])
        if not participant:
            await interaction.followup.send(embed=error_embed("Error", "Your faction is not a participant in this war."))
            return
        if participant['side'] != side:
            await interaction.followup.send(embed=error_embed("Warning", f"Your faction is on side **{participant['side']}** in this war, but you're joining battle on side **{side}**. Proceeding anyway..."))
    else:
        war_id = await create_standalone_war(battle_world_name, faction_data['id'], side)

    if fleet_data['total_cs'] == 0:
        await interaction.followup.send(embed=error_embed("Warning", "Fleet has 0 CS and cannot contribute to battle. Proceeding anyway..."))

    try:
        battle_id = await start_battle(war_id, fleet_data['id'], side, battle_world_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    fleet_name = fleet_data['name'] or f"Fleet #{fleet_data['id']}"
    embed = success_embed(
        "Battle Started",
        f"**{fleet_name}** has started a battle at **{battle_world_name}**!\n"
        f"**Battle ID:** {battle_id}\n**War ID:** {war_id}\n**Side:** {side}\n"
        f"Other fleets can join with `/join-battle {battle_id}`"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(start_battle_cmd)
