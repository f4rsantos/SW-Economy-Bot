import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_currency
from services.fleet_service import transfer_infantry_between_units
from services.validation_service import require_faction, require_unit


@app_commands.command(name="transfer", description="Move infantry between units")
@app_commands.describe(
    faction="Faction name",
    from_unit="Source unit ID or name",
    to_unit="Destination unit ID or name",
    amount="Amount of infantry to transfer (supports k/m/b/t multipliers)"
)
@require_access_level(0)
async def transfer(
    interaction: discord.Interaction,
    faction: str,
    from_unit: str,
    to_unit: str,
    amount: str
):
    await interaction.response.defer()

    try:
        transfer_amount = int(handle_currency(amount))
        if transfer_amount < 1:
            raise ValueError
    except Exception:
        await interaction.followup.send(embed=error_embed("Error", "Invalid amount."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    r_from_unit_data, r_to_unit_data = await asyncio.gather(
        require_unit(from_unit, faction_id),
        require_unit(to_unit, faction_id)
    )
    if not r_from_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_from_unit_data.error))
    from_unit_data = r_from_unit_data.data
    if not r_to_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_to_unit_data.error))
    to_unit_data = r_to_unit_data.data

    if from_unit_data['id'] == to_unit_data['id']:
        await interaction.followup.send(embed=error_embed("Error", "Cannot transfer infantry to the same unit."))
        return

    try:
        await transfer_infantry_between_units(from_unit_data['id'], to_unit_data['id'], faction_id, transfer_amount)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    from_label = from_unit_data['name'] or f"Unit #{from_unit_data['faction_fleet_number']}"
    to_label = to_unit_data['name'] or f"Unit #{to_unit_data['faction_fleet_number']}"
    embed = discord.Embed(
        title=f"{faction_data['display_name']}'s Military",
        description=f"Transferred **{transfer_amount:,} infantry**\n\nFrom: **{from_label}**\nTo: **{to_label}**",
        color=faction_color
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
