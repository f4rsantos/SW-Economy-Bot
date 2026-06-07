import discord
from discord import app_commands
from typing import Literal, Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from services.ratings.missile_rating_service import rate_missile

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
    missile_type: Literal["cruise", "gto", "ip", "ballistic", "interceptor"] = "cruise",
    nuclear: int = 0,
    systems: int = 0
):
    await interaction.response.defer()

    data = {'length': length, 'type': missile_type, 'nuclear': nuclear, 'systems': systems}

    try:
        costs = rate_missile(data)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Failed to calculate missile cost: {str(e)}"), ephemeral=True)
        return

    embed = success_embed(title=f"Missile: {name}" if name else "Missile", description=f"**{_TYPE_NAMES.get(missile_type, missile_type)}**")
    embed.add_field(name="ER Cost", value=handle_return(costs['ER']), inline=True)
    embed.add_field(name="CM Cost", value=handle_return(costs['CM']), inline=True)
    embed.add_field(name="EL Cost", value=handle_return(costs['EL']), inline=True)
    embed.add_field(name="CS Cost", value=handle_return(costs['CS']), inline=True)
    embed.add_field(name="Specifications", value=f"Length: {length}m | Nuclear: {nuclear} kilotons | Systems: {systems}", inline=False)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(missile_rate)
