import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.currency import split_currency, handle_return, handle_return_multiple, resource_array_to_object
from utils.faction_utils import hex_to_int
from services.trade_service import get_trade_delivery_world, execute_ceres_trade
from services.blockade_service import check_belt_station_blockade
from services.validation_service import require_faction


@app_commands.command(name="ceres", description="Access the Ceres trading market")
@app_commands.describe(
    faction="Faction name",
    choice="Type of resource to receive (CM, CS, or EL)",
    payment="Amount of funds to trade (e.g., '1000 CM, 500 CS')",
    world="World to receive the traded resources (optional)"
)
@app_commands.choices(choice=[
    app_commands.Choice(name="CM", value="CM"),
    app_commands.Choice(name="CS", value="CS"),
    app_commands.Choice(name="EL", value="EL")
])
@require_access_level(0)
async def ceres(interaction: discord.Interaction, faction: str, choice: str, payment: str, world: Optional[str] = None):
    await interaction.response.defer()

    gain = choice.upper()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    if await check_belt_station_blockade(faction_data['id']):
        await interaction.followup.send(embed=error_embed("Blockaded", "Your faction is blockaded at Ceres or Vesta and cannot use belt station markets."))
        return

    try:
        world_data = await get_trade_delivery_world(faction_data['id'], world)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    costs = [(amt - amt % 4, name) for amt, name in split_currency(payment) if name in ('CM', 'CS', 'EL')]
    costs = [(int(amt), name) for amt, name in costs if amt > 0]
    if not costs:
        await interaction.followup.send(embed=error_embed("Error", "No valid resources in payment. Use CM, CS, or EL."))
        return

    gain_amount = sum(amt for amt, _ in costs) // 4

    try:
        await execute_ceres_trade(faction_data['id'], world_data['id'], gain, costs)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = discord.Embed(
        title="Ceres Station",
        description=f"Welcome to Ceres, **{faction_data['display_name']}**!\n\n"
                    f"We have the best prices in the system...\n"
                    f"Buy any resource for 4 other resources!\n\n"
                    f"You've bought **{handle_return(gain_amount)} {gain}**\n"
                    f"for {handle_return_multiple(resource_array_to_object(costs))}.\n\n"
                    f"Delivered to **{world_data['name']}**.",
        color=hex_to_int(faction_data['color'])
    )
    embed.set_footer(text="Trade complete")
    embed.timestamp = discord.utils.utcnow()
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(ceres)
