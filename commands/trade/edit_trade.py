# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.currency import parse_single_amount, handle_return
from services.trade_service import get_trade, edit_trade as edit_trade_service, validate_world_for_trade
from services.validation_service import require_faction
from database.static_cache import static_cache


MAX_TRADE_AMOUNT = 1_000_000_000_000_000


@app_commands.command(name="edit", description="Edit a recurring trade")
@app_commands.describe(
    trade_id="Trade ID to edit",
    to_faction="New receiving faction",
    amount="New amount and resource per income cycle, e.g. '10k CM', '2.5mil ER'",
    from_world="New source world",
    to_world="New destination world"
)
@require_access_level(0)
async def edit_trade(interaction: discord.Interaction, trade_id: int, to_faction: str = None, amount: str = None, from_world: str = None, to_world: str = None):
    await interaction.response.defer()

    if not any([to_faction, amount, from_world, to_world]):
        await interaction.followup.send(embed=error_embed("Error", "Provide at least one field to edit."))
        return

    trade = await get_trade(trade_id)
    if not trade:
        await interaction.followup.send(embed=error_embed("Error", "Trade not found."))
        return

    receiver_faction_id = None
    if to_faction:
        r_receiver_data = await require_faction(to_faction)
        if not r_receiver_data.ok:
            await interaction.followup.send(embed=error_embed("Error", r_receiver_data.error))
            return
        receiver_faction_id = r_receiver_data.data.id

    resource_id = None
    parsed_amount = None
    if amount:
        try:
            parsed_amount, resource_name = parse_single_amount(amount)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

        resource_data = static_cache.get_resource(resource_name)
        if not resource_data:
            await interaction.followup.send(embed=error_embed("Error", f"Resource '{resource_name}' not found."))
            return
        resource_id = resource_data['id']

        if parsed_amount <= 0:
            await interaction.followup.send(embed=error_embed("Error", "Amount must be positive."))
            return
        if parsed_amount > MAX_TRADE_AMOUNT:
            await interaction.followup.send(embed=error_embed("Error", f"Amount is too large. Maximum is {handle_return(MAX_TRADE_AMOUNT)}."))
            return

    sender_world_id = None
    if from_world:
        try:
            sender_world_id = await validate_world_for_trade(from_world, trade.sender_faction_id)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

    receiver_world_id = None
    if to_world:
        target_receiver_id = receiver_faction_id if receiver_faction_id is not None else trade.receiver_faction_id
        try:
            receiver_world_id = await validate_world_for_trade(to_world, target_receiver_id)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

    try:
        updated = await edit_trade_service(
            trade_id,
            receiver_faction_id=receiver_faction_id,
            resource_id=resource_id,
            amount=parsed_amount,
            sender_world_id=sender_world_id,
            receiver_world_id=receiver_world_id,
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    route_line = ""
    if updated.sender_world or updated.receiver_world:
        sw = updated.sender_world or "Capital"
        rw = updated.receiver_world or "Capital"
        route_line = f"**Route:** {sw} → {rw}\n"

    embed = success_embed(
        "Trade Deal Updated",
        f"**{updated.sender_name}** → **{updated.receiver_name}**\n\n"
        f"**Resource:** {updated.resource_name}\n"
        f"**Amount:** {handle_return(updated.amount)} per income cycle\n"
        f"{route_line}"
        f"**Trade ID:** {updated.id}"
    )
    embed.color = hex_to_int(updated.sender_color)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(edit_trade)
