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

ROWS = 6
COLS = 7
EMPTY = 0
P1 = 1
P2 = 2

DISC_P1   = '🔴'
DISC_P2   = '🟡'
DISC_EMPTY = '⚫'

COL_LABELS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣']



def make_board():
    return [[EMPTY] * COLS for _ in range(ROWS)]


def drop_piece(board, col: int, player: int) -> int:
                                                                 
    for row in range(ROWS - 1, -1, -1):
        if board[row][col] == EMPTY:
            board[row][col] = player
            return row
    return -1


def check_winner(board) -> int:
    for r in range(ROWS):
        for c in range(COLS - 3):
            if board[r][c] != EMPTY and board[r][c] == board[r][c+1] == board[r][c+2] == board[r][c+3]:
                return board[r][c]
    for r in range(ROWS - 3):
        for c in range(COLS):
            if board[r][c] != EMPTY and board[r][c] == board[r+1][c] == board[r+2][c] == board[r+3][c]:
                return board[r][c]
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            if board[r][c] != EMPTY and board[r][c] == board[r+1][c+1] == board[r+2][c+2] == board[r+3][c+3]:
                return board[r][c]
    for r in range(3, ROWS):
        for c in range(COLS - 3):
            if board[r][c] != EMPTY and board[r][c] == board[r-1][c+1] == board[r-2][c+2] == board[r-3][c+3]:
                return board[r][c]
    return 0


def is_full(board) -> bool:
    return all(board[0][c] != EMPTY for c in range(COLS))


def valid_cols(board):
    return [c for c in range(COLS) if board[0][c] == EMPTY]


def render_board(board) -> str:
    rows = []
    for r in range(ROWS):
        row_str = ''
        for c in range(COLS):
            if board[r][c] == P1:
                row_str += DISC_P1
            elif board[r][c] == P2:
                row_str += DISC_P2
            else:
                row_str += DISC_EMPTY
        rows.append(row_str)
    rows.append(''.join(COL_LABELS))
    return '\n'.join(rows)



def score_window(window, player):
    opp = P1 if player == P2 else P2
    score = 0
    if window.count(player) == 4:
        score += 100
    elif window.count(player) == 3 and window.count(EMPTY) == 1:
        score += 5
    elif window.count(player) == 2 and window.count(EMPTY) == 2:
        score += 2
    if window.count(opp) == 3 and window.count(EMPTY) == 1:
        score -= 4
    return score


def score_board(board, player):
    score = 0
    centre = [board[r][COLS // 2] for r in range(ROWS)]
    score += centre.count(player) * 3
    for r in range(ROWS):
        for c in range(COLS - 3):
            score += score_window([board[r][c+i] for i in range(4)], player)
    for c in range(COLS):
        for r in range(ROWS - 3):
            score += score_window([board[r+i][c] for i in range(4)], player)
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            score += score_window([board[r+i][c+i] for i in range(4)], player)
    for r in range(3, ROWS):
        for c in range(COLS - 3):
            score += score_window([board[r-i][c+i] for i in range(4)], player)
    return score


def minimax(board, depth, alpha, beta, maximizing):
    w = check_winner(board)
    if w == P2:
        return (None, 100000 + depth)
    if w == P1:
        return (None, -100000 - depth)
    if is_full(board) or depth == 0:
        return (None, score_board(board, P2))
    cols = valid_cols(board)
    best_col = random.choice(cols)
    if maximizing:
        value = -float('inf')
        for c in cols:
            import copy
            b2 = copy.deepcopy(board)
            drop_piece(b2, c, P2)
            _, s = minimax(b2, depth - 1, alpha, beta, False)
            if s > value:
                value, best_col = s, c
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return best_col, value
    else:
        value = float('inf')
        for c in cols:
            import copy
            b2 = copy.deepcopy(board)
            drop_piece(b2, c, P1)
            _, s = minimax(b2, depth - 1, alpha, beta, True)
            if s < value:
                value, best_col = s, c
            beta = min(beta, value)
            if alpha >= beta:
                break
        return best_col, value


def ai_move(board) -> int:
    col, _ = minimax(board, 4, -float('inf'), float('inf'), True)
    return col



class ColButton(discord.ui.Button):
    def __init__(self, col: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=str(col + 1),
            row=col // 4,
            custom_id=f"c4_col_{col}"
        )
        self.col = col

    async def callback(self, interaction: discord.Interaction):
        view: Connect4View = self.view
        if interaction.user.id != view.current_player_id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        if view.game_over:
            await interaction.response.send_message("Game is already over!", ephemeral=True)
            return
        if view.board[0][self.col] != EMPTY:
            await interaction.response.send_message("That column is full!", ephemeral=True)
            return

        player_num = P1 if interaction.user.id == view.player1_id else P2
        drop_piece(view.board, self.col, player_num)
        view.refresh_buttons()

        winner = check_winner(view.board)
        if winner:
            view.game_over = True
            view.disable_all()
            winner_name = view.player1_name if winner == P1 else view.player2_name
            embed = discord.Embed(
                title="Connect 4",
                description=render_board(view.board),
                color=0xFFD700
            )
            embed.set_footer(text=f"{winner_name} wins!")
            await interaction.response.edit_message(embed=embed, view=view)
            return

        if is_full(view.board):
            view.game_over = True
            view.disable_all()
            embed = discord.Embed(
                title="Connect 4",
                description=render_board(view.board),
                color=0x888888
            )
            embed.set_footer(text="It's a draw!")
            await interaction.response.edit_message(embed=embed, view=view)
            return

        if view.is_vs_ai:
            col = ai_move(view.board)
            if col is not None:
                drop_piece(view.board, col, P2)
                view.refresh_buttons()
                winner = check_winner(view.board)
                if winner:
                    view.game_over = True
                    view.disable_all()
                    embed = discord.Embed(
                        title="Connect 4",
                        description=render_board(view.board),
                        color=0xff0000
                    )
                    embed.set_footer(text="AI wins! Better luck next time.")
                    await interaction.response.edit_message(embed=embed, view=view)
                    return
                if is_full(view.board):
                    view.game_over = True
                    view.disable_all()
                    embed = discord.Embed(
                        title="Connect 4",
                        description=render_board(view.board),
                        color=0x888888
                    )
                    embed.set_footer(text="It's a draw!")
                    await interaction.response.edit_message(embed=embed, view=view)
                    return
            await interaction.response.edit_message(embed=view.make_embed(f"Your turn, {view.player1_name}!"), view=view)
        else:
            view.current_player_id = view.player2_id if player_num == P1 else view.player1_id
            next_name = view.player2_name if player_num == P1 else view.player1_name
            await interaction.response.edit_message(embed=view.make_embed(f"Your turn, {next_name}!"), view=view)



class Connect4View(discord.ui.View):
    def __init__(self, player1_id: int, player1_name: str,
                 player2_id: int, player2_name: str, is_vs_ai: bool):
        super().__init__(timeout=300)
        self.player1_id   = player1_id
        self.player1_name = player1_name
        self.player2_id   = player2_id
        self.player2_name = player2_name
        self.is_vs_ai     = is_vs_ai
        self.current_player_id = player1_id
        self.board = make_board()
        self.game_over = False
        for c in range(COLS):
            self.add_item(ColButton(c))

    def refresh_buttons(self):
        for child in self.children:
            if isinstance(child, ColButton):
                child.disabled = (self.board[0][child.col] != EMPTY)

    def disable_all(self):
        for child in self.children:
            child.disabled = True

    def make_embed(self, turn_msg: str) -> discord.Embed:
        embed = discord.Embed(
            title="Connect 4",
            description=render_board(self.board),
            color=0x3498db
        )
        embed.set_footer(text=f"{DISC_P1} {self.player1_name}  vs  {DISC_P2} {self.player2_name} | {turn_msg}")
        return embed



@app_commands.command(name="connect4", description="Play Connect 4 vs AI or a friend")
@app_commands.describe(opponent="Challenge another player (leave empty to play vs AI)")
@require_access_level(0)
async def connect4(interaction: discord.Interaction, opponent: Optional[discord.Member] = None):
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

    view = Connect4View(p1_id, p1_name, p2_id, p2_name, is_vs_ai)
    turn_msg = f"Your turn, {p1_name}!"
    await interaction.followup.send(embed=view.make_embed(turn_msg), view=view)


async def setup(bot):
    bot.tree.add_command(connect4)
