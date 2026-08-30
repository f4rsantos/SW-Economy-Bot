# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.validation_service import require_faction, require_world
from utils.casino_wager import parse_casino_wager, requires_world
from services.casino_service import get_current_edge, settle_bet
from utils.casino_games import (
    DICE_EMOJI,
    roll_die,
    dice_payout_multiplier,
    dice_roll_animation_frames,
    random_loss_message,
)
from utils.casino_session import start_game, end_game

ROLL_DELAY_SECONDS = 0.6

BET_CHOICES = [
    app_commands.Choice(name="High (4, 5 or 6)", value="high"),
    app_commands.Choice(name="Low (1, 2 or 3)", value="low"),
    app_commands.Choice(name="Exact number", value="exact"),
]


def _render(face: int) -> str:
    return f"[ {DICE_EMOJI[face]} ]"


@app_commands.command(name="dice", description="Wager on a roll of the black market's dice")
@app_commands.describe(
    faction="Your faction name",
    amount="Wager, e.g. '1m ER 50k CM'",
    bet_type="What you are betting on",
    number="Exact face value (1 to 6), required for an exact bet",
    world="World the CM, EL or CS stake comes from (required if wagering those)"
)
@app_commands.choices(bet_type=BET_CHOICES)
@require_access_level(0)
async def dice_cmd(
    interaction: discord.Interaction,
    faction: str,
    amount: str,
    bet_type: app_commands.Choice[str],
    number: Optional[int] = None,
    world: Optional[str] = None,
):
    await interaction.response.defer()

    if bet_type.value == 'exact':
        if number is None or not (1 <= number <= 6):
            await interaction.followup.send(embed=error_embed("Error", "An exact bet needs a face value from 1 to 6."))
            return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data
    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

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
        start_game(interaction.user.id, "dice")
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e).split(':', 1)[1].strip()))
        return

    try:
        for wager in wagers:
            resource = wager['resource']
            stake = wager['amount']
            edge = await get_current_edge(resource)
            face = roll_die()
            multiplier = dice_payout_multiplier(bet_type.value, number, face, edge)
            frames = dice_roll_animation_frames(face)

            embed = success_embed(title=f"Dice [{resource}]", description=_render(frames[0]))
            embed.color = faction_color
            msg = await interaction.followup.send(embed=embed, wait=True)

            for frame in frames[1:]:
                await asyncio.sleep(ROLL_DELAY_SECONDS)
                embed = success_embed(title=f"Dice [{resource}]", description=_render(frame))
                embed.color = faction_color
                await msg.edit(embed=embed)

            try:
                settlement = await settle_bet(faction_id, world_id, resource, stake, multiplier)
            except ValueError as e:
                await msg.edit(embed=error_embed("Error", str(e).split(':', 1)[-1].strip()))
                continue

            landed = f"The die landed on {face}."
            if settlement['net'] > 0:
                text = f"{landed}\nYou won {handle_return(settlement['payout'])} {resource}. Net gain: {handle_return(settlement['net'])} {resource}."
                if settlement['alloys_awarded']:
                    text += f"\nHigh stakes bonus: {settlement['alloys_awarded']} Alloys."
                result_embed = success_embed(title=f"Dice [{resource}], Winner!", description=text)
            elif settlement['net'] == 0:
                text = f"{landed}\nYour wager was returned. No gain, no loss."
                result_embed = success_embed(title=f"Dice [{resource}]", description=text)
            else:
                text = f"{landed}\nYou lost {handle_return(stake)} {resource}.\n{random_loss_message()}"
                result_embed = error_embed(title=f"Dice [{resource}]", description=text)
            result_embed.color = faction_color
            await msg.edit(embed=result_embed)
    finally:
        end_game(interaction.user.id)


async def setup(bot):
    pass
