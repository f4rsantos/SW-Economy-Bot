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
from utils.casino_games import SLOT_EMOJI, SLOT_SYMBOLS, slot_weights_for_edge, spin_reel, evaluate_slots, random_loss_message
from utils.casino_session import start_game, end_game

SPIN_FRAME_SECONDS = 0.28
FRAMES_BEFORE_FIRST_LOCK = 4
FRAMES_BETWEEN_LOCKS = 3


def _reel_line(symbols):
    return "  ".join(SLOT_EMOJI[s] for s in symbols)


def _render(reels, locked: list[bool], tick: int):
    def cell(index):
        if locked[index]:
            return SLOT_EMOJI[reels[index]]
        spinning = SLOT_SYMBOLS[(tick + index * 3) % len(SLOT_SYMBOLS)]
        return SLOT_EMOJI[spinning]
    return f"[ {cell(0)} | {cell(1)} | {cell(2)} ]"


def _spin_frames():
    frames = []
    tick = 0
    for locked_count in range(4):
        held = FRAMES_BEFORE_FIRST_LOCK if locked_count == 0 else FRAMES_BETWEEN_LOCKS
        if locked_count == 3:
            held = 1
        for _ in range(held):
            frames.append(([j < locked_count for j in range(3)], tick))
            tick += 1
    return frames


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
    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

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

            frames = _spin_frames()
            first_locked, first_tick = frames[0]
            embed = success_embed(title=f"Slots [{resource}]", description=_render(reels, first_locked, first_tick))
            embed.color = faction_color
            msg = await interaction.followup.send(embed=embed, wait=True)

            for locked, tick in frames[1:]:
                await asyncio.sleep(SPIN_FRAME_SECONDS)
                embed = success_embed(title=f"Slots [{resource}]", description=_render(reels, locked, tick))
                embed.color = faction_color
                try:
                    await msg.edit(embed=embed)
                except discord.HTTPException:
                    break

            try:
                settlement = await settle_bet(faction_id, world_id, resource, stake, multiplier)
            except ValueError as e:
                await msg.edit(embed=error_embed("Error", str(e).split(':', 1)[-1].strip()))
                continue

            results.append((resource, settlement, reels))

            if settlement['net'] > 0:
                text = f"{_reel_line(reels)}\nYou won {handle_return(settlement['payout'])} {resource}. Net gain: {handle_return(settlement['net'])} {resource}."
                if settlement['alloys_awarded']:
                    text += f"\nHigh stakes bonus: {settlement['alloys_awarded']} Alloys."
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
