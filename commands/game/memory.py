# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import logging
import discord
from discord import app_commands
import random
from typing import List, Optional
from utils.embeds import success_embed, error_embed
from utils.checks import require_access_level
from services.game_service import set_high_score_if_higher

logger = logging.getLogger(__name__)

_EMOJIS = ['🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🫐']
_PTS_CORRECT = 10
_PTS_WRONG = 3


class MemoryButton(discord.ui.Button):
    def __init__(self, emoji: str, position: int):
        super().__init__(style=discord.ButtonStyle.secondary, emoji='❓', row=position // 4)
        self.fruit_emoji = emoji
        self.position = position
        self.revealed = False

    async def callback(self, interaction: discord.Interaction):
        view: MemoryView = self.view
        if interaction.user.id != view.player_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        if view.game_over or self.revealed:
            await interaction.response.send_message("Can't select that!", ephemeral=True)
            return

        if len(view.revealed_positions) >= 2:
            for pos in view.revealed_positions:
                btn = view.get_button(pos)
                if btn and not view.matched_positions.get(pos):
                    btn.emoji = '❓'
                    btn.style = discord.ButtonStyle.secondary
                    btn.revealed = False
            view.revealed_positions = []

        self.emoji = self.fruit_emoji
        self.style = discord.ButtonStyle.primary
        self.revealed = True
        view.revealed_positions.append(self.position)
        view.moves += 1

        if len(view.revealed_positions) == 2:
            p1, p2 = view.revealed_positions
            b1, b2 = view.get_button(p1), view.get_button(p2)
            if b1.fruit_emoji == b2.fruit_emoji:
                view.matches += 1
                view.score += _PTS_CORRECT
                for p, b in [(p1, b1), (p2, b2)]:
                    view.matched_positions[p] = True
                    b.style = discord.ButtonStyle.success
                    b.disabled = True
                if view.matches == 8:
                    view.game_over = True
                    await view.save_score(view.score)
                    await interaction.response.edit_message(
                        embed=success_embed(f"**Score:** {view.score}\n**Moves:** {view.moves}", "You Win!"),
                        view=view
                    )
                    return
            else:
                view.score -= _PTS_WRONG

        embed = discord.Embed(
            title="Memory Game",
            description=f"**Score:** {view.score}\n**Matches:** {view.matches}/8\n**Moves:** {view.moves}",
            color=0x00ff00
        )
        embed.set_footer(text=f"Match pairs: +{_PTS_CORRECT} pts | Wrong guess: -{_PTS_WRONG} pts")
        await interaction.response.edit_message(embed=embed, view=view)


class MemoryView(discord.ui.View):
    def __init__(self, player_id: int):
        super().__init__(timeout=600)
        self.player_id = player_id
        self.score = 0
        self.moves = 0
        self.matches = 0
        self.game_over = False
        self.revealed_positions: List[int] = []
        self.matched_positions: dict = {}
        cards = _EMOJIS + _EMOJIS
        random.shuffle(cards)
        for i, emoji in enumerate(cards):
            self.add_item(MemoryButton(emoji, i))

    def get_button(self, position: int) -> Optional[MemoryButton]:
        for child in self.children:
            if isinstance(child, MemoryButton) and child.position == position:
                return child
        return None

    async def save_score(self, score: int):
        try:
            await set_high_score_if_higher('memory', self.player_id, score)
        except Exception as e:
            logger.error(f"Error saving Memory score: {e}")


@app_commands.command(name="memory", description="Play Memory matching game")
@require_access_level(0)
async def memory(interaction: discord.Interaction):
    await interaction.response.defer()
    view = MemoryView(interaction.user.id)
    embed = discord.Embed(
        title="Memory Game",
        description="**Score:** 0\n**Matches:** 0/8\n**Moves:** 0",
        color=0x00ff00
    )
    embed.set_footer(text=f"Match pairs: +{_PTS_CORRECT} pts | Wrong guess: -{_PTS_WRONG} pts")
    await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    bot.tree.add_command(memory)
