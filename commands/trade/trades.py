import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.trade_service import get_faction_trades
from services.validation_service import require_faction


def _format_world_route(trade) -> str:
    if trade['sender_world'] or trade['receiver_world']:
        sw = trade['sender_world'] or '?'
        rw = trade['receiver_world'] or '?'
        return f" ({sw} → {rw})"
    return ""


@app_commands.command(name="list", description="View faction's trade deals")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def trades(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']

    trades_data = await get_faction_trades(faction_id)
    outgoing = trades_data['outgoing']
    incoming = trades_data['incoming']

    if not outgoing and not incoming:
        await interaction.followup.send(embed=error_embed("No Trades", f"{faction_data['display_name']} has no active trade deals."))
        return

    embed = discord.Embed(title=f"Trade Deals - {faction_data['display_name']}", color=hex_to_int(faction_data['color']))

    if outgoing:
        lines = [f"**ID {t['id']}:** {t['amount']:,} {t['resource_name']} → {t['receiver_name']}{_format_world_route(t)}" for t in outgoing[:10]]
        embed.add_field(name=f"Outgoing ({len(outgoing)})", value="\n".join(lines), inline=False)
        if len(outgoing) > 10:
            embed.add_field(name="...", value=f"and {len(outgoing) - 10} more", inline=False)

    if incoming:
        lines = [f"**ID {t['id']}:** {t['amount']:,} {t['resource_name']} from {t['sender_name']}{_format_world_route(t)}" for t in incoming[:10]]
        embed.add_field(name=f"Incoming ({len(incoming)})", value="\n".join(lines), inline=False)
        if len(incoming) > 10:
            embed.add_field(name="...", value=f"and {len(incoming) - 10} more", inline=False)

    embed.set_footer(text="Use /end-trade <id> to cancel a trade")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(trades)
