import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import set_fleet_status
from services.faction_service import search_faction_names
from services.validation_service import require_faction, require_unit


async def faction_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_faction_names(current)
    return [app_commands.Choice(name=name, value=name) for name in names]


@app_commands.command(name="status", description="Change unit status")
@app_commands.describe(
    faction="Faction owning the unit",
    unit_id="Unit number (faction-specific) or name",
    status="New status"
)
@app_commands.choices(status=[
    app_commands.Choice(name="Idle",    value="idle"),
    app_commands.Choice(name="Defense", value="defence"),
    app_commands.Choice(name="Patrol",  value="patrol"),
])
@require_access_level(0)
async def unit_status_command(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    status: str
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    r_unit_data = await require_unit(unit_id, faction_data['id'])
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    current_status = unit_data['status_name'].lower()
    if current_status == 'debris':
        await interaction.followup.send(embed=error_embed("Error", "Debris units cannot change status. Repair them first."))
        return

    try:
        await set_fleet_status(unit_data['id'], status)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    embed = success_embed(
        "Unit Status Changed",
        f"**{unit_name}**\n\n{unit_data['status_name']} → {status.title()}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    unit_status_command.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(unit_status_command)
