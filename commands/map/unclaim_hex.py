import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.map_service import unclaim_hex as unclaim_hex_service
from services.validation_service import require_faction, require_world


@app_commands.command(name="unclaim", description="Unclaim hexes from a world")
@app_commands.describe(faction="Faction name", world="World name", hexes="Number of hexes to unclaim")
@require_access_level(0)
async def unclaim_hex(interaction: discord.Interaction, faction: str, world: str, hexes: int):
    await interaction.response.defer()

    r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    faction_data = r_faction_data.data
    world_data = r_world.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    world_id = world_data['id']

    if hexes <= 0:
        await interaction.followup.send(embed=error_embed("Error", "Must unclaim at least 1 hex."))
        return

    try:
        result = await unclaim_hex_service(faction_id, world_id, world_data['name'], hexes)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="Hexes Unclaimed", description=f"**{faction_data['display_name']}** unclaimed **{hexes}** hex(es) from **{world_data['name']}**.")
    embed.color = faction_color
    embed.add_field(name="Remaining Hexes", value=f"{result['remaining_hexes']:,}", inline=True)
    embed.add_field(name="Buildings", value=f"{result['total_buildings']:,}", inline=True)
    embed.set_footer(text="No influence refund given")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(unclaim_hex)
