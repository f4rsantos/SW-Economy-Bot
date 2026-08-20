import asyncio
import random
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import create_embed, error_embed, terminal_panel, meta_line, route_bar
from utils.currency import split_currency, handle_return
from utils.faction_utils import hex_to_int
from services.econ_query_service import execute_vesta_trade
from services.blockade_service import check_belt_station_blockade
from services.validation_service import require_faction, require_world

STATION_NAME = "Vesta Refinery Terminal"
WELCOME = (
    "Greetings, what brings you to Vesta?\n\n"
    "We'll refine anything you got!\n"
    "We can only give you 1/4th of what you give us, "
    "we got to make a living somehow y'know?"
)


def _info_embed() -> discord.Embed:
    return create_embed(
        title=STATION_NAME,
        description=terminal_panel(
            "VESTA REFINERY TERMINAL",
            [meta_line("SMELTERY")],
            ["4 raw in, 1 pure out"],
        ),
        fields=[
            {'name': "Welcome", 'value': WELCOME, 'inline': False},
            {'name': "Rate", 'value': "4 : 1", 'inline': True},
            {'name': "Accepts", 'value': "U-CM, U-CS, U-EL", 'inline': True},
            {'name': "Usage", 'value': "`/vesta faction: world: choice: payment:`", 'inline': False},
        ],
    )


@app_commands.command(name="vesta", description="Access the Vesta refining market")
@app_commands.describe(
    faction="Faction name",
    world="World the unrefined resources are on (e.g. Ceres)",
    choice="Type of resource to receive (CM, CS, or EL)",
    payment="Amount of unrefined resources to trade (e.g., '1000 U-CM')",
    info="Show how the station works instead of refining"
)
@app_commands.choices(choice=[
    app_commands.Choice(name="CM", value="CM"),
    app_commands.Choice(name="CS", value="CS"),
    app_commands.Choice(name="EL", value="EL")
])
@require_access_level(0)
async def vesta(
    interaction: discord.Interaction,
    faction: Optional[str] = None,
    world: Optional[str] = None,
    choice: Optional[str] = None,
    payment: Optional[str] = None,
    info: bool = False
):
    await interaction.response.defer()

    if info:
        await interaction.followup.send(embed=_info_embed())
        return

    missing = [n for n, v in (("faction", faction), ("world", world), ("choice", choice), ("payment", payment)) if not v]
    if missing:
        await interaction.followup.send(embed=error_embed(
            "Error",
            f"Missing {', '.join(missing)}. Use `/vesta info:true` to see how the station works."
        ))
        return

    gain = choice.upper()
    expected = f"U-{gain}"

    r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    faction_data = r_faction_data.data
    world_data = r_world.data

    if await check_belt_station_blockade(faction_data['id']):
        await interaction.followup.send(embed=error_embed("Blockaded", "Your faction is blockaded at Ceres or Vesta and cannot use belt station markets."))
        return

    costs = [(int(amt), name) for amt, name in split_currency(payment) if name == expected]
    if not costs:
        await interaction.followup.send(embed=error_embed("Error", f"You must pay with {expected} to receive {gain}."))
        return

    total_in = sum(amt for amt, _ in costs)
    gain_amount = total_in // 4

    try:
        await execute_vesta_trade(faction_data['id'], world_data['id'], expected, total_in, gain_amount, gain)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    bay = random.randint(1, 24)

    embed = create_embed(
        title=STATION_NAME,
        description=terminal_panel(
            "VESTA REFINERY TERMINAL",
            [meta_line(f"DOCK: BAY-{bay:02d}", f"BUYER: {faction_data['name'][:10].upper()}")],
            ["", "   " + route_bar(expected, gain, 31), ""],
        ),
        color=hex_to_int(faction_data['color']),
        fields=[
            {'name': "Refined", 'value': f"{handle_return(gain_amount)} {gain}", 'inline': True},
            {'name': "Paid", 'value': f"{handle_return(total_in)} {expected}", 'inline': True},
            {'name': "Delivered to", 'value': world_data['name'], 'inline': True},
        ],
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(vesta)
