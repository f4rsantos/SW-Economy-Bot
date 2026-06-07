import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.building_service import buy_building as buy_building_service
from services.validation_service import require_faction, require_world


@app_commands.command(name="buy-building", description="Buy buildings on a world")
@app_commands.describe(
    faction="Faction name",
    building_id="Building type ID",
    world="World name",
    amount="Number of buildings to construct",
    level="Building level (1-10)"
)
@require_access_level(0)
async def buy_building(
    interaction: discord.Interaction,
    faction: str,
    building_id: int,
    world: str,
    amount: int = 1,
    level: int = 1
):
    await interaction.response.defer()

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."), ephemeral=True)
        return

    if level < 1 or level > 10:
        await interaction.followup.send(embed=error_embed("Error", "Level must be between 1 and 10."), ephemeral=True)
        return

    r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error), ephemeral=True)
    faction_data = r_faction_data.data
    world_data = r_world.data

    faction_id = faction_data['id']
    is_company = faction_data['is_company']
    faction_color = hex_to_int(faction_data['color'])

    world_id = world_data['id']

    try:
        result = await buy_building_service(faction_id, world_id, building_id, amount, level, is_company)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)), ephemeral=True)
        return

    cost_str = ", ".join(f"{handle_return(cost)} {res}" for res, cost in result['costs'].items())
    embed = success_embed(
        "Buildings Constructed",
        f"**{faction_data['display_name']}** has built {amount} level {level} {result['building_name']} on **{world_data['name']}** for {cost_str}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(buy_building)
