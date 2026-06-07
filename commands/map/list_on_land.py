import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.map_service import get_world_factions
from services.validation_service import require_world


@app_commands.command(name="list-onland", description="View all factions on a world")
@app_commands.describe(world="World name")
@require_access_level(0)
async def list_on_land(interaction: discord.Interaction, world: str):
    await interaction.response.defer()

    r_world = await require_world(world)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error), ephemeral=True)
    world_data = r_world.data

    world_id = world_data['id']
    max_hexes = world_data['hex_count']

    factions = await get_world_factions(world_id)

    if not factions:
        await interaction.followup.send(embed=error_embed("No Claims", f"No factions have claimed hexes on {world_data['name']}."), ephemeral=True)
        return

    total_claimed = sum(f['territory'] for f in factions)
    embed = discord.Embed(
        title=f"Factions on {world_data['name']}",
        description=f"**Total Hexes:** {max_hexes:,}\n**Claimed:** {total_claimed:,}\n**Available:** {max_hexes - total_claimed:,}",
        color=hex_to_int(factions[0]['color'])
    )

    lines = [f"**{f['display_name']}:** {f['territory']:,} ({f['territory'] / max_hexes * 100:.1f}%)" for f in factions]
    for i in range(0, len(lines), 20):
        embed.add_field(name="Factions" if i == 0 else "...", value="\n".join(lines[i:i+20]), inline=False)

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(list_on_land)
