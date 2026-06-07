import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.building_service import get_building_by_name, list_faction_buildings
from services.validation_service import require_faction, require_world


@app_commands.command(name="list-buildings", description="View your faction's buildings")
@app_commands.describe(
    faction="Faction name",
    world="Optional: specific world name",
    building="Optional: specific building name to filter by"
)
@require_access_level(0)
async def list_buildings(
    interaction: discord.Interaction,
    faction: str,
    world: Optional[str] = None,
    building: Optional[str] = None
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    world_id = None
    world_display = None
    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error), ephemeral=True)
        world_id = r_world.data['id']
        world_display = r_world.data['name']

    building_id = None
    building_display = None
    if building:
        building_data = await get_building_by_name(building)
        if not building_data:
            await interaction.followup.send(embed=error_embed("Error", f"Building '{building}' not found."), ephemeral=True)
            return
        building_id = building_data['id']
        building_display = building_data['name']

    buildings = await list_faction_buildings(faction_data['id'], world_id, building_id)

    title_parts = [faction_data['display_name']]
    if building_display:
        title_parts.append(building_display)
    if world_display:
        title_parts.append(f"on {world_display}")
    title = " - ".join(title_parts) if len(title_parts) > 1 else f"{faction_data['display_name']} - All Buildings"
    if not building_display and not world_display:
        title += " - All Buildings"

    if not buildings:
        parts = []
        if building_display:
            parts.append(building_display)
        if world_display:
            parts.append(f"on {world_display}")
        location = f" ({', '.join(parts)})" if parts else ""
        await interaction.followup.send(embed=error_embed("No Buildings", f"No buildings found{location}."), ephemeral=True)
        return

    by_world: dict = {}
    total_weighted = 0
    for b in buildings:
        by_world.setdefault(b['world_name'], []).append(b)
        total_weighted += b['amount'] * b['level']

    embed = discord.Embed(title=title, description="Owned buildings by world", color=faction_color)
    for world_name, world_buildings in by_world.items():
        lines = []
        for b in world_buildings:
            level_str = f" L{b['level']}" if b['level'] > 1 else ""
            lines.append(f"{b['amount']:,}x {b['name']}{level_str}")
        embed.add_field(name=world_name, value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Total weighted buildings: {total_weighted:,}")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(list_buildings)
