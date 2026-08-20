import random
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import create_embed, error_embed, terminal_panel, meta_line, route_bar
from utils.currency import split_currency, handle_return
from utils.faction_utils import hex_to_int
from services.trade_service import get_trade_delivery_world, execute_ceres_trade
from services.blockade_service import check_belt_station_blockade
from services.validation_service import require_faction

STATION_NAME = "Ceres Commerce Terminal"
WELCOME = (
    "Welcome to Ceres!\n\n"
    "We have the best prices in the system...\n"
    "Buy any resource for 4 other resources!"
)


def _info_embed() -> discord.Embed:
    return create_embed(
        title=STATION_NAME,
        description=terminal_panel(
            "CERES COMMERCE TERMINAL",
            [meta_line("TRADE POST")],
            ["4 units in, 1 unit out"],
        ),
        fields=[
            {'name': "Welcome", 'value': WELCOME, 'inline': False},
            {'name': "Rate", 'value': "4 : 1", 'inline': True},
            {'name': "Accepts", 'value': "CM, CS, EL", 'inline': True},
            {'name': "Delivery", 'value': "Any world you hold. Defaults to your capital.", 'inline': False},
            {'name': "Usage", 'value': "`/ceres faction: choice: payment: world:`", 'inline': False},
        ],
    )


@app_commands.command(name="ceres", description="Access the Ceres trading market")
@app_commands.describe(
    faction="Faction name",
    choice="Type of resource to receive (CM, CS, or EL)",
    payment="Amount of funds to trade (e.g., '1000 CM, 500 CS')",
    world="World to receive the traded resources (optional)",
    info="Show how the station works instead of trading"
)
@app_commands.choices(choice=[
    app_commands.Choice(name="CM", value="CM"),
    app_commands.Choice(name="CS", value="CS"),
    app_commands.Choice(name="EL", value="EL")
])
@require_access_level(0)
async def ceres(
    interaction: discord.Interaction,
    faction: Optional[str] = None,
    choice: Optional[str] = None,
    payment: Optional[str] = None,
    world: Optional[str] = None,
    info: bool = False
):
    await interaction.response.defer()

    if info:
        await interaction.followup.send(embed=_info_embed())
        return

    missing = [n for n, v in (("faction", faction), ("choice", choice), ("payment", payment)) if not v]
    if missing:
        await interaction.followup.send(embed=error_embed(
            "Error",
            f"Missing {', '.join(missing)}. Use `/ceres info:true` to see how the station works."
        ))
        return

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

    bay = random.randint(1, 24)
    paid = "\n".join(f"{handle_return(amt)} {name}" for amt, name in costs)

    embed = create_embed(
        title=STATION_NAME,
        description=terminal_panel(
            "CERES COMMERCE TERMINAL",
            [meta_line(f"DOCK: BAY-{bay:02d}", f"BUYER: {faction_data['name'][:10].upper()}")],
            ["", "   " + route_bar("CERES", world_data['name'][:9], 31), ""],
        ),
        color=hex_to_int(faction_data['color']),
        fields=[
            {'name': "Bought", 'value': f"{handle_return(gain_amount)} {gain}", 'inline': True},
            {'name': "Paid", 'value': paid, 'inline': True},
            {'name': "Delivered to", 'value': world_data['name'], 'inline': True},
        ],
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(ceres)
