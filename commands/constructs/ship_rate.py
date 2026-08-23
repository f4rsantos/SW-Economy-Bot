# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional, Literal
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_return, handle_currency
from utils.views import RegisterVehicleView
from services.ratings.vehicle_rating_service import rate_spacecraft
from services.validation_service import require_faction


@app_commands.command(name="ship", description="Rate a spacecraft design")
@app_commands.describe(
    name="Name of the ship design",
    designation="Short designation code (max 25 chars)",
    length="Length of the ship in meters",
    faction="The faction designing this ship (required to register)",
    main="Primary weapon count",
    secondary="Secondary weapon count",
    lances="Lance-like weapon count",
    pdc="PDC-like weapon count",
    torpedoes="Torpedo/Missile count",
    shield="Has shield system",
    stealth="Has stealth capabilities",
    systems="Additional systems count",
    engines="Engine configuration (e.g., '4S 2M 1L')",
    ftl="FTL drive type",
    cargo="Cargo space (1 unit per meter)",
    drone="Is this a drone",
    other="Additional cost modifier",
    boat="Is this a boat/water vessel"
)
@require_access_level(0)
async def ship_rate(
    interaction: discord.Interaction,
    length: float,
    name: Optional[str] = None,
    faction: Optional[str] = None,
    main: int = 0,
    secondary: int = 0,
    lances: int = 0,
    pdc: int = 0,
    torpedoes: int = 0,
    shield: bool = False,
    stealth: bool = False,
    systems: int = 0,
    engines: str = "",
    ftl: Literal["EXT", "INT", "NONE"] = "NONE",
    cargo: int = 0,
    drone: bool = False,
    other: str = "0",
    boat: bool = False,
    designation: Optional[str] = None
):
    await interaction.response.defer()

    other_cost = int(handle_currency(other))

    faction_data = None
    if faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data

    if designation and len(designation) > 25:
        await interaction.followup.send(embed=error_embed("Error", "Designation must be 25 characters or less."))
        return

    data = {
        'length': length, 'main': main, 'secondary': secondary, 'lances': lances,
        'pdc': pdc, 'torpedoes': torpedoes, 'shield': shield, 'stealth': stealth,
        'systems': systems, 'engines': engines, 'ftl': ftl, 'cargo': cargo,
        'drone': drone, 'other': other_cost, 'boat': boat
    }

    costs = rate_spacecraft(data)
    upkeep = costs['CS'] // 6

    embed = success_embed(
        title=f"Spacecraft: {name}" if name else "Spacecraft",
        description=f"**{'Boat' if boat else 'Spacecraft'}** design rated"
    )
    if faction_data:
        embed.color = hex_to_int(faction_data.color)

    embed.add_field(name="ER Cost", value=handle_return(costs['ER']), inline=True)
    embed.add_field(name="CM Cost", value=handle_return(costs['CM']), inline=True)
    embed.add_field(name="EL Cost", value=handle_return(costs['EL']), inline=True)
    embed.add_field(name="CS Cost", value=handle_return(costs['CS']), inline=True)
    embed.add_field(name="Upkeep", value=f"{handle_return(upkeep)} CS", inline=True)
    if designation:
        embed.add_field(name="Designation", value=designation, inline=True)
    embed.add_field(name="Specifications", value=f"Length: {length}m | Engines: {engines or 'None'} | FTL: {ftl}", inline=False)

    if faction_data and name:
        vehicle_type = "Sea" if boat else "Space"
        view = RegisterVehicleView(interaction.user.id, faction_data.id, faction_data.display_name, name, designation, vehicle_type, costs, data)
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(ship_rate)
