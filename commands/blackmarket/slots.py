import asyncio
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.validation_service import require_faction, require_world
from services.casino_wager import parse_casino_wager, requires_world
from services.casino_service import get_current_edge, settle_bet
from services.casino_games import SLOT_EMOJI, slot_weights_for_edge, spin_reel, evaluate_slots, random_loss_message
from services.casino_session import start_game, end_game

SPIN_DELAY_SECONDS = 0.9


def _reel_line(symbols):
    return "  ".join(SLOT_EMOJI[s] for s in symbols)


def _render(reel1, reel2, reel3, locked: list[bool]):
    def cell(sym, is_locked):
        return SLOT_EMOJI[sym] if is_locked else "❔"
    return f"[ {cell(reel1, locked[0])} | {cell(reel2, locked[1])} | {cell(reel3, locked[2])} ]"


@app_commands.command(name="slots", description="Pull the lever on the black market's slot machine")
@app_commands.describe(
    faction="Your faction name",
    amount="Wager, e.g. '1m ER 50k CM'",
    world="World the CM, EL or CS stake comes from (required if wagering those)"
)
@require_access_level(0)
async def slots_cmd(interaction: discord.Interaction, faction: str, amount: str, world: Optional[str] = None):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data
    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    try:
        wagers = parse_casino_wager(amount)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    world_id = None
    world_name = None
    if requires_world(wagers):
        if not world:
            await interaction.followup.send(embed=error_embed("Error", "A world is required when wagering CM, EL or CS."))
            return
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']
        world_name = r_world.data['name']

    try:
        start_game(interaction.user.id, "slots")
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e).split(':', 1)[1].strip()))
        return

    try:
        results = []
        for wager in wagers:
            resource = wager['resource']
            stake = wager['amount']
            edge = await get_current_edge(resource)
            weights = slot_weights_for_edge(edge)
            reels = [spin_reel(weights) for _ in range(3)]
            multiplier = evaluate_slots(reels)

            embed = success_embed(title=f"Slots [{resource}]", description=_render(reels[0], reels[1], reels[2], [False, False, False]))
            embed.color = faction_color
            msg = await interaction.followup.send(embed=embed, wait=True)

            for i in range(3):
                await asyncio.sleep(SPIN_DELAY_SECONDS)
                locked = [j <= i for j in range(3)]
                embed = success_embed(title=f"Slots [{resource}]", description=_render(reels[0], reels[1], reels[2], locked))
                embed.color = faction_color
                await msg.edit(embed=embed)

            try:
                settlement = await settle_bet(faction_id, world_id, resource, stake, multiplier)
            except ValueError as e:
                await msg.edit(embed=error_embed("Error", str(e).split(':', 1)[-1].strip()))
                continue

            results.append((resource, settlement, reels))

            if settlement['net'] > 0:
                text = f"{_reel_line(reels)}\nYou won {handle_return(settlement['payout'])} {resource}. Net gain: {handle_return(settlement['net'])} {resource}."
                result_embed = success_embed(title=f"Slots [{resource}], Winner!", description=text)
            elif settlement['net'] == 0:
                text = f"{_reel_line(reels)}\nYour wager was returned. No gain, no loss."
                result_embed = success_embed(title=f"Slots [{resource}]", description=text)
            else:
                text = f"{_reel_line(reels)}\nYou lost {handle_return(stake)} {resource}.\n{random_loss_message()}"
                result_embed = error_embed(title=f"Slots [{resource}]", description=text)
            result_embed.color = faction_color
            await msg.edit(embed=result_embed)
    finally:
        end_game(interaction.user.id)


async def setup(bot):
    pass
