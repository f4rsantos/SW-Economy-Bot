# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.map_service import get_world, add_world
from services.validation_service import require_world


@app_commands.command(name="add-place", description="Add a new world (Admin)")
@app_commands.describe(
    name="World name",
    orbit_of="Parent body name",
    hex_count="Number of hexes on this world",
    population_capacity_per_hex="Population capacity per hex",
    background="Background description",
    u_cm="U-CM percentage (1-100)",
    u_el="U-EL percentage (1-100)",
    u_cs="U-CS percentage (1-100)"
)
@require_access_level(7)
async def add_place(
    interaction: discord.Interaction,
    name: str,
    orbit_of: str,
    hex_count: int,
    population_capacity_per_hex: int = 200000,
    background: Optional[str] = None,
    u_cm: Optional[int] = None,
    u_el: Optional[int] = None,
    u_cs: Optional[int] = None
):
    await interaction.response.defer()

    r_parent = await require_world(orbit_of)
    if not r_parent.ok:
        await interaction.followup.send(embed=error_embed("Error", f"Parent body '{orbit_of}' not found. Create it first."))
        return
    parent_data = r_parent.data

    if await get_world(name):
        await interaction.followup.send(embed=error_embed("Error", f"World '{name}' already exists."))
        return

    if hex_count <= 0:
        await interaction.followup.send(embed=error_embed("Error", "Hex count must be positive."))
        return

    resource_percentages = {}
    for res_name, val in [('U-CM', u_cm), ('U-EL', u_el), ('U-CS', u_cs)]:
        if val is not None:
            if not 1 <= val <= 100:
                await interaction.followup.send(embed=error_embed("Error", f"{res_name} percentage must be between 1 and 100."))
                return
            resource_percentages[res_name] = val

    if u_cs is not None and u_cs >= 80 and population_capacity_per_hex == 200000:
        population_capacity_per_hex = 300000

    world_result = await add_world(
        name,
        parent_data['id'],
        hex_count,
        population_capacity_per_hex,
        background,
        resource_percentages,
    )

    embed = success_embed(title="World Created", description=f"**{name}** has been added to the map.")
    embed.add_field(name="Orbits", value=parent_data['name'], inline=True)
    embed.add_field(name="Hexes", value=f"{hex_count:,}", inline=True)
    embed.add_field(name="Pop Cap/Hex", value=f"{population_capacity_per_hex:,}", inline=True)
    if resource_percentages:
        embed.add_field(name="Resources", value="\n".join(f"{r}: {p}%" for r, p in resource_percentages.items()), inline=False)
    if background:
        embed.add_field(name="Background", value=background, inline=False)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(add_place)
