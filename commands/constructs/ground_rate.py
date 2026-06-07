import discord
from discord import app_commands
from typing import Optional, Literal
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_return, handle_currency
from utils.views import RegisterVehicleView
from services.ratings.ground_rating_service import rate_ground_vehicle
from services.validation_service import require_faction


@app_commands.command(name="ground", description="Rate ground vehicles")
@app_commands.describe(
    name="Name of the ground vehicle",
    designation="Short designation code (max 25 chars)",
    length="Length of vehicle in meters",
    faction="The faction designing this vehicle (required to register)",
    armor="Armor level",
    protection="Active Protection System type",
    heavy="Heavy armament count (100mm+ cannons, 130mm+ rockets, long range missiles)",
    medium="Medium armament count (up to 99mm cannons, short range missiles)",
    light="Light armament count (machine guns, grenade launchers up to 40mm)",
    rocket="Rocket armament count (unguided rockets up to 130mm)",
    shield="Has shield system",
    systems="Additional systems count",
    other="Additional cost modifier"
)
@require_access_level(0)
async def ground_rate(
    interaction: discord.Interaction,
    length: float,
    name: Optional[str] = None,
    faction: Optional[str] = None,
    armor: Literal["none", "light", "medium", "heavy"] = "none",
    protection: Literal["none", "soft", "hard", "both"] = "none",
    heavy: int = 0,
    medium: int = 0,
    light: int = 0,
    rocket: int = 0,
    shield: bool = False,
    systems: int = 0,
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
        'length': length, 'armor': armor, 'protection': protection,
        'heavy': heavy, 'medium': medium, 'light': light, 'rocket': rocket,
        'shield': shield, 'systems': systems, 'other': other_cost
    }

    costs = rate_ground_vehicle(data)
    upkeep = costs['CS'] // 6

    embed = success_embed(title=f"Ground Vehicle: {name}" if name else "Ground Vehicle", description="**Ground Vehicle** design rated")
    if faction_data:
        embed.color = hex_to_int(faction_data['color'])

    embed.add_field(name="ER Cost", value=handle_return(costs['ER']), inline=True)
    embed.add_field(name="CM Cost", value=handle_return(costs['CM']), inline=True)
    embed.add_field(name="EL Cost", value=handle_return(costs['EL']), inline=True)
    embed.add_field(name="CS Cost", value=handle_return(costs['CS']), inline=True)
    embed.add_field(name="Upkeep", value=f"{handle_return(upkeep)} CS", inline=True)
    if designation:
        embed.add_field(name="Designation", value=designation, inline=True)
    embed.add_field(
        name="Specifications",
        value=f"Length: {length}m | Armor: {armor} | Protection: {protection}\nHeavy: {heavy} | Medium: {medium} | Light: {light} | Rockets: {rocket}",
        inline=False
    )

    if faction_data and name:
        view = RegisterVehicleView(interaction.user.id, faction_data['id'], faction_data['display_name'], name, designation, "ground", costs, data)
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(ground_rate)
