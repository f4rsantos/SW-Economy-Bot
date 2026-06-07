import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import get_faction, hex_to_int
from utils.fleet_utils import get_vehicle_in_fleet
from services.fleet_service import transfer_vehicle
from services.validation_service import require_faction, require_unit


@app_commands.command(name="transfer", description="Transfer vehicles between units")
@app_commands.describe(
    faction="Faction name or ID that owns the source unit",
    from_unit_id="Source unit ID or name",
    to_unit_id="Destination unit ID or name",
    vehicle_id="Vehicle display ID or name",
    amount="Number of vehicles to transfer",
    target_faction="Target faction name (for inter-faction transfers)"
)
@require_access_level(0)
async def transfer_vehicle_cmd(
    interaction: discord.Interaction,
    faction: str,
    from_unit_id: str,
    to_unit_id: str,
    vehicle_id: str,
    amount: int,
    target_faction: str = None
):
    await interaction.response.defer()

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    if from_unit_id == to_unit_id:
        await interaction.followup.send(embed=error_embed("Error", "Cannot transfer to the same unit."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    r_from_unit = await require_unit(from_unit_id, faction_data['id'])
    if not r_from_unit.ok: return await interaction.followup.send(embed=error_embed("Error", r_from_unit.error))
    from_unit = r_from_unit.data

    if from_unit['status_name'].lower() == 'debris':
        await interaction.followup.send(embed=error_embed("Error", "Cannot transfer vehicles from debris units."))
        return

    vehicle_data = await get_vehicle_in_fleet(vehicle_id, from_unit['id'])
    if not vehicle_data:
        await interaction.followup.send(embed=error_embed("Error", f"Vehicle '{vehicle_id}' not found in source unit."))
        return

    if target_faction:
        r_target_faction_data = await require_faction(target_faction)
        if not r_target_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_target_faction_data.error))
        target_faction_data = r_target_faction_data.data
        dest_faction_id = target_faction_data['id']
    else:
        dest_faction_id = faction_data['id']

    r_to_unit = await require_unit(to_unit_id, dest_faction_id)
    if not r_to_unit.ok: return await interaction.followup.send(embed=error_embed("Error", r_to_unit.error))
    to_unit = r_to_unit.data

    if to_unit['status_name'].lower() == 'debris':
        await interaction.followup.send(embed=error_embed("Error", "Cannot transfer vehicles to debris units."))
        return

    try:
        await transfer_vehicle(from_unit['id'], to_unit['id'], vehicle_data['id'], amount)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    from_name = from_unit['name'] or f"Unit #{from_unit['faction_fleet_number']}"
    to_name = to_unit['name'] or f"Unit #{to_unit['faction_fleet_number']}"

    embed = success_embed(
        "Vehicles Transferred",
        f"**{amount:,}x {vehicle_data['name']}**\n\n"
        f"From: **{from_name}** ({from_unit['world_name']})\n"
        f"To: **{to_name}** ({to_unit['world_name']})"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(transfer_vehicle_cmd)
