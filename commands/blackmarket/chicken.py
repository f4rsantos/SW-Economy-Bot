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
from services.casino_service import (
    open_chicken_round,
    close_chicken_round_cashout,
    close_chicken_round_crash,
    close_chicken_round_refund,
)
from utils.casino_games import (
    CHICKEN_MAX_STEPS,
    chicken_multiplier_at_step,
    chicken_resolve_step,
    random_loss_message,
)
from utils.casino_session import start_game, end_game

VIEW_TIMEOUT_SECONDS = 90


def _render_lanes(step: int) -> str:
    lanes = []
    for i in range(CHICKEN_MAX_STEPS + 1):
        if i < step:
            lanes.append("〰")
        elif i == step:
            lanes.append("🐔")
        else:
            lanes.append("・")
    return " ".join(lanes)


CHICKEN_ALLOY_MIN_STEP = 3


class ChickenView(discord.ui.View):
    def __init__(self, owner_id: int, faction_id: int, faction_color: int, resource: str, wager: int, res_id: int, edge: float, table_max: int = 0):
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.owner_id = owner_id
        self.faction_id = faction_id
        self.faction_color = faction_color
        self.resource = resource
        self.wager = wager
        self.res_id = res_id
        self.edge = edge
        self.table_max = table_max
        self.step = 0
        self.world_id = None
        self.settled = False
        self._lock = asyncio.Lock()
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(embed=error_embed("Not Allowed", "You cannot interact with someone else's game."), ephemeral=True)
            return False
        return True

    def _current_multiplier(self) -> float:
        return chicken_multiplier_at_step(self.step, self.edge)

    def _next_multiplier(self) -> float:
        return chicken_multiplier_at_step(self.step + 1, self.edge)

    def build_embed(self, footer: str = None) -> discord.Embed:
        current = self._current_multiplier()
        nxt = self._next_multiplier() if self.step < CHICKEN_MAX_STEPS else None
        lines = [_render_lanes(self.step), ""]
        lines.append(f"Current multiplier: {current:.2f}x")
        if nxt is not None:
            lines.append(f"Jump again for: {nxt:.2f}x")
        else:
            lines.append("The chicken has reached the far shore. Cash out now.")
        embed = success_embed(title=f"Chicken Crossing [{self.resource}]", description="\n".join(lines))
        embed.color = self.faction_color
        embed.add_field(name="Wager", value=f"{handle_return(self.wager)} {self.resource}", inline=True)
        embed.add_field(name="Potential Payout", value=f"{handle_return(int(self.wager * current))} {self.resource}", inline=True)
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def _finish(self, embed: discord.Embed, disable: bool = True):
        if disable:
            for child in self.children:
                child.disabled = True
        self.stop()
        if self.message:
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Jump", style=discord.ButtonStyle.green)
    async def jump_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        async with self._lock:
            if self.settled:
                await interaction.response.defer()
                return
            await interaction.response.defer()

            next_step = self.step + 1
            survived = chicken_resolve_step(next_step)

            if not survived:
                self.settled = True
                result = await close_chicken_round_crash(self.resource, self.res_id, self.wager)
                text = f"{_render_lanes(self.step)}\nThe chicken did not make it. You lost {handle_return(self.wager)} {self.resource}.\n{random_loss_message()}"
                embed = error_embed(title=f"Chicken Crossing [{self.resource}], Splat!", description=text)
                embed.color = self.faction_color
                await self._finish(embed)
                return

            self.step = next_step
            if self.step >= CHICKEN_MAX_STEPS:
                self.settled = True
                multiplier = self._current_multiplier()
                result = await close_chicken_round_cashout(
                    self.faction_id, self.world_id, self.resource, self.res_id, self.wager, multiplier,
                    table_max=self.table_max, alloy_eligible=(self.step >= CHICKEN_ALLOY_MIN_STEP),
                )
                text = (
                    f"{_render_lanes(self.step)}\nThe chicken made it all the way across. "
                    f"You cashed out {handle_return(result['payout'])} {self.resource}. "
                    f"Net gain: {handle_return(result['net'])} {self.resource}."
                )
                if result.get('alloys_awarded'):
                    text += f"\nHigh stakes bonus: {result['alloys_awarded']} Alloys."
                embed = success_embed(title=f"Chicken Crossing [{self.resource}], Made it!", description=text)
                embed.color = self.faction_color
                await self._finish(embed)
                return

            embed = self.build_embed()
            if self.message:
                await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.blurple)
    async def cashout_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        async with self._lock:
            if self.settled:
                await interaction.response.defer()
                return
            self.settled = True
            await interaction.response.defer()

            if self.step == 0:
                result = await close_chicken_round_refund(
                    self.faction_id, self.world_id, self.resource, self.res_id, self.wager
                )
                text = f"{_render_lanes(self.step)}\nYou cashed out before the first jump. Your wager was returned."
                embed = success_embed(title=f"Chicken Crossing [{self.resource}]", description=text)
            else:
                multiplier = self._current_multiplier()
                result = await close_chicken_round_cashout(
                    self.faction_id, self.world_id, self.resource, self.res_id, self.wager, multiplier,
                    table_max=self.table_max, alloy_eligible=(self.step >= CHICKEN_ALLOY_MIN_STEP),
                )
                text = (
                    f"{_render_lanes(self.step)}\nYou cashed out {handle_return(result['payout'])} {self.resource}. "
                    f"Net gain: {handle_return(result['net'])} {self.resource}."
                )
                if result.get('alloys_awarded'):
                    text += f"\nHigh stakes bonus: {result['alloys_awarded']} Alloys."
                embed = success_embed(title=f"Chicken Crossing [{self.resource}], Cashed Out!", description=text)
            embed.color = self.faction_color
            await self._finish(embed)

    async def on_timeout(self):
        async with self._lock:
            if self.settled:
                return
            self.settled = True
            if self.step == 0:
                await close_chicken_round_refund(
                    self.faction_id, self.world_id, self.resource, self.res_id, self.wager
                )
                text = f"{_render_lanes(self.step)}\nGame abandoned before the first jump. Your wager was returned."
                embed = success_embed(title=f"Chicken Crossing [{self.resource}], Timed Out", description=text)
            else:
                multiplier = self._current_multiplier()
                result = await close_chicken_round_cashout(
                    self.faction_id, self.world_id, self.resource, self.res_id, self.wager, multiplier,
                    table_max=self.table_max, alloy_eligible=(self.step >= CHICKEN_ALLOY_MIN_STEP),
                )
                text = (
                    f"{_render_lanes(self.step)}\nGame abandoned. Auto cashed out {handle_return(result['payout'])} {self.resource} "
                    f"at the multiplier you had reached."
                )
                if result.get('alloys_awarded'):
                    text += f"\nHigh stakes bonus: {result['alloys_awarded']} Alloys."
                embed = success_embed(title=f"Chicken Crossing [{self.resource}], Timed Out", description=text)
            embed.color = self.faction_color
            for child in self.children:
                child.disabled = True
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except discord.HTTPException:
                    pass
            end_game(self.owner_id)


@app_commands.command(name="chicken", description="Send the chicken across the black market's crossing, one resource at a time")
@app_commands.describe(
    faction="Your faction name",
    amount="Wager for a single resource, e.g. '50k CM'",
    world="World the CM, EL or CS stake comes from (required if wagering those)"
)
@require_access_level(0)
async def chicken_cmd(interaction: discord.Interaction, faction: str, amount: str, world: Optional[str] = None):
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

    if len(wagers) != 1:
        await interaction.followup.send(embed=error_embed("Error", "Chicken Crossing takes exactly one resource per game."))
        return

    resource = wagers[0]['resource']
    stake = wagers[0]['amount']

    world_id = None
    if requires_world(wagers):
        if not world:
            await interaction.followup.send(embed=error_embed("Error", "A world is required when wagering CM, EL or CS."))
            return
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']

    try:
        start_game(interaction.user.id, "chicken")
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e).split(':', 1)[1].strip()))
        return

    try:
        opened = await open_chicken_round(faction_id, world_id, resource, stake)
    except ValueError as e:
        end_game(interaction.user.id)
        await interaction.followup.send(embed=error_embed("Error", str(e).split(':', 1)[-1].strip()))
        return

    view = ChickenView(
        owner_id=interaction.user.id,
        faction_id=faction_id,
        faction_color=faction_color,
        resource=resource,
        wager=stake,
        res_id=opened['res_id'],
        edge=opened['edge'],
        table_max=opened['table_max'],
    )
    view.world_id = world_id

    original_stop = view.stop

    def _stop_and_end():
        end_game(interaction.user.id)
        original_stop()

    view.stop = _stop_and_end

    embed = view.build_embed()
    msg = await interaction.followup.send(embed=embed, view=view, wait=True)
    view.message = msg


async def setup(bot):
    pass
