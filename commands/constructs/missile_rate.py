import discord
from discord import app_commands
from typing import Literal, Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.views import RegisterVehicleView
from services.ratings.missile_rating_service import rate_missile
from services.validation_service import require_faction

_TYPE_NAMES = {
    'cruise': 'Cruise Missile',
    'gto': 'Ground to Orbit',
    'ip': 'Inter Planetary',
    'ballistic': 'Ballistic Missile',
    'interceptor': 'Interceptor'
}


@app_commands.command(name="missile", description="Calculate missile costs")
@app_commands.describe(
    name="Name of the missile",
    designation="Short designation code (max 25 chars)",
    faction="The faction designing this missile (required to register)",
    length="Length of missile in meters",
    missile_type="Type of missile",
    nuclear="Nuclear warhead yield in kilotons",
    systems="Additional systems count"
)
@require_access_level(0)
async def missile_rate(
    interaction: discord.Interaction,
    length: float,
    name: Optional[str] = None,
    designation: Optional[str] = None,
    faction: Optional[str] = None,
    missile_type: Literal["cruise", "gto", "ip", "ballistic", "interceptor"] = "cruise",
    nuclear: int = 0,
    systems: int = 0
):
    await interaction.response.defer()

    faction_data = None
    if faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok:
            return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
        faction_data = r_faction_data.data

    if designation and len(designation) > 25:
        await interaction.followup.send(embed=error_embed("Error", "Designation must be 25 characters or less."), ephemeral=True)
        return

    data = {'length': length, 'type': missile_type, 'nuclear': nuclear, 'systems': systems}

    try:
        costs = rate_missile(data)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Failed to calculate missile cost: {str(e)}"), ephemeral=True)
        return

    register_costs = {k: v for k, v in costs.items() if k != 'CS'}

    embed = success_embed(title=f"Missile: {name}" if name else "Missile", description=f"**{_TYPE_NAMES.get(missile_type, missile_type)}**")
    if faction_data:
        from utils.faction_utils import hex_to_int
        embed.color = hex_to_int(faction_data['color'])
    embed.add_field(name="ER Cost", value=handle_return(costs['ER']), inline=True)
    embed.add_field(name="CM Cost", value=handle_return(costs['CM']), inline=True)
    embed.add_field(name="EL Cost", value=handle_return(costs['EL']), inline=True)
    embed.add_field(name="CS Cost", value=handle_return(costs['CS']), inline=True)
    embed.add_field(name="Upkeep", value="None (missiles exempt)", inline=True)
    if designation:
        embed.add_field(name="Designation", value=designation, inline=True)
    embed.add_field(name="Specifications", value=f"Length: {length}m | Nuclear: {nuclear} kilotons | Systems: {systems}", inline=False)

    if faction_data and name:
        view = RegisterVehicleView(
            interaction.user.id, faction_data['id'], faction_data['display_name'],
            name, designation, "Missile", register_costs, data
        )
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(missile_rate)
