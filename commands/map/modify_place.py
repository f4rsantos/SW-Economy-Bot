# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.map_service import modify_world
from services.validation_service import require_world


@app_commands.command(name="modify-place", description="Modify world properties (Admin)")
@app_commands.describe(
    world="World name",
    hex_count="New hex count",
    population_capacity_per_hex="New population capacity per hex",
    background="New background description",
    orbit_of="New parent body name",
    u_cm="New U-CM percentage (1-100)",
    u_el="New U-EL percentage (1-100)",
    u_cs="New U-CS percentage (1-100)"
)
@require_access_level(7)
async def modify_place(
    interaction: discord.Interaction,
    world: str,
    hex_count: Optional[int] = None,
    population_capacity_per_hex: Optional[int] = None,
    background: Optional[str] = None,
    orbit_of: Optional[str] = None,
    u_cm: Optional[int] = None,
    u_el: Optional[int] = None,
    u_cs: Optional[int] = None
):
    await interaction.response.defer()

    r_world = await require_world(world)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    world_data = r_world.data

    world_id = world_data['id']

    if all(arg is None for arg in [hex_count, population_capacity_per_hex, background, orbit_of, u_cm, u_el, u_cs]):
        await interaction.followup.send(embed=error_embed("Error", "No changes specified."))
        return

    resource_updates = {}
    for res_name, val in [('U-CM', u_cm), ('U-EL', u_el), ('U-CS', u_cs)]:
        if val is not None:
            if not 1 <= val <= 100:
                await interaction.followup.send(embed=error_embed("Error", f"{res_name} percentage must be between 1 and 100."))
                return
            resource_updates[res_name] = val

    orbit_of_id = None
    if orbit_of is not None:
        r_parent = await require_world(orbit_of)
        if not r_parent.ok:
            await interaction.followup.send(embed=error_embed("Error", r_parent.error))
            return
        orbit_of_id = r_parent.data['id']
    try:
        await modify_world(
            world_id,
            world_data,
            hex_count,
            population_capacity_per_hex,
            background,
            orbit_of_id,
            resource_updates,
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="World Modified", description=f"**{world_data['name']}** has been updated.")
    changes = []
    if hex_count is not None:
        changes.append(f"Hex Count: {world_data['hex_count']:,} → {hex_count:,}")
    if population_capacity_per_hex is not None:
        changes.append(f"Pop Cap/Hex: {population_capacity_per_hex:,}")
    if background is not None:
        changes.append(f"Background: {background[:100]}")
    if orbit_of is not None:
        changes.append(f"Now orbits: {orbit_of}")
    for res_name, pct in resource_updates.items():
        changes.append(f"{res_name}: {pct}%")
    if changes:
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(modify_place)
