import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import create_fleet
from services.validation_service import require_faction, require_world
from utils.autocomplete import faction_autocomplete


@app_commands.command(name="create", description="Create a new unit")
@app_commands.describe(
    faction="Faction name",
    world="World where unit will be created",
    name="Unit name (optional)"
)
@require_access_level(0)
async def unit_create(
    interaction: discord.Interaction,
    faction: str,
    world: str,
    name: str = None
):
    await interaction.response.defer()

    r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    faction_data = r_faction_data.data
    world_data = r_world.data

    faction_color = hex_to_int(faction_data['color'])

    try:
        result = await create_fleet(faction_data['id'], name, world_data['id'])
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_name = name if name else f"Unit #{result['faction_fleet_number']}"
    embed = success_embed(
        "Unit Created",
        f"**{unit_name}** (ID: #{result['faction_fleet_number']})\n"
        f"**Faction:** {faction_data['display_name']}\n"
        f"**Location:** {world_data['name']}\n"
        f"**Status:** Idle"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    unit_create.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(unit_create)
