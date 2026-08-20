import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.validation_service import require_faction
from services.blackmarket_service import sell_alloys


@app_commands.command(name="sell", description="Sell Alloys to the pirates and expect to get shortchanged")
@app_commands.describe(
    faction="Your faction name",
    quantity="Number of Alloys to sell (default 1)"
)
@require_access_level(0)
async def sell_cmd(interaction: discord.Interaction, faction: str, quantity: int = 1):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    if quantity < 1:
        await interaction.followup.send(embed=error_embed("Error", "Quantity must be at least 1."))
        return

    try:
        result = await sell_alloys(faction_id, quantity)
    except ValueError as e:
        msg = str(e)
        if 'RESOURCE_INSUFFICIENT' in msg or 'RESOURCE_NOT_FOUND' in msg or 'NO_WORLD' in msg:
            await interaction.followup.send(embed=error_embed("Error", msg.split(':', 1)[1].strip()))
        else:
            await interaction.followup.send(embed=error_embed("Error", msg))
        return

    payout_str = ", ".join(f"{handle_return(amount)} {res}" for res, amount in result['payout'].items())
    embed = success_embed(
        title="Alloys Sold",
        description=(
            f"**{faction_data['display_name']}** sold {quantity} Alloys to the black market for {payout_str}.\n"
            f"The pirates shortchanged you, as usual.\n"
            f"Holdings: {result['held_before']} -> {result['held_after']}"
        ),
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)
