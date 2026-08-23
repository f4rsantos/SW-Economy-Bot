# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Literal, Optional
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import get_faction, hex_to_int
from utils.fleet_utils import get_vehicle_in_fleet
from utils.currency import handle_return
from services.fleet_service import add_vehicle_to_fleet, refund_vehicle as svc_refund_vehicle
from services.validation_service import require_faction, require_unit, require_vehicle


@app_commands.command(name="buy-free", description="Admin: Instantly add vehicles to unit for free")
@app_commands.describe(
    faction="Faction that owns the unit",
    unit_id="Unit ID or name",
    vehicle_id="Vehicle name or ID",
    amount="Number of vehicles to add",
    vehicle_faction="Faction that owns the vehicle design (optional)"
)
@require_access_level(4)
async def buy_vehicle_free(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    vehicle_id: str,
    amount: int,
    vehicle_faction: Optional[str] = None
):
    await interaction.response.defer()

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    r_user_faction = await require_faction(faction)
    if not r_user_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_user_faction.error))
    user_faction = r_user_faction.data

    faction_color = hex_to_int(user_faction.color)

    r_unit_data = await require_unit(unit_id, user_faction.id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    if vehicle_faction:
        r_veh_faction = await require_faction(vehicle_faction)
        if not r_veh_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_veh_faction.error))
        veh_faction = r_veh_faction.data
        target_faction_id = veh_faction.id
    else:
        target_faction_id = user_faction.id

    r_vehicle_data = await require_vehicle(vehicle_id, target_faction_id)
    if not r_vehicle_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_vehicle_data.error))
    vehicle_data = r_vehicle_data.data

    try:
        await add_vehicle_to_fleet(unit_data['id'], vehicle_data['id'], amount)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    embed = success_embed(
        title="Vehicles Added (Free)",
        description=f"**{amount}x {vehicle_data['name']}** added to **{unit_name}**."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


@app_commands.command(name="refund", description="Refund and remove vehicles from a unit")
@app_commands.describe(
    faction="Faction that owns the unit",
    unit_id="Unit ID or name",
    vehicle_id="Vehicle name or ID",
    amount="Number of vehicles to refund",
    percentage="Refund percentage"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def refund_vehicle_cmd(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    vehicle_id: str,
    amount: int,
    percentage: Literal["100%", "75%", "50%", "0%"]
):
    await defer_response(interaction)

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    pct_val = {"100%": 1.0, "75%": 0.75, "50%": 0.50, "0%": 0.0}[percentage]

    r_user_faction = await require_faction(faction)
    if not r_user_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_user_faction.error))
    user_faction = r_user_faction.data

    faction_color = hex_to_int(user_faction.color)

    r_unit_data = await require_unit(unit_id, user_faction.id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    target_vehicle = await get_vehicle_in_fleet(vehicle_id, unit_data['id'])
    if not target_vehicle:
        await interaction.followup.send(embed=error_embed("Error", f"Vehicle '{vehicle_id}' not found in unit."))
        return

    try:
        await svc_refund_vehicle(unit_data['id'], target_vehicle['id'], amount, user_faction.id, pct_val)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    embed = success_embed(
        title="Vehicles Refunded",
        description=f"**{amount}x {target_vehicle['name']}** removed from **{unit_name}** ({percentage} refund)."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(buy_vehicle_free)
    bot.tree.add_command(refund_vehicle_cmd)
