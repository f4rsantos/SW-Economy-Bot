# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.building_efficiency_service import get_faction_building_count_actual
from services.building_service import (
    get_buildings_catalog, get_all_building_cost_rows, get_faction_mega_factory_count,
    get_faction_building_ids_at_level, get_building_ids_supporting_level,
    MEGA_FACTORY_BUILDING_ID, MEGA_FACTORY_SCALE_RATE,
)
from services.validation_service import require_faction


@app_commands.command(name="buildings", description="View building types and their costs")
@app_commands.describe(
    faction="Optional: View costs for a specific faction (includes scaling)",
    level="Optional: Only show buildings of this level"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def buildings_list(interaction: discord.Interaction, faction: str = None, level: int = None):
    await defer_response(interaction)

    faction_data = None
    curr_buildings = 0
    curr_mega = 0

    if faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data
        curr_buildings = max(0, await get_faction_building_count_actual(faction_data.id) - 27)
        curr_mega = await get_faction_mega_factory_count(faction_data.id)

    buildings_data = await get_buildings_catalog()

    if level is not None:
        if faction_data:
            allowed_ids = await get_faction_building_ids_at_level(faction_data.id, level)
        else:
            allowed_ids = await get_building_ids_supporting_level(level)
        buildings_data = [b for b in buildings_data if b.id in allowed_ids]

    if not buildings_data:
        empty_msg = f"No buildings found at level {level}." if level is not None else "No buildings found."
        await interaction.followup.send(embed=error_embed("No Data", empty_msg))
        return

    all_costs_rows = await get_all_building_cost_rows()
    costs_by_building: dict = {}
    for row in all_costs_rows:
        costs_by_building.setdefault(row.building_id, []).append(row)

    title = f"Building Costs for {faction_data.display_name}" if faction_data else "Building Types"
    if level is not None:
        title += f" (Level {level})"
    if faction_data:
        desc = f"Current Buildings (Taxable): {curr_buildings} (Next Cost: Base * (1 + 0.02 * {curr_buildings}))\n*Starter buildings (27) are excluded from cost scaling.*"
    else:
        desc = "Available buildings with costs and scaling (2% linear increase per building)\n*First 27 buildings (starter pack) do not increase costs.*"

    embed = discord.Embed(title=title, description=desc, color=hex_to_int(faction_data.color) if faction_data else 0x2ecc71)

    for building in buildings_data:
        costs = costs_by_building.get(building.id, [])
        if costs:
            cost_str = ", ".join(f"{handle_return(c.amount)} {c.name}" for c in costs)
            if faction_data:
                if building.id == MEGA_FACTORY_BUILDING_ID:
                    scale = (1 + MEGA_FACTORY_SCALE_RATE) ** curr_mega
                    personal_costs = [
                        f"{handle_return(int(c.amount * scale))} {c.name}"
                        for c in costs
                    ]
                else:
                    scale_factor = 1 + (0.02 * curr_buildings)
                    personal_costs = [f"{handle_return(int(c.amount * scale_factor))} {c.name}" for c in costs]
                scaling_str = f"**Your Cost:** {', '.join(personal_costs)}"
            else:
                scaling_str = ""
        else:
            cost_str = "No cost data"
            scaling_str = ""

        info_parts = []
        if building.production:
            prod_type = "Refinery" if building.is_refinery else "Extractor"
            affected = " (% affected)" if building.percentage_affects else ""
            info_parts.append(f"{prod_type}: {handle_return(building.production)} {building.resource_name}{affected}")
        if building.storage:
            info_parts.append(f"Storage: {handle_return(building.storage)} {building.resource_name}")

        info_str = "\n".join(info_parts) if info_parts else "Non-production building"
        field_value = f"**Base Cost:** {cost_str}\n"
        if scaling_str:
            field_value += f"{scaling_str}\n"
        field_value += info_str
        if building.description:
            field_value += f"\n*{building.description}*"

        embed.add_field(name=f"{building.name} (ID: {building.id})", value=field_value, inline=False)

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(buildings_list)
