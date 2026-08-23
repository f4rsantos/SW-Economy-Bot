# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import parse_currency, handle_return
from utils.faction_utils import hex_to_int
from services.battle_service import repair_fleet, get_fleet_costs
from services.fleet_service import get_fleet_by_identifier
from services.validation_service import require_faction


@app_commands.command(name="repair", description="Repair a damaged unit (costs resources)")
@app_commands.describe(
    unit="Unit number or name (e.g. '3' for Unit #3)",
    repair_amount="Amount of health to repair (percentage points, 1-100)",
    costs="Optional: Manual resource costs (e.g., '1000 ER, 500 CM'). If omitted, auto-calculates.",
    faction="Your faction name",
    ref="Set to True for free repair (no resource cost)"
)
@require_access_level(0)
async def repair_unit_cmd(
    interaction: discord.Interaction,
    unit: str,
    repair_amount: int,
    faction: str,
    costs: Optional[str] = None,
    ref: bool = False
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    if repair_amount < 1 or repair_amount > 100:
        await interaction.followup.send(embed=error_embed("Error", "Repair amount must be between 1 and 100."))
        return

    unit_data = await get_fleet_by_identifier(unit, faction_data.id)
    if not unit_data:
        await interaction.followup.send(embed=error_embed("Error", "Unit not found or you don't own this unit."))
        return

    if unit_data.health >= 100:
        await interaction.followup.send(embed=error_embed("Error", "Unit is already at full health."))
        return

    max_repairable = 100 - unit_data.health
    if repair_amount > max_repairable:
        await interaction.followup.send(embed=error_embed("Error", f"Unit only needs {max_repairable}% repair to reach full health."))
        return

    if unit_data.status_name.lower() == 'in combat':
        await interaction.followup.send(embed=error_embed("Error", "Cannot repair a unit while it's in combat."))
        return

    actual_repair = min(repair_amount, max_repairable)

    if ref:
        costs_dict = {}
        cost_text = "\n**Cost:** FREE (ref=True)"
    elif costs:
        try:
            parsed = parse_currency(costs)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", f"Invalid cost format: {e}"))
            return
        costs_dict = {item['resource']: item['amount'] for item in parsed}
        cost_text = f"\n**Cost Paid:** {', '.join(f'{handle_return(v)} {k}' for k, v in costs_dict.items())}"
    else:
        unit_costs = await get_fleet_costs(unit_data.id)
        if not unit_costs:
            await interaction.followup.send(embed=error_embed("Error", "Unit has no vehicles or costs defined. Use ref=True or specify costs manually."))
            return
        costs_dict = {}
        cost_parts = []
        for row in unit_costs:
            amount = int(int(row['total_cost']) * (actual_repair / 100))
            if amount > 0:
                costs_dict[row['resource_name']] = amount
                cost_parts.append(f"{handle_return(amount)} {row['resource_name']}")
        if not costs_dict:
            await interaction.followup.send(embed=error_embed("Error", "Calculated repair cost is 0. Use ref=True for free repair."))
            return
        cost_text = f"\n**Cost Paid:** {', '.join(cost_parts)} ({actual_repair}% of unit value)"

    try:
        await repair_fleet(unit_data.id, faction_data.id, actual_repair, costs_dict)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_name = unit_data.name or f"Unit #{unit_data.id}"
    embed = success_embed(
        "Unit Repaired",
        f"**{unit_name}** at **{unit_data.position_name}**\n"
        f"**Repaired:** {actual_repair}% HP{cost_text}\n"
        f"**Health:** {unit_data.health}% → {unit_data.health + actual_repair}%"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(repair_unit_cmd)
