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
from services.casino_games import (
    roulette_payout_multiplier,
    spin_roulette,
    roulette_color,
    roulette_animation_frames,
    random_loss_message,
)
from services.casino_session import start_game, end_game

SPIN_DELAY_SECONDS = 0.6

POCKET_EMOJI_RED = "🟥"
POCKET_EMOJI_BLACK = "⬛"
POCKET_EMOJI_GREEN = "🟩"


def _pocket_symbol(pocket: int) -> str:
    color = roulette_color(pocket)
    if color == 'GREEN':
        return f"{POCKET_EMOJI_GREEN}{pocket}"
    if color == 'RED':
        return f"{POCKET_EMOJI_RED}{pocket}"
    return f"{POCKET_EMOJI_BLACK}{pocket}"


def _render_window(window: list[int]) -> str:
    cells = [_pocket_symbol(p) for p in window]
    cells[2] = f"[ {cells[2]} ]"
    return "  ".join(cells)


BET_CHOICES = [
    app_commands.Choice(name="Straight (single number)", value="straight"),
    app_commands.Choice(name="Red", value="red"),
    app_commands.Choice(name="Black", value="black"),
    app_commands.Choice(name="Odd", value="odd"),
    app_commands.Choice(name="Even", value="even"),
]


@app_commands.command(name="roulette", description="Spin the black market's roulette wheel")
@app_commands.describe(
    faction="Your faction name",
    amount="Wager, e.g. '1m ER 50k CM'",
    bet_type="What you are betting on",
    number="Pocket number (0 to 36), required for a straight bet",
    world="World the CM, EL or CS stake comes from (required if wagering those)"
)
@app_commands.choices(bet_type=BET_CHOICES)
@require_access_level(0)
async def roulette_cmd(
    interaction: discord.Interaction,
    faction: str,
    amount: str,
    bet_type: app_commands.Choice[str],
    number: Optional[int] = None,
    world: Optional[str] = None,
):
    await interaction.response.defer()

    if bet_type.value == 'straight':
        if number is None or not (0 <= number <= 36):
            await interaction.followup.send(embed=error_embed("Error", "A straight bet needs a pocket number from 0 to 36."))
            return

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
    if requires_world(wagers):
        if not world:
            await interaction.followup.send(embed=error_embed("Error", "A world is required when wagering CM, EL or CS."))
            return
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']

    try:
        start_game(interaction.user.id, "roulette")
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e).split(':', 1)[1].strip()))
        return

    try:
        for wager in wagers:
            resource = wager['resource']
            stake = wager['amount']
            edge = await get_current_edge(resource)
            pocket = spin_roulette()
            multiplier = roulette_payout_multiplier(bet_type.value, number, pocket, edge)
            frames = roulette_animation_frames(pocket)

            embed = success_embed(title=f"Roulette [{resource}]", description=_render_window(frames[0]))
            embed.color = faction_color
            msg = await interaction.followup.send(embed=embed, wait=True)

            for frame in frames[1:]:
                await asyncio.sleep(SPIN_DELAY_SECONDS)
                embed = success_embed(title=f"Roulette [{resource}]", description=_render_window(frame))
                embed.color = faction_color
                await msg.edit(embed=embed)

            try:
                settlement = await settle_bet(faction_id, world_id, resource, stake, multiplier)
            except ValueError as e:
                await msg.edit(embed=error_embed("Error", str(e).split(':', 1)[-1].strip()))
                continue

            color = roulette_color(pocket)
            landed = f"Ball landed on {pocket} ({color})."
            if settlement['net'] > 0:
                text = f"{landed}\nYou won {handle_return(settlement['payout'])} {resource}. Net gain: {handle_return(settlement['net'])} {resource}."
                result_embed = success_embed(title=f"Roulette [{resource}], Winner!", description=text)
            elif settlement['net'] == 0:
                text = f"{landed}\nYour wager was returned. No gain, no loss."
                result_embed = success_embed(title=f"Roulette [{resource}]", description=text)
            else:
                text = f"{landed}\nYou lost {handle_return(stake)} {resource}.\n{random_loss_message()}"
                result_embed = error_embed(title=f"Roulette [{resource}]", description=text)
            result_embed.color = faction_color
            await msg.edit(embed=result_embed)
    finally:
        end_game(interaction.user.id)


async def setup(bot):
    pass
