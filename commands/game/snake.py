import logging
import discord
from discord import app_commands
import random
import asyncio
from utils.embeds import error_embed
from utils.checks import require_access_level
from services.game_service import get_high_score, set_high_score

logger = logging.getLogger(__name__)

_MODES = {'normal': 'Normal', 'hard': 'Hard', 'impossible': 'Impossible'}
_OPPOSITE = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}


class SnakeButton(discord.ui.Button):
    def __init__(self, direction: str, row: int = None):
        _emojis = {'up': '⬆️', 'down': '⬇️', 'left': '⬅️', 'right': '➡️', 'quit': '❌'}
        if direction == 'spacer':
            super().__init__(style=discord.ButtonStyle.secondary, label='─', disabled=True, row=row)
        else:
            style = discord.ButtonStyle.danger if direction == 'quit' else discord.ButtonStyle.primary
            super().__init__(style=style, emoji=_emojis[direction], row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: SnakeView = self.view
        if interaction.user.id != view.player_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        if view.game_over:
            await interaction.response.send_message("Game is over!", ephemeral=True)
            return
        if self.direction == 'quit':
            view.game_over = True
            view.disable_all()
            await view.save_score()
            await interaction.response.edit_message(
                embed=error_embed("Game Ended!", f"**Final Score:** {view.score}\n\n{view.render()}"),
                view=view
            )
            return
        if self.direction != _OPPOSITE.get(view.direction):
            view.next_direction = self.direction
        await interaction.response.defer()


class SnakeView(discord.ui.View):
    def __init__(self, player_id: int, difficulty: str = 'normal'):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.difficulty = difficulty
        self.width = 10
        self.height = 10
        self.snake = [(5, 5), (5, 6), (5, 7)]
        self.direction = 'up'
        self.next_direction = 'up'
        self.walls = []
        self.food = self.spawn_food()
        self.score = 0
        self.game_over = False
        self.message = None
        self.add_item(SnakeButton('spacer', row=0))
        self.add_item(SnakeButton('up', row=0))
        self.add_item(SnakeButton('quit', row=0))
        self.add_item(SnakeButton('left', row=1))
        self.add_item(SnakeButton('down', row=1))
        self.add_item(SnakeButton('right', row=1))

    def spawn_food(self):
        while True:
            x, y = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
            if (x, y) not in self.snake and (x, y) not in self.walls:
                return (x, y)

    def spawn_wall(self):
        hx, hy = self.snake[0]
        deltas = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
        dx, dy = deltas[self.direction]
        ahead = ((hx + dx) % self.width, (hy + dy) % self.height)
        for attempt in range(50):
            x, y = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
            pos = (x, y)
            if pos not in self.snake and pos not in self.walls and pos != self.food:
                if pos != ahead or attempt > 40:
                    self.walls.append(pos)
                    return

    def move(self) -> bool:
        self.direction = self.next_direction
        hx, hy = self.snake[0]
        deltas = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
        dx, dy = deltas[self.direction]
        new_head = (hx + dx, hy + dy)
        if self.difficulty == 'normal':
            new_head = (new_head[0] % self.width, new_head[1] % self.height)
        elif not (0 <= new_head[0] < self.width and 0 <= new_head[1] < self.height):
            return False
        if new_head in self.walls or new_head in self.snake:
            return False
        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 1
            self.food = self.spawn_food()
            if self.difficulty == 'impossible' and random.random() < 0.5:
                self.spawn_wall()
        else:
            self.snake.pop()
        return True

    def render(self) -> str:
        board = [['⬛'] * self.width for _ in range(self.height)]
        for x, y in self.walls:
            board[y][x] = '🟥'
        arrows = {'up': '⬆️', 'down': '⬇️', 'left': '⬅️', 'right': '➡️'}
        for i, (x, y) in enumerate(self.snake):
            board[y][x] = arrows[self.direction] if i == 0 else '🟦'
        if self.food:
            board[self.food[1]][self.food[0]] = '🍎'
        return '\n'.join(''.join(row) for row in board)

    def disable_all(self):
        for child in self.children:
            child.disabled = True

    async def game_loop(self):
        while not self.game_over:
            await asyncio.sleep(0.8)
            if not self.move():
                self.game_over = True
                self.disable_all()
                await self.save_score()
                if self.message:
                    try:
                        await self.message.edit(
                            embed=error_embed("Game Over!", f"**Final Score:** {self.score}\n\n{self.render()}"),
                            view=self
                        )
                    except discord.HTTPException:
                        pass
                break
            mode_name = _MODES[self.difficulty]
            embed = discord.Embed(
                title=f"Snake [{mode_name}] - Score: {self.score}",
                description=self.render(), color=0x00ff00
            )
            embed.set_footer(text="Use arrow buttons to control. X to give up.")
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except discord.HTTPException:
                    break

    async def save_score(self):
        if self.score == 0:
            return
        game_type = f'snake_{self.difficulty}'
        try:
            row = await get_high_score(game_type)
            if not row or self.score > row['score']:
                await set_high_score(game_type, self.player_id, self.score)
                if self.message:
                    prev = row['score'] if row else 0
                    try:
                        await self.message.edit(embed=discord.Embed(
                            title="NEW HIGH SCORE!",
                            description=f"**{self.score}** points ({_MODES[self.difficulty]} mode)\nPrevious best: {prev}",
                            color=0xFFD700
                        ), view=self)
                    except discord.HTTPException:
                        pass
        except Exception as e:
            logger.error(f"Error saving Snake score: {e}")


@app_commands.command(name="snake", description="Play Snake game")
@app_commands.describe(difficulty="Game difficulty: normal (teleport borders), hard (wall borders), impossible (walls + random obstacles)")
@app_commands.choices(difficulty=[
    app_commands.Choice(name="Normal (Teleport Borders)", value="normal"),
    app_commands.Choice(name="Hard (Wall Borders)", value="hard"),
    app_commands.Choice(name="Impossible (Walls + Random Obstacles)", value="impossible")
])
@require_access_level(0)
async def snake(interaction: discord.Interaction, difficulty: app_commands.Choice[str] = None):
    diff = difficulty.value if difficulty else 'normal'
    view = SnakeView(interaction.user.id, diff)
    embed = discord.Embed(
        title=f"Snake [{_MODES[diff]}] - Score: 0",
        description=view.render(), color=0x00ff00
    )
    embed.set_footer(text="Use arrow buttons to control. X to give up.")
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()
    asyncio.create_task(view.game_loop())


async def setup(bot):
    bot.tree.add_command(snake)
