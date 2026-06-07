import discord
from discord import app_commands
from typing import Literal, Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_return, handle_currency
from utils.views import RegisterVehicleView
from services.ratings.air_rating_service import rate_aircraft
from services.validation_service import require_faction


@app_commands.command(name="air", description="Calculate aircraft costs")
@app_commands.describe(
    name="Name of the aircraft",
    designation="Short designation code (max 25 chars)",
    length="Length of aircraft in meters",
    faction="The faction designing this aircraft (required to register)",
    aircraft_type="Type of aircraft",
    weapons="Is the aircraft armed?",
    guns="Number of guns/cannons",
    stealth="Stealth level",
    engines="Number of engines",
    systems="Number of additional systems",
    ordnance_kg="Ordnance capacity in kg",
    cargo="Cargo capacity",
    helicopter="Is this a helicopter?",
    radar="Radar type",
    flight_type="Flight capability",
    capability="Landing capability",
    speed_mach="Speed in Mach number (for air/hybrid)",
    shield="Has shields?",
    other="Additional cost modifier"
)
@require_access_level(0)
async def air_rate(
    interaction: discord.Interaction,
    length: float,
    name: Optional[str] = None,
    faction: Optional[str] = None,
    aircraft_type: Literal["fighter", "bomber", "transport", "drone", "gunship"] = "fighter",
    weapons: bool = False,
    guns: int = 0,
    stealth: Literal["none", "low", "yes"] = "none",
    engines: int = 1,
    systems: int = 0,
    ordnance_kg: int = 0,
    cargo: int = 0,
    helicopter: bool = False,
    radar: Literal["normal", "AEW"] = "normal",
    flight_type: Literal["air", "hybrid", "space"] = "air",
    capability: Literal["none", "STOL", "VTOL"] = "none",
    speed_mach: Optional[float] = None,
    shield: bool = False,
    other: str = "0",
    designation: Optional[str] = None
):
    await interaction.response.defer()

    other_cost = int(handle_currency(other))

    faction_data = None
    if faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
        faction_data = r_faction_data.data

    if designation and len(designation) > 25:
        await interaction.followup.send(embed=error_embed("Error", "Designation must be 25 characters or less."), ephemeral=True)
        return

    data = {
        'length': length, 'aircraft_type': aircraft_type, 'weapons': weapons, 'guns': guns,
        'stealth': stealth, 'engines': engines, 'systems': systems, 'ordnance_kg': ordnance_kg,
        'cargo': cargo, 'helicopter': helicopter, 'radar': radar, 'flight_type': flight_type,
        'capability': capability, 'speed_mach': speed_mach, 'shield': shield, 'other': other_cost
    }

    type_names = {'fighter': 'Fighter', 'bomber': 'Bomber', 'transport': 'Transport', 'drone': 'Drone', 'gunship': 'Gunship'}
    costs = rate_aircraft(data)
    upkeep = costs['CS'] // 6

    embed = success_embed(title=f"Aircraft: {name}" if name else "Aircraft", description=f"**{type_names.get(aircraft_type, aircraft_type)}**")
    if faction_data:
        embed.color = hex_to_int(faction_data['color'])

    embed.add_field(name="ER Cost", value=handle_return(costs['ER']), inline=True)
    embed.add_field(name="CM Cost", value=handle_return(costs['CM']), inline=True)
    embed.add_field(name="EL Cost", value=handle_return(costs['EL']), inline=True)
    embed.add_field(name="CS Cost", value=handle_return(costs['CS']), inline=True)
    embed.add_field(name="Upkeep", value=f"{handle_return(upkeep)} CS", inline=True)
    if designation:
        embed.add_field(name="Designation", value=designation, inline=True)

    specs = [f"Length: {length}m", f"Engines: {engines}", f"Flight Type: {flight_type.title()}"]
    if weapons: specs.append("Armed")
    if guns > 0: specs.append(f"Guns: {guns}")
    if stealth != "none": specs.append(f"Stealth: {stealth.title()}")
    if helicopter: specs.append("Helicopter")
    if radar == "AEW": specs.append("AEW Radar")
    if capability != "none": specs.append(capability)
    if ordnance_kg > 0: specs.append(f"Ordnance: {ordnance_kg}kg")
    if cargo > 0: specs.append(f"Cargo: {cargo}")
    if systems > 0: specs.append(f"Systems: {systems}")
    if shield: specs.append("Shielded")
    if flight_type in ["air", "hybrid"] and speed_mach and speed_mach > 0: specs.append(f"Speed: Mach {speed_mach}")
    embed.add_field(name="Specifications", value=" | ".join(specs), inline=False)

    if faction_data and name:
        vehicle_type = "Space" if flight_type in ["hybrid", "space"] else "Air"
        view = RegisterVehicleView(interaction.user.id, faction_data['id'], faction_data['display_name'], name, designation, vehicle_type, costs, data)
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(air_rate)
