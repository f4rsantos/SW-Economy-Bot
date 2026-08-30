# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
import random
from typing import Optional
from utils.embeds import success_embed, error_embed
from utils.checks import require_access_level



def check_winner(board) -> int:
    for row in board:
        if row[0] == row[1] == row[2] != 0:
            return row[0]
    for col in range(3):
        if board[0][col] == board[1][col] == board[2][col] != 0:
            return board[0][col]
    if board[0][0] == board[1][1] == board[2][2] != 0:
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != 0:
        return board[0][2]
    return 0


def is_full(board) -> bool:
    return all(board[y][x] != 0 for y in range(3) for x in range(3))


def minimax(board, depth: int, is_maximizing: bool) -> int:
    winner = check_winner(board)
    if winner == 2:
        return 10 - depth
    if winner == 1:
        return depth - 10
    if is_full(board):
        return 0
    if is_maximizing:
        best = -1000
        for y in range(3):
            for x in range(3):
                if board[y][x] == 0:
                    board[y][x] = 2
                    best = max(best, minimax(board, depth + 1, False))
                    board[y][x] = 0
        return best
    else:
        best = 1000
        for y in range(3):
            for x in range(3):
                if board[y][x] == 0:
                    board[y][x] = 1
                    best = min(best, minimax(board, depth + 1, True))
                    board[y][x] = 0
        return best


def make_ai_move(board):
    best_score, best_move = -1000, None
    for y in range(3):
        for x in range(3):
            if board[y][x] == 0:
                board[y][x] = 2
                score = minimax(board, 0, False)
                board[y][x] = 0
                if score > best_score:
                    best_score, best_move = score, (x, y)
    return best_move



class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if interaction.user.id != view.current_player_id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        if view.game_over:
            await interaction.response.send_message("Game is already over!", ephemeral=True)
            return
        if view.board[self.y][self.x] != 0:
            await interaction.response.send_message("That spot is taken!", ephemeral=True)
            return

        player_num = 1 if interaction.user.id == view.player1_id else 2
        view.board[self.y][self.x] = player_num
        self.style = discord.ButtonStyle.primary if player_num == 1 else discord.ButtonStyle.danger
        self.label = 'X' if player_num == 1 else 'O'
        self.disabled = True

        winner = check_winner(view.board)
        if winner:
            view.game_over = True
            view.disable_all()
            if view.is_vs_ai and winner == 1:
                await interaction.response.edit_message(
                    embed=success_embed("You Win!", "Congratulations!"), view=view
                )
            elif view.is_vs_ai and winner == 2:
                await interaction.response.edit_message(
                    embed=error_embed("You Lose!", "AI wins! Better luck next time."), view=view
                )
            else:
                winner_name = view.player1_name if winner == 1 else view.player2_name
                await interaction.response.edit_message(
                    embed=success_embed(f"{winner_name} Wins!", "Congratulations!"), view=view
                )
            return

        if is_full(view.board):
            view.game_over = True
            view.disable_all()
            await interaction.response.edit_message(
                embed=success_embed("Tie!", "It's a draw!"), view=view
            )
            return

        if view.is_vs_ai:
            move = make_ai_move(view.board)
            if move:
                ax, ay = move
                view.board[ay][ax] = 2
                for child in view.children:
                    if isinstance(child, TicTacToeButton) and child.x == ax and child.y == ay:
                        child.label = 'O'
                        child.style = discord.ButtonStyle.danger
                        child.disabled = True
                        break
                if check_winner(view.board) == 2:
                    view.game_over = True
                    view.disable_all()
                    await interaction.response.edit_message(
                        embed=error_embed("You Lose!", "AI wins! Better luck next time."), view=view
                    )
                    return
                if is_full(view.board):
                    view.game_over = True
                    view.disable_all()
                    await interaction.response.edit_message(
                        embed=success_embed("Tie!", "It's a draw!"), view=view
                    )
                    return
            await interaction.response.edit_message(
                embed=view.make_embed(f"Your turn, {view.player1_name}!"), view=view
            )
        else:
            view.current_player_id = view.player2_id if player_num == 1 else view.player1_id
            next_name = view.player2_name if player_num == 1 else view.player1_name
            await interaction.response.edit_message(
                embed=view.make_embed(f"Your turn, {next_name}!"), view=view
            )



class TicTacToeView(discord.ui.View):
    def __init__(self, player1_id: int, player1_name: str,
                 player2_id: int, player2_name: str, is_vs_ai: bool):
        super().__init__(timeout=300)
        self.player1_id = player1_id
        self.player1_name = player1_name
        self.player2_id = player2_id
        self.player2_name = player2_name
        self.is_vs_ai = is_vs_ai
        self.current_player_id = player1_id
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self.game_over = False
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def make_embed(self, turn_msg: str) -> discord.Embed:
        return discord.Embed(
            title="TicTacToe",
            description=(
                f"{self.player1_name} = **X**  |  {self.player2_name} = **O**\n\n{turn_msg}"
            ),
            color=0x00ff00
        )

    def disable_all(self):
        for child in self.children:
            child.disabled = True



@app_commands.command(name="tictactoe", description="Play TicTacToe vs AI or a friend")
@app_commands.describe(opponent="Challenge another player (leave empty to play vs AI)")
@require_access_level(0)
async def tictactoe(interaction: discord.Interaction, opponent: Optional[discord.Member] = None):
    await interaction.response.defer()

    is_vs_ai = opponent is None
    p1_id   = interaction.user.id
    p1_name = interaction.user.display_name

    if is_vs_ai:
        p2_id   = interaction.client.user.id
        p2_name = "AI"
    else:
        if opponent.id == p1_id:
            await interaction.followup.send("You can't challenge yourself!", ephemeral=True)
            return
        if opponent.bot:
            await interaction.followup.send("You can't challenge a bot!", ephemeral=True)
            return
        p2_id   = opponent.id
        p2_name = opponent.display_name

    view = TicTacToeView(p1_id, p1_name, p2_id, p2_name, is_vs_ai)

    if is_vs_ai and random.choice([True, False]):
        move = make_ai_move(view.board)
        if move:
            ax, ay = move
            view.board[ay][ax] = 2
            for child in view.children:
                if isinstance(child, TicTacToeButton) and child.x == ax and child.y == ay:
                    child.label = 'O'
                    child.style = discord.ButtonStyle.danger
                    child.disabled = True
                    break
        turn_msg = f"AI went first! Your turn, {p1_name}."
    else:
        turn_msg = f"Your turn, {p1_name}!" if is_vs_ai else f"Your turn, {p1_name}!"

    embed = view.make_embed(turn_msg)
    if not is_vs_ai:
        embed.set_footer(text=f"Challenged: {p2_name}")
    await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    bot.tree.add_command(tictactoe)
