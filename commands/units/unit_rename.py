import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import rename_fleet
from services.faction_service import search_faction_names
from services.validation_service import require_faction, require_unit


async def faction_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_faction_names(current)
    return [app_commands.Choice(name=name, value=name) for name in names]


@app_commands.command(name="rename", description="Rename a unit")
@app_commands.describe(
    faction="Faction owning the unit",
    unit_id="Unit ID or name",
    new_name="New name for the unit"
)
@require_access_level(0)
async def unit_rename(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    new_name: str
):
    await interaction.response.defer()

    if len(new_name) > 100:
        await interaction.followup.send(embed=error_embed("Error", "Unit name must be 100 characters or less."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    r_unit_data = await require_unit(unit_id, faction_data['id'])
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    old_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    await rename_fleet(unit_data['id'], new_name)

    embed = success_embed("Unit Renamed", f"**{old_name}** → **{new_name}**")
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    unit_rename.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(unit_rename)
