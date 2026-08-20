import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import log_embed, error_embed, manifest_block
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.validation_service import require_faction
from services.blackmarket_service import get_alloys_held, buy_price_for_tier, ALLOY_HOLD_CAP, SELL_PAYOUT_BASE


@app_commands.command(name="view", description="Check the black market's current Alloy prices for your faction")
@app_commands.describe(faction="Your faction name")
@require_access_level(0)
async def view_cmd(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    held = await get_alloys_held(faction_id)
    can_buy = max(ALLOY_HOLD_CAP - held, 0)

    if can_buy > 0:
        next_price = buy_price_for_tier(held)
        buy_line = f"`{handle_return(next_price)}` each of CM, EL, CS"
    else:
        buy_line = "`Refused, holdings at cap`"

    table_rows = [
        ["Held", str(held)],
        ["Cap", str(ALLOY_HOLD_CAP)],
        ["Can buy", str(can_buy)],
    ]

    embed = log_embed(
        title="Black Market -- Alloys",
        subtitle=f"ACCOUNT // {faction_data['display_name']}",
        color=faction_color,
        description=manifest_block(table_rows, headers=["STAT", "VALUE"], align=['<', '>']),
        fields=[
            {'name': "Next Buy Price", 'value': buy_line, 'inline': True},
            {'name': "Sell Payout", 'value': f"`{handle_return(round(SELL_PAYOUT_BASE * 0.9))}-{handle_return(SELL_PAYOUT_BASE)}` each of CM, EL, CS", 'inline': True},
        ],
    )
    await interaction.followup.send(embed=embed)
