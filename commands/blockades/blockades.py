import asyncio
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.blockade_service import get_blockades
from services.validation_service import require_faction, require_world


@app_commands.command(name="list", description="View all blockades by faction or world")
@app_commands.describe(faction="Filter by blockading faction or target faction", world="Filter by world being blockaded")
@require_access_level(0)
async def blockades(interaction: discord.Interaction, faction: Optional[str] = None, world: Optional[str] = None):
    await interaction.response.defer()

    faction_data = None
    world_data = None
    faction_color = discord.Color.red()

    if faction and world:
        r_faction_data, r_world_data = await asyncio.gather(require_faction(faction), require_world(world))
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        if not r_world_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_world_data.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data['color'])
        world_data = r_world_data.data
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data['color'])
    elif world:
        r_world_data = await require_world(world)
        if not r_world_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_world_data.error))
        world_data = r_world_data.data

    faction_id = faction_data['id'] if faction_data else None
    world_id = world_data['id'] if world_data else None

    blockades_data = await get_blockades(faction_id=faction_id, world_id=world_id)

    if faction_data and world_data:
        title = f"Blockades at {world_data['name']} involving {faction_data['display_name']}"
    elif faction_data:
        title = f"Blockades involving {faction_data['display_name']}"
    elif world_data:
        title = f"Blockades at {world_data['name']}"
    else:
        title = "All Active Blockades"

    if not blockades_data:
        await interaction.followup.send(embed=success_embed("Blockades", "No active blockades found."))
        return

    embed = discord.Embed(title=title, description=f"{len(blockades_data)} active blockade(s)", color=faction_color)
    for blockade in blockades_data:
        targets = ', '.join(blockade['targets']) if blockade['targets'] else 'None'
        blockaders = ', '.join(set(blockade['blockading_factions'])) if blockade['blockading_factions'] else 'None'
        embed.add_field(
            name=f"Blockade #{blockade['id']} - {blockade['world_name']}",
            value=f"**Blockading:** {blockaders}\n**Targets:** {targets}\n**Fleets:** {blockade['fleet_count']}\n**Started:** <t:{int(blockade['date_start'].timestamp())}:R>",
            inline=False
        )

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(blockades)
