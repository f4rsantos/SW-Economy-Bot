import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.building_service import destroy_building as destroy_building_service
from services.validation_service import require_faction, require_world


@app_commands.command(name="destroy-building", description="Destroy buildings (no refund)")
@app_commands.describe(
    faction="Faction name",
    building_id="Building type ID",
    world="World name",
    amount="Number of buildings to destroy",
    level="Building level (1-10)"
)
@require_access_level(0)
async def destroy_building(
    interaction: discord.Interaction,
    faction: str,
    building_id: int,
    world: str,
    amount: int = 1,
    level: int = 1
):
    await interaction.response.defer()

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    if level < 1 or level > 10:
        await interaction.followup.send(embed=error_embed("Error", "Level must be between 1 and 10."))
        return

    r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    faction_data = r_faction_data.data
    world_data = r_world.data

    faction_color = hex_to_int(faction_data['color'])

    try:
        result = await destroy_building_service(faction_data['id'], world_data['id'], building_id, amount, level)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        "Buildings Destroyed",
        f"**{faction_data['display_name']}** has destroyed {amount} level {level} {result['building_name']} on **{world_data['name']}** (no refund)"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(destroy_building)
