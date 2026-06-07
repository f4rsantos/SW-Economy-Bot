import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.map_service import claim_hex as claim_hex_service
from services.validation_service import require_faction, require_world


@app_commands.command(name="claim", description="Claim hexes on a world")
@app_commands.describe(faction="Faction name", world="World name", hexes="Number of hexes to claim")
@require_access_level(0)
async def claim_hex(interaction: discord.Interaction, faction: str, world: str, hexes: int):
    await interaction.response.defer()

    r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error), ephemeral=True)
    faction_data = r_faction_data.data
    world_data = r_world.data

    if faction_data['is_company']:
        await interaction.followup.send(embed=error_embed("Error", "Companies cannot claim territory."), ephemeral=True)
        return

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    world_id = world_data['id']
    max_hexes = world_data['hex_count']

    if hexes <= 0:
        await interaction.followup.send(embed=error_embed("Error", "Must claim at least 1 hex."), ephemeral=True)
        return

    try:
        result = await claim_hex_service(faction_id, world_id, world_data['name'], max_hexes, hexes)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)), ephemeral=True)
        return

    embed = success_embed(title="Hexes Claimed", description=f"**{faction_data['display_name']}** claimed **{hexes}** hex(es) on **{world_data['name']}**.")
    embed.color = faction_color
    embed.add_field(name="Cost", value=f"{result['influence_cost']:,} Influence", inline=True)
    embed.add_field(name="Total Hexes", value=f"{result['new_total']:,}", inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(claim_hex)
