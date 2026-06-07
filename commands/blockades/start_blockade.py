import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.blockade_service import get_fleet_for_blockade, start_blockade
from services.validation_service import require_faction, require_world


@app_commands.command(name="start", description="Start a blockade on a world targeting specific faction(s)")
@app_commands.describe(
    fleet="Name or ID of your fleet to participate in blockade",
    world="World to blockade",
    target_faction="Faction(s) to blockade (comma-separated if multiple)",
    faction="Your faction name"
)
@require_access_level(0)
async def start_blockade_cmd(interaction: discord.Interaction, fleet: str, world: str, target_faction: str, faction: str):
    await interaction.response.defer()

    r_faction_data, r_world_data = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    if not r_world_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_world_data.error))
    faction_data = r_faction_data.data
    world_data = r_world_data.data

    fleet_data = await get_fleet_for_blockade(fleet, faction_data['id'])
    if not fleet_data:
        await interaction.followup.send(embed=error_embed("Error", "Fleet not found or you don't own this fleet."))
        return

    if fleet_data['position'] != world_data['id']:
        await interaction.followup.send(embed=error_embed("Error", f"Fleet must be at **{world_data['name']}** to blockade it. Currently at **{fleet_data['position_name']}**."))
        return

    target_faction_ids = []
    target_faction_names = []
    for target in [t.strip() for t in target_faction.split(',')]:
        r_target_data = await require_faction(target)
        if not r_target_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_target_data.error))
        target_data = r_target_data.data
        if target_data['id'] == faction_data['id']:
            await interaction.followup.send(embed=error_embed("Error", "You cannot blockade your own faction."))
            return
        target_faction_ids.append(target_data['id'])
        target_faction_names.append(target_data['display_name'])

    try:
        blockade_id = await start_blockade(fleet_data['id'], world_data['id'], target_faction_ids)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    fleet_name = fleet_data['name'] or f"Fleet #{fleet_data['id']}"
    embed = success_embed(
        "Blockade Started",
        f"**{fleet_name}** has started a blockade of **{world_data['name']}**\n"
        f"**Blockade ID:** {blockade_id}\n"
        f"**Blockading:** {', '.join(target_faction_names)}\n\n"
        f"Blockaded factions cannot transfer resources to or from this world."
    )
    embed.color = hex_to_int(faction_data['color'])
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(start_blockade_cmd)
