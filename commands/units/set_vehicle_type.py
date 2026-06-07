import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.vehicle_service import set_vehicle_type as set_vehicle_type_service
from services.validation_service import require_faction, require_vehicle

VEHICLE_TYPE_NAMES = {
    1: "Space",
    2: "Sea",
    3: "Ground",
    4: "Air",
    5: "Platform",
}


@app_commands.command(name="set-type", description="Set the domain type of a vehicle design")
@app_commands.describe(
    faction="Faction name or ID that owns the vehicle",
    vehicle_id="Vehicle display ID or name",
    vehicle_type="New domain type"
)
@app_commands.choices(vehicle_type=[
    app_commands.Choice(name="Space",    value=1),
    app_commands.Choice(name="Sea",      value=2),
    app_commands.Choice(name="Ground",   value=3),
    app_commands.Choice(name="Air",      value=4),
    app_commands.Choice(name="Platform", value=5)
])
@require_access_level(0)
async def set_vehicle_type(
    interaction: discord.Interaction,
    faction: str,
    vehicle_id: str,
    vehicle_type: app_commands.Choice[int]
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    r_vehicle_data = await require_vehicle(vehicle_id, faction_data['id'])
    if not r_vehicle_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_vehicle_data.error))
    vehicle_data = r_vehicle_data.data

    old_type = VEHICLE_TYPE_NAMES.get(vehicle_data['type'], 'Unknown')

    if old_type == vehicle_type.name:
        await interaction.followup.send(embed=error_embed("Error", f"Vehicle is already set to {vehicle_type.name}."))
        return

    await set_vehicle_type_service(vehicle_data['id'], vehicle_type.value)

    embed = success_embed("Vehicle Type Updated", f"**{vehicle_data['name']}**\n{old_type} → **{vehicle_type.name}**")
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(set_vehicle_type)
