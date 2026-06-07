import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.trade_service import begin_trade as begin_trade_service, validate_world_for_trade
from database.static_cache import static_cache
from services.validation_service import require_faction


@app_commands.command(name="begin", description="Create recurring trade")
@app_commands.describe(
    sender="Sending faction",
    receiver="Receiving faction",
    resource="Resource to trade",
    amount="Amount per income cycle",
    from_world="Optional: Specific source world",
    to_world="Optional: Specific destination world"
)
@require_access_level(0)
async def begin_trade(interaction: discord.Interaction, sender: str, receiver: str, resource: str, amount: int, from_world: str = None, to_world: str = None):
    await interaction.response.defer()

    r_sender_data, r_receiver_data = await asyncio.gather(
        require_faction(sender),
        require_faction(receiver)
    )
    if not r_sender_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_sender_data.error))
    sender_data = r_sender_data.data
    if not r_receiver_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_receiver_data.error))
    receiver_data = r_receiver_data.data

    resource_data = static_cache.get_resource(resource)
    if not resource_data:
        await interaction.followup.send(embed=error_embed("Error", "Resource not found."))
        return

    if amount <= 0:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be positive."))
        return

    sender_world_id = None
    if from_world:
        try:
            sender_world_id = await validate_world_for_trade(from_world, sender_data['id'])
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

    receiver_world_id = None
    if to_world:
        try:
            receiver_world_id = await validate_world_for_trade(to_world, receiver_data['id'])
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

    trade_id = await begin_trade_service(
        sender_data['id'], receiver_data['id'], resource_data['id'], amount, sender_world_id, receiver_world_id
    )

    embed = success_embed(
        "Trade Deal Created",
        f"**{sender_data['display_name']}** → **{receiver_data['display_name']}**\n\n"
        f"**Resource:** {resource_data['name']}\n"
        f"**Amount:** {amount:,} per income cycle\n"
        f"**Trade ID:** {trade_id}\n\n"
        f"This trade will execute automatically during each income cycle."
    )
    embed.color = hex_to_int(sender_data['color'])
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(begin_trade)
