# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.currency import parse_single_amount, handle_return
from services.trade_service import begin_trade as begin_trade_service, validate_world_for_trade
from services.fleet_service import get_fleet_by_identifier
from database.static_cache import static_cache
from services.validation_service import require_faction


MAX_TRADE_AMOUNT = 1_000_000_000_000_000


@app_commands.command(name="begin", description="Create recurring trade")
@app_commands.describe(
    sender="Sending faction",
    receiver="Receiving faction",
    amount="Amount and resource per income cycle, e.g. '10k CM', '2.5mil ER', '500 CM'",
    from_world="Optional: Specific source world",
    to_world="Optional: Specific destination world",
    escort_fleet="Optional: Escort fleet (requires from_world; must be at that world each cycle)"
)
@require_access_level(0)
@ephemeral_capable('sender')
async def begin_trade(interaction: discord.Interaction, sender: str, receiver: str, amount: str, from_world: str = None, to_world: str = None, escort_fleet: str = None):
    await defer_response(interaction)

    r_sender_data, r_receiver_data = await asyncio.gather(
        require_faction(sender),
        require_faction(receiver)
    )
    if not r_sender_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_sender_data.error))
    sender_data = r_sender_data.data
    if not r_receiver_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_receiver_data.error))
    receiver_data = r_receiver_data.data

    try:
        amount, resource_name = parse_single_amount(amount)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    resource_data = static_cache.get_resource(resource_name)
    if not resource_data:
        await interaction.followup.send(embed=error_embed("Error", f"Resource '{resource_name}' not found."))
        return

    if amount <= 0:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be positive."))
        return
    if amount > MAX_TRADE_AMOUNT:
        await interaction.followup.send(embed=error_embed("Error", f"Amount is too large. Maximum is {handle_return(MAX_TRADE_AMOUNT)}."))
        return

    sender_world_id = None
    if from_world:
        try:
            sender_world_id = await validate_world_for_trade(from_world, sender_data.id)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

    receiver_world_id = None
    if to_world:
        try:
            receiver_world_id = await validate_world_for_trade(to_world, receiver_data.id)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

    escort_fleet_id = None
    escort_display = None
    if escort_fleet:
        if sender_world_id is None:
            await interaction.followup.send(embed=error_embed("Error", "An escort fleet requires a specific from_world."))
            return
        fleet_data = await get_fleet_by_identifier(escort_fleet, sender_data.id)
        if not fleet_data:
            await interaction.followup.send(embed=error_embed("Error", f"Fleet '{escort_fleet}' not found."))
            return
        if fleet_data.position != sender_world_id:
            await interaction.followup.send(embed=error_embed("Error", f"Escort fleet must be at {from_world} to escort this trade."))
            return
        escort_fleet_id = fleet_data.id
        escort_display = fleet_data.name or f"Fleet #{fleet_data.faction_fleet_number}"

    trade_id = await begin_trade_service(
        sender_data.id, receiver_data.id, resource_data['id'], amount, sender_world_id, receiver_world_id, escort_fleet_id
    )

    escort_line = f"**Escort:** {escort_display}\n" if escort_display else ""
    route_line = ""
    if from_world or to_world:
        sw = from_world or "Capital"
        rw = to_world or "Capital"
        route_line = f"**Route:** {sw} → {rw}\n"

    embed = success_embed(
        "Trade Deal Created",
        f"**{sender_data.display_name}** → **{receiver_data.display_name}**\n\n"
        f"**Resource:** {resource_data['name']}\n"
        f"**Amount:** {handle_return(amount)} per income cycle\n"
        f"{route_line}"
        f"{escort_line}"
        f"**Trade ID:** {trade_id}\n\n"
        f"This trade will execute automatically during each income cycle."
    )
    embed.color = hex_to_int(sender_data.color)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(begin_trade)
