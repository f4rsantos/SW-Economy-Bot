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
from services.casino_wager import parse_casino_wager, requires_world
from services.casino_service import open_blackjack_round, close_blackjack_round
from utils.casino_games import (
    draw_blackjack_card,
    blackjack_card_label,
    blackjack_hand_value,
    blackjack_is_soft,
    blackjack_is_natural,
    blackjack_dealer_should_hit,
    blackjack_resolve,
    blackjack_natural_multiplier,
    random_loss_message,
)
from services.casino_session import start_game, end_game

VIEW_TIMEOUT_SECONDS = 90
DEAL_DELAY_SECONDS = 0.7


def _hand_line(hand: list, hide_second: bool = False) -> str:
    if hide_second and len(hand) >= 2:
        cards = [blackjack_card_label(hand[0]), "🂠"] + [blackjack_card_label(c) for c in hand[2:]]
    else:
        cards = [blackjack_card_label(c) for c in hand]
    return "  ".join(cards)


def _value_label(hand: list) -> str:
    value = blackjack_hand_value(hand)
    if blackjack_is_soft(hand) and value != 21:
        return f"soft {value}"
    return str(value)


class BlackjackView(discord.ui.View):
    def __init__(self, owner_id: int, faction_id: int, faction_color: int, resource: str, wager: int, res_id: int, edge: float):
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.owner_id = owner_id
        self.faction_id = faction_id
        self.faction_color = faction_color
        self.resource = resource
        self.wager = wager
        self.res_id = res_id
        self.edge = edge
        self.world_id = None
        self.player_hand: list = []
        self.dealer_hand: list = []
        self.settled = False
        self._lock = asyncio.Lock()
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(embed=error_embed("Not Allowed", "You cannot interact with someone else's game."), ephemeral=True)
            return False
        return True

    def build_embed(self, footer: str = None, reveal_dealer: bool = False) -> discord.Embed:
        lines = [
            f"Dealer: {_hand_line(self.dealer_hand, hide_second=not reveal_dealer)}"
            + ("" if not reveal_dealer else f"  ({_value_label(self.dealer_hand)})"),
            "",
            f"You: {_hand_line(self.player_hand)}  ({_value_label(self.player_hand)})",
        ]
        embed = success_embed(title=f"Blackjack [{self.resource}]", description="\n".join(lines))
        embed.color = self.faction_color
        embed.add_field(name="Wager", value=f"{handle_return(self.wager)} {self.resource}", inline=True)
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

    async def _play_dealer_and_resolve(self) -> dict:
        while blackjack_dealer_should_hit(self.dealer_hand):
            self.dealer_hand.append(draw_blackjack_card())
        resolution = blackjack_resolve(self.player_hand, self.dealer_hand, self.edge)
        result = await close_blackjack_round(
            self.faction_id, self.world_id, self.resource, self.res_id, self.wager, resolution['multiplier']
        )
        return resolution, result

    def _outcome_embed(self, resolution: dict, result: dict) -> discord.Embed:
        lines = [
            f"Dealer: {_hand_line(self.dealer_hand)}  ({_value_label(self.dealer_hand)})",
            "",
            f"You: {_hand_line(self.player_hand)}  ({_value_label(self.player_hand)})",
            "",
        ]
        outcome = resolution['outcome']
        if outcome in ('win', 'dealer_bust', 'natural'):
            lines.append(f"You won {handle_return(result['payout'])} {self.resource}. Net gain: {handle_return(result['net'])} {self.resource}.")
            embed = success_embed(title=f"Blackjack [{self.resource}], Winner!", description="\n".join(lines))
        elif outcome == 'push':
            lines.append("Push. Your wager was returned. No gain, no loss.")
            embed = success_embed(title=f"Blackjack [{self.resource}]", description="\n".join(lines))
        else:
            lines.append(f"You lost {handle_return(self.wager)} {self.resource}.")
            lines.append(random_loss_message())
            embed = error_embed(title=f"Blackjack [{self.resource}]", description="\n".join(lines))
        embed.color = self.faction_color
        return embed

    async def _settle_and_show(self):
        resolution, result = await self._play_dealer_and_resolve()
        embed = self._outcome_embed(resolution, result)
        await self._finish(embed)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        async with self._lock:
            if self.settled:
                await interaction.response.defer()
                return
            await interaction.response.defer()

            self.player_hand.append(draw_blackjack_card())
            value = blackjack_hand_value(self.player_hand)

            if value >= 21:
                self.settled = True
                await self._settle_and_show()
                return

            embed = self.build_embed()
            if self.message:
                await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.blurple)
    async def stand_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        async with self._lock:
            if self.settled:
                await interaction.response.defer()
                return
            self.settled = True
            await interaction.response.defer()
            await self._settle_and_show()

    async def on_timeout(self):
        async with self._lock:
            if self.settled:
                return
            self.settled = True
            resolution, result = await self._play_dealer_and_resolve()
            embed = self._outcome_embed(resolution, result)
            embed.set_footer(text="Game abandoned. Auto stood and resolved.")
            for child in self.children:
                child.disabled = True
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except discord.HTTPException:
                    pass
            end_game(self.owner_id)


@app_commands.command(name="blackjack", description="Play a hand of blackjack against the black market's dealer")
@app_commands.describe(
    faction="Your faction name",
    amount="Wager for a single resource, e.g. '50k CM'",
    world="World the CM, EL or CS stake comes from (required if wagering those)"
)
@require_access_level(0)
async def blackjack_cmd(interaction: discord.Interaction, faction: str, amount: str, world: Optional[str] = None):
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
        await interaction.followup.send(embed=error_embed("Error", "Blackjack takes exactly one resource per hand."))
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
        start_game(interaction.user.id, "blackjack")
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e).split(':', 1)[1].strip()))
        return

    try:
        opened = await open_blackjack_round(faction_id, world_id, resource, stake)
    except ValueError as e:
        end_game(interaction.user.id)
        await interaction.followup.send(embed=error_embed("Error", str(e).split(':', 1)[-1].strip()))
        return

    view = BlackjackView(
        owner_id=interaction.user.id,
        faction_id=faction_id,
        faction_color=faction_color,
        resource=resource,
        wager=stake,
        res_id=opened['res_id'],
        edge=opened['edge'],
    )
    view.world_id = world_id

    original_stop = view.stop

    def _stop_and_end():
        end_game(interaction.user.id)
        original_stop()

    view.stop = _stop_and_end

    embed = success_embed(title=f"Blackjack [{resource}]", description="Dealing...")
    embed.color = faction_color
    msg = await interaction.followup.send(embed=embed, wait=True)
    view.message = msg

    deal_order = [
        (view.player_hand, False),
        (view.dealer_hand, False),
        (view.player_hand, False),
        (view.dealer_hand, True),
    ]
    for hand, is_dealer_hole_card in deal_order:
        hand.append(draw_blackjack_card())
        await asyncio.sleep(DEAL_DELAY_SECONDS)
        embed = view.build_embed()
        await msg.edit(embed=embed)

    player_natural = blackjack_is_natural(view.player_hand)
    dealer_natural = blackjack_is_natural(view.dealer_hand)

    if player_natural or dealer_natural:
        view.settled = True
        if player_natural and dealer_natural:
            resolution = {'outcome': 'push', 'multiplier': 1.0}
        elif player_natural:
            resolution = {'outcome': 'natural', 'multiplier': blackjack_natural_multiplier(view.edge)}
        else:
            resolution = {'outcome': 'loss', 'multiplier': 0.0}
        result = await close_blackjack_round(
            faction_id, world_id, resource, opened['res_id'], stake, resolution['multiplier']
        )
        embed = view._outcome_embed(resolution, result)
        for child in view.children:
            child.disabled = True
        view.stop()
        await msg.edit(embed=embed, view=view)
        return

    embed = view.build_embed()
    await msg.edit(embed=embed, view=view)


async def setup(bot):
    pass
